#!/usr/bin/env python3
import unittest
import audit_dependencies as audit


class ComparisonTests(unittest.TestCase):
    def test_parse_depmod_and_closure(self):
        text = b"extra/gvotable.ko:\nextra/google-bms.ko: extra/logbuffer.ko\n"
        d = audit.parse_depfile(text)
        self.assertEqual(d["google-bms.ko"], ["logbuffer.ko"])
        self.assertEqual(audit.closure(["google-bms.ko"], d),
                         ["google-bms.ko", "logbuffer.ko"])

    def test_oem_power_8_dependencies_close(self):
        data = {
            "gvotable.ko": [],
            "logbuffer.ko": [],
            "qpnp-smblite-main.ko": ["gvotable.ko"],
            "qti-qbg-main.ko": [],
            "google-bms.ko": ["logbuffer.ko"],
            "google-battery.ko": ["google-bms.ko", "logbuffer.ko", "gvotable.ko"],
            "google-charger.ko": ["google-bms.ko", "logbuffer.ko", "gvotable.ko"],
            "sw5100_bms.ko": ["qpnp-smblite-main.ko", "google-bms.ko",
                               "logbuffer.ko", "gvotable.ko"],
        }
        self.assertEqual(set(audit.closure(data, data)), set(data))

    def test_missing_supplementary_usb_module_does_not_imply_built_in(self):
        stage7 = ["gvotable.ko", "logbuffer.ko"]
        stock = ["dwc3-msm.ko", "phy-msm-snps-hs.ko"]
        self.assertFalse(set(stock).intersection(stage7))
        # Absence from /lib/modules is not evidence of whether the kernel
        # built the corresponding functionality in statically or not.


if __name__ == "__main__":
    unittest.main()
