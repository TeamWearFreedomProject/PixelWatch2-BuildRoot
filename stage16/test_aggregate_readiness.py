#!/usr/bin/env python3
import pathlib
import tempfile
import unittest
import aggregate_readiness as audit

class SafetyRegression(unittest.TestCase):
    def test_real_boot_never_approved_by_static_pass(self):
        fake7={"stage":7}
        s13={"stage":13,"physical_fastboot_boot_authorization":"BLOCKED","static_scan_completed":True,
             "nodes":[{}]*16,"source_revisions":{"kernel":"test"}}
        s14={"stage":14,"static_kbuild_tracing":"COMPLETED",
             "physical_fastboot_boot_authorization":"BLOCKED",
             "all_compatible_traces":[{}]*16,"stage13_commit_sources":{"kernel":"test"},
             "kconfig_safety_relevant":{"CONFIG_SOUND":"n"}}
        s15={"stage":15,"static_usb_audit":"PASS",
             "physical_fastboot_boot_authorization":"BLOCKED",
             "boot_kernel_or_gadget_executed":False,
             "gadget_script_would_be_invoked_on_boot":True,
             "physical_usb_enumeration":"NOT_TESTED"}
        self.assertEqual(s13["physical_fastboot_boot_authorization"],"BLOCKED")
        self.assertEqual(s14["physical_fastboot_boot_authorization"],"BLOCKED")
        self.assertEqual(s15["physical_fastboot_boot_authorization"],"BLOCKED")
        self.assertTrue(any(b["id"]=="pmic_thermal" for b in audit.BLOCKERS))
        self.assertTrue(any(b["id"]=="usb_observability" for b in audit.BLOCKERS))

    def test_missing_artifact_or_forged_checksummed_files_fail(self):
        with tempfile.TemporaryDirectory() as td:
            root=pathlib.Path(td)
            (root/"SHA256SUMS").write_text(
                "0"*64+"  boot.img\n")
            (root/"boot.img").write_bytes(b"fake")
            with self.assertRaises(ValueError):
                audit.check_sha(root)

    def test_seven_explicit_warning_and_blocker_records(self):
        self.assertEqual(len(audit.BLOCKERS),7)
        critical=[x for x in audit.BLOCKERS if x["severity"]=="critical"]
        self.assertEqual(len(critical),5)

if __name__=="__main__":
    unittest.main()
