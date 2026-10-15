#!/usr/bin/env python3
"""Synthetic fixtures only, no user firmware and no device access."""
import json
import pathlib
import struct
import tempfile
import unittest
import inspect_stock as p

def pack_token(value):
    return struct.pack(">I",value)

def padding(data):
    return data + b"\x00"*((-len(data))%4)

def make_fdt():
    strings=b"compatible\x00model\x00"
    compatible=b"qcom,aurora-test\x00qcom,sw5100-test\x00"
    model=b"Synthetic Test Watch\x00"
    s=pack_token(1)+b"\0"*4
    s+=pack_token(3)+struct.pack(">II",len(compatible),0)+padding(compatible)
    s+=pack_token(3)+struct.pack(">II",len(model),len(b"compatible\x00"))+padding(model)
    s+=pack_token(2)+pack_token(9)
    off_struct=56
    off_strings=off_struct+len(s)
    size=off_strings+len(strings)
    h=struct.pack(">10I",p.FDT_MAGIC,size,off_struct,off_strings,40,17,16,0,len(strings),len(s))
    return h+b"\0"*16+s+strings

def make_vendor(dtb):
    header=bytearray(2128)
    header[:8]=p.VENDOR_MAGIC
    struct.pack_into("<II",header,8,4,4096)
    struct.pack_into("<I",header,24,0)
    struct.pack_into("<II",header,2096,2128,len(dtb))
    struct.pack_into("<4I",header,2112,0,0,0,0)
    return bytes(header)+b"\0"*(4096-len(header))+dtb

def make_dtbo(dtb):
    header=struct.pack(">8I",p.DT_TABLE_MAGIC,64+len(dtb),32,32,1,32,4096,0)
    entry=struct.pack(">8I",len(dtb),64,42,1,0,0,0,0)
    return header+entry+dtb

class StockAuditTests(unittest.TestCase):
    def test_synthetic_partition_formats(self):
        fdt=make_fdt()
        vendor=p.parse_vendor_boot(make_vendor(fdt))
        overlay=p.parse_dtbo(make_dtbo(fdt))
        self.assertEqual(vendor["header_version"],4)
        self.assertEqual(vendor["dtbs_parsed"],1)
        self.assertIn("qcom,aurora-test",vendor["dtbs"][0]["compatible"])
        self.assertEqual(overlay["entry_count"],1)
        self.assertEqual(overlay["entries"][0]["board_id"],42)

    def test_no_automatic_boot_approval_even_with_all_inputs(self):
        fdt=make_fdt()
        r=p.report(make_vendor(fdt),make_dtbo(fdt),
            {"product":"aurora","current-slot":"a","unlocked":"yes",
             "version-bootloader":"synthetic-test","is-userspace":"no"})
        self.assertEqual(r["stock_format_inspection"],"COMPLETE")
        self.assertEqual(r["physical_fastboot_boot_authorization"],"BLOCKED")
        self.assertTrue(r["unresolved_blockers"])

    def test_missing_inputs_always_blocked(self):
        r=p.report()
        self.assertEqual(r["stock_format_inspection"],"INCOMPLETE")
        self.assertEqual(r["physical_fastboot_boot_authorization"],"BLOCKED")
        self.assertEqual(len(r["unresolved_blockers"]),7)

    def test_redact_unknown_private_fields(self):
        with tempfile.TemporaryDirectory() as td:
            f=pathlib.Path(td)/"evidence.json"
            f.write_text(json.dumps({"product":"aurora","serialno":"PRIVATE123",
                                      "current-slot":"a","unlocked":"yes"}))
            sanitized=p.device_evidence(f)
            self.assertNotIn("serialno",sanitized)
            self.assertNotIn("PRIVATE123",str(sanitized))

    def test_reject_wrong_device_and_invalid_images(self):
        self.assertRaises(ValueError,p.parse_vendor_boot,b"not a vendor boot")
        self.assertRaises(ValueError,p.parse_dtbo,b"not a dtbo")
        with tempfile.TemporaryDirectory() as td:
            f=pathlib.Path(td)/"evidence.json"
            f.write_text(json.dumps({"product":"shiba"}))
            self.assertRaises(ValueError,p.device_evidence,f)

if __name__=="__main__":
    unittest.main()
