#!/usr/bin/env python3
import pathlib
import tempfile
import unittest
import audit_usb_startup as a

class UsbParserTests(unittest.TestCase):
    def test_config_disabled_and_enabled(self):
        with tempfile.TemporaryDirectory() as td:
            root=pathlib.Path(td)
            (root/"kernel.config").write_text(
                "CONFIG_USB_DWC3=y\n"
                "CONFIG_USB_CONFIGFS_ACM=y\n"
                "# CONFIG_SOUND is not set\n")
            c=a.get_config(root)
            self.assertEqual(c["USB_CONFIGFS_ACM"],"y")
            self.assertEqual(c["SOUND"],"n")

    def test_missing_archive_is_not_boot_approval(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(FileNotFoundError):
                a.audit(pathlib.Path(td))

    def test_actual_script_guards_exist_in_repository(self):
        root=pathlib.Path(__file__).resolve().parents[1]
        code=(root/"stage5/rootfs-overlay/usr/sbin/aurora-acm").read_text()
        self.assertIn("/sys/class/udc",code)
        self.assertIn("dev-acm-enabled",code)
        self.assertIn('echo "$UDC" > "$G/UDC"',code)
        self.assertIn("0x1d6b",code)

if __name__=="__main__":
    unittest.main()
