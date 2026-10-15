#!/usr/bin/env python3
"""Inspect known stock vendor_boot and dtbo OFFLINE. No hardware access.

This tool cannot certify hardware boot compatibility. Its safety gate stays
BLOCKED, including when every input is present and structurally valid.
"""
import argparse
import hashlib
import json
import pathlib
import struct

FDT_MAGIC = 0xd00dfeed
DT_TABLE_MAGIC = 0xd7b7ab1e
VENDOR_MAGIC = b"VNDRBOOT"
DEVICE_KEYS = (
    "product", "current-slot", "unlocked", "is-userspace",
    "version-bootloader", "version-baseband",
    "partition-size:boot", "partition-size:boot_a",
    "partition-size:boot_b", "partition-size:vendor_boot_a",
    "partition-size:vendor_boot_b", "partition-size:dtbo_a",
    "partition-size:dtbo_b"
)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def align(n, block):
    return ((n + block - 1) // block) * block


def fdt_summary(data):
    if len(data) < 40:
        raise ValueError("FDT truncated")
    fields = struct.unpack_from(">10I", data)
    magic, size, off_struct, off_strings, _off_rsv, ver, _last, _bootcpu, strs_size, struct_size = fields
    if magic != FDT_MAGIC or not 40 <= size <= len(data):
        raise ValueError("invalid FDT header")
    if off_struct + struct_size > size or off_strings + strs_size > size:
        raise ValueError("FDT section exceeds declared size")
    strings = data[off_strings:off_strings + strs_size]
    sdata = data[off_struct:off_struct + struct_size]
    pos, depth, props = 0, 0, {}
    for _ in range(200000):
        if pos + 4 > len(sdata):
            raise ValueError("FDT structure is truncated")
        token = struct.unpack_from(">I", sdata, pos)[0]
        pos += 4
        if token == 1:
            end = sdata.find(b"\0", pos)
            if end < pos:
                raise ValueError("FDT invalid node")
            pos = align(end + 1, 4)
            depth += 1
        elif token == 2:
            depth -= 1
            if depth < 0:
                raise ValueError("FDT unbalanced node")
        elif token == 3:
            if pos + 8 > len(sdata):
                raise ValueError("FDT property truncated")
            length, name_off = struct.unpack_from(">II", sdata, pos)
            pos += 8
            if name_off >= len(strings) or pos + length > len(sdata):
                raise ValueError("FDT invalid property")
            end = strings.find(b"\0", name_off)
            if end < 0:
                raise ValueError("FDT property name unterminated")
            name = strings[name_off:end].decode("ascii", errors="replace")
            value = sdata[pos:pos + length]
            pos = align(pos + length, 4)
            if depth == 1 and name in ("compatible", "model"):
                props[name] = [v.decode("utf-8", errors="replace")[:100]
                               for v in value.rstrip(b"\0").split(b"\0") if v][:12]
        elif token == 4:
            continue
        elif token == 9:
            if depth != 0:
                raise ValueError("FDT ends with open node")
            return {"bytes": size, "version": ver,
                    "compatible": props.get("compatible", []),
                    "model": props.get("model", [])}
        else:
            raise ValueError("FDT unknown structure token")
    raise ValueError("FDT structure iteration exceeded limit")


def parse_vendor_boot(data):
    if len(data) < 2128 or data[:8] != VENDOR_MAGIC:
        raise ValueError("not a supported vendor_boot image")
    version, page = struct.unpack_from("<2I", data, 8)
    if version not in (3, 4) or page < 512 or page > 65536 or page & (page - 1):
        raise ValueError("unsupported vendor_boot header or page size")
    vendor_ramdisk_size = struct.unpack_from("<I", data, 24)[0]
    hdr_size, dtb_size = struct.unpack_from("<2I", data, 2096)
    expected_header = 2112 if version == 3 else 2128
    if hdr_size != expected_header or dtb_size == 0:
        raise ValueError("unexpected vendor_boot header size or empty DTB")
    dtb_offset = align(hdr_size, page) + align(vendor_ramdisk_size, page)
    if dtb_offset + dtb_size > len(data):
        raise ValueError("vendor_boot DTB exceeds file size")
    blob = data[dtb_offset:dtb_offset+dtb_size]
    trees = []
    pos = 0
    for _ in range(100):
        if pos + 40 > len(blob) or blob[pos:pos+4] != b"\xd0\x0d\xfe\xed":
            break
        summary = fdt_summary(blob[pos:])
        trees.append(summary)
        pos += summary["bytes"]
    if not trees:
        raise ValueError("no raw FDT found in vendor_boot DTB section")
    out = {"sha256":digest(data), "bytes":len(data),
           "header_version":version, "page_size":page,
           "vendor_ramdisk_bytes":vendor_ramdisk_size,
           "dtb_bytes":dtb_size, "dtb_sha256":digest(blob),
           "dtbs":trees, "dtbs_parsed":len(trees)}
    if version == 4:
        table_size, count, entry_size, bc_size = struct.unpack_from("<4I", data, 2112)
        table_start = dtb_offset + align(dtb_size, page)
        if table_start + table_size > len(data) or entry_size > 4096 or count > 1000:
            raise ValueError("vendor ramdisk table is out of range")
        if count and (entry_size == 0 or count*entry_size > table_size):
            raise ValueError("invalid vendor ramdisk fragment table")
        if table_start + align(table_size, page) + bc_size > len(data):
            raise ValueError("vendor bootconfig is out of range")
        out.update({"ramdisk_table_entries":count, "bootconfig_bytes":bc_size})
    return out


def parse_dtbo(data):
    if len(data) < 32:
        raise ValueError("DTBO truncated")
    values = struct.unpack_from(">8I", data)
    magic, total, header, entry_size, count, offset, page, version = values
    if magic != DT_TABLE_MAGIC:
        raise ValueError("DTBO magic not Android device-tree table")
    if total > len(data) or header < 32 or entry_size < 32 or count > 512:
        raise ValueError("invalid DTBO table bounds")
    if offset < header or offset + count * entry_size > total:
        raise ValueError("DTBO entries exceed declared table")
    entries = []
    for i in range(count):
        pos = offset + i * entry_size
        dtb_size, dtb_offset, board_id, revision = struct.unpack_from(">4I",data,pos)
        if dtb_size < 40 or dtb_offset + dtb_size > total:
            raise ValueError("DTBO entry is out of range")
        blob = data[dtb_offset:dtb_offset+dtb_size]
        tree = fdt_summary(blob)
        entries.append({"board_id":board_id,"revision":revision,
                        "offset":dtb_offset,"size":dtb_size,
                        "sha256":digest(blob), "dtb":tree})
    return {"sha256":digest(data), "bytes":len(data), "version":version,
            "page_size":page, "entry_count":count, "entries":entries}


def device_evidence(path):
    evidence = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(evidence, dict):
        raise ValueError("device evidence must be a JSON object")
    # Deliberate allowlist: device IDs / serial numbers are NEVER propagated.
    result = {key: str(evidence[key]) for key in DEVICE_KEYS
              if key in evidence and evidence[key] is not None}
    if result.get("product") not in (None, "aurora"):
        raise ValueError("Device product is not aurora")
    return result


def report(vendor=None, dtbo=None, evidence=None):
    findings = {}
    blockers = []
    if vendor is not None:
        findings["stock_vendor_boot"] = parse_vendor_boot(vendor)
    else:
        blockers.append("Matching stock vendor_boot.img not supplied")
    if dtbo is not None:
        findings["stock_dtbo"] = parse_dtbo(dtbo)
    else:
        blockers.append("Matching stock dtbo.img not supplied")
    if evidence is None:
        blockers.append("Fresh read-only fastboot evidence not supplied")
    else:
        findings["device_evidence"] = evidence
        required = ("product", "current-slot", "unlocked", "version-bootloader")
        for key in required:
            if key not in evidence or not evidence[key]:
                blockers.append("Device evidence missing: " + key)
    blockers += [
        "No proof supplied that stock images match the watch's active firmware and slot",
        "No Qualcomm PMIC, thermal, battery-gauge and charge safety validation",
        "No verified physical USB serial shell or validated non-destructive recovery",
        "No hardware-tested vendor_boot/DTBO/kernel compatibility",
    ]
    return {
        "stage":9, "audit_type":"OFFLINE_READ_ONLY",
        "stock_format_inspection": "COMPLETE" if vendor is not None and dtbo is not None else "INCOMPLETE",
        "physical_fastboot_boot_authorization":"BLOCKED",
        "findings":findings, "unresolved_blockers":blockers,
        "note":"Vendor boot and DTBO formats/compatible strings cannot prove kernel or hardware compatibility."
    }


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--vendor-boot", type=pathlib.Path)
    ap.add_argument("--dtbo", type=pathlib.Path)
    ap.add_argument("--device-evidence", type=pathlib.Path)
    ap.add_argument("--output", type=pathlib.Path, required=True)
    args=ap.parse_args()
    r=report(
        args.vendor_boot.read_bytes() if args.vendor_boot else None,
        args.dtbo.read_bytes() if args.dtbo else None,
        device_evidence(args.device_evidence) if args.device_evidence else None,
    )
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(r,indent=2,ensure_ascii=False)+"\n")
    print("STAGE 9 OFFLINE CHECK:",r["stock_format_inspection"])
    print("PHYSICAL FASTBOOT BOOT:",r["physical_fastboot_boot_authorization"])
    for reason in r["unresolved_blockers"]:
        print("BLOCKED:",reason)

if __name__=="__main__":
    main()
