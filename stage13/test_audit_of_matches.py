#!/usr/bin/env python3
"""Offline synthetic unit tests, no OEM binaries or device."""
import json
import pathlib
import tempfile
import unittest
import audit_of_matches as audit

class SourceTests(unittest.TestCase):
    def test_comments_not_counted_as_driver_matches(self):
        c='/* struct of_device_id fake[] = {\n { .compatible = "qcom,a" },\n }; */\n'
        self.assertFalse(audit.TABLE_RE.search(audit.strip_comments(c)))

    def test_table_and_direct_kbuild_config(self):
        with tempfile.TemporaryDirectory() as td:
            root=pathlib.Path(td)
            folder=root/"drivers"/"watch"
            folder.mkdir(parents=True)
            (folder/"probe.c").write_text(
                'static const struct of_device_id watch_of_match[] = {\n'
                ' { .compatible = "qcom,probe" },\n'
                ' { .compatible = "qcom,another" },\n'
                '};\nMODULE_DEVICE_TABLE(of,watch_of_match);\n'
                '/* { .compatible = "qcom,commented" } */')
            (folder/"Makefile").write_text("obj-$(CONFIG_WATCH_PROBE) += probe.o\n")
            result=audit.scan(root,{"WATCH_PROBE":"y"},
                              {"qcom,probe","qcom,another","qcom,commented"})
            match=result["of_matches"]["qcom,probe"]
            self.assertEqual(len(match),1)
            self.assertEqual(match[0]["table"],"watch_of_match")
            self.assertEqual(match[0]["makefile_direct_rules"][0]["stage7_config"],"y")
            self.assertEqual(result["of_matches"]["qcom,commented"],[])

    def test_unsafe_claim_not_possible_from_literals(self):
        with tempfile.TemporaryDirectory() as td:
            root=pathlib.Path(td)
            folder=root/"drivers"/"misc"
            folder.mkdir(parents=True)
            (folder/"foo.c").write_text('static const char *hint = "qcom,qbg";\n')
            result=audit.scan(root,{},{"qcom,qbg"})
            self.assertEqual(result["of_matches"]["qcom,qbg"],[])
            self.assertTrue(result["other_literal_files"]["qcom,qbg"])

    def test_config_parser(self):
        config=audit.parse_config(
            "CONFIG_SPMI=y\n# CONFIG_QCOM_POWER_SUPPLY is not set\n"
            "CONFIG_USB_GADGET=m\n")
        self.assertEqual(config["SPMI"],"y")
        self.assertEqual(config["QCOM_POWER_SUPPLY"],"n")
        self.assertEqual(config["USB_GADGET"],"m")

if __name__=="__main__":
    unittest.main()
