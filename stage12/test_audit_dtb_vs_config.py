#!/usr/bin/env python3
"""Synthetic tests; no OEM binary files or live devices."""
import json
import pathlib
import unittest
import audit_dtb_vs_config as m

MANIFEST = pathlib.Path(__file__).with_name("twd9-dtb-derived.json")

class Stage12Tests(unittest.TestCase):
    def setUp(self):
        self.metadata = json.loads(MANIFEST.read_text())
        self.config = {key:"y" for key in (
            "ARM64","COMPAT","MODULES","MODVERSIONS","SPMI","REGMAP_SPMI",
            "USB_DWC3","USB_GADGET","USB_CONFIGFS_ACM","QCOM_SCM",
            "REGULATOR","THERMAL")}
        self.config["SOUND"]="n"

    def test_manifest_and_critical_qbg_disabled(self):
        m.validate_manifest(self.metadata)
        qbg=next(r for r in self.metadata["target_compatibles"]
                 if r["compatible"]=="qcom,qbg")
        self.assertEqual(qbg["base_status"],"disabled")
        self.assertEqual(len(self.metadata["overlay_entries"]),11)

    def test_no_false_boot_approval_when_config_is_all_built_in(self):
        result=m.run(self.metadata,self.config,m.EXPECTED_POWER)
        self.assertEqual(result["static_manifest_and_config"],"PASS")
        self.assertEqual(result["physical_fastboot_boot_authorization"],"BLOCKED")
        self.assertEqual(result["overlay_selected_by_this_watch"],"UNKNOWN")
        self.assertTrue(all(x["driver_binds_on_watch"]=="UNKNOWN"
                            for x in result["device_tree_nodes"]))

    def test_reject_unsupported_qbg_enabled_claim(self):
        altered=json.loads(json.dumps(self.metadata))
        next(r for r in altered["target_compatibles"] if r["compatible"]=="qcom,qbg")["base_status"]="okay"
        with self.assertRaises(ValueError):
            m.validate_manifest(altered)

    def test_reject_incomplete_dtbo_table(self):
        altered=json.loads(json.dumps(self.metadata))
        altered["overlay_entries"].pop()
        with self.assertRaises(ValueError):
            m.validate_manifest(altered)

    def test_missing_usb_config_fails_static_gate(self):
        self.config["USB_DWC3"]="n"
        with self.assertRaises(ValueError):
            m.run(self.metadata,self.config,m.EXPECTED_POWER)

    def test_config_parser_negative_state(self):
        config=m.parse_config("CONFIG_USB_DWC3=y\n# CONFIG_SOUND is not set\n")
        self.assertEqual(config["USB_DWC3"],"y")
        self.assertEqual(config["SOUND"],"n")

if __name__=="__main__":
    unittest.main()
