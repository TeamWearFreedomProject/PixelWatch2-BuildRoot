#!/usr/bin/env python3
import pathlib
import tempfile
import unittest
import report_compile as r

class ThermalConfigTests(unittest.TestCase):
    def test_one_target_symbol_becomes_enabled(self):
        with tempfile.TemporaryDirectory() as td:
            base=pathlib.Path(td)/"base.config"
            enabled=pathlib.Path(td)/"enabled.config"
            foundation=("CONFIG_ARM64=y\nCONFIG_THERMAL=y\nCONFIG_SPMI=y\n"
                        "CONFIG_REGMAP_SPMI=y\n# CONFIG_SOUND is not set\n"
                        "# CONFIG_TRIM_UNUSED_KSYMS is not set\n"
                        "# CONFIG_QCOM_POWER_SUPPLY is not set\n")
            base.write_text(foundation+"# CONFIG_QCOM_SPMI_TEMP_ALARM is not set\n")
            enabled.write_text(foundation+"CONFIG_QCOM_SPMI_TEMP_ALARM=y\n")
            result=r.compare(base,enabled)
            self.assertEqual(set(result),{"QCOM_SPMI_TEMP_ALARM"})
            self.assertEqual(result["QCOM_SPMI_TEMP_ALARM"],
                             {"stage7":"n","research_variant":"y"})

    def test_must_not_disable_sound_or_other_safe_baseline_config(self):
        with tempfile.TemporaryDirectory() as td:
            base=pathlib.Path(td)/"base.config"
            enabled=pathlib.Path(td)/"enabled.config"
            foundation=("CONFIG_ARM64=y\nCONFIG_THERMAL=y\nCONFIG_SPMI=y\n"
                        "CONFIG_REGMAP_SPMI=y\n"
                        "# CONFIG_TRIM_UNUSED_KSYMS is not set\n"
                        "# CONFIG_QCOM_POWER_SUPPLY is not set\n")
            base.write_text(foundation+"# CONFIG_SOUND is not set\n"
                            "# CONFIG_QCOM_SPMI_TEMP_ALARM is not set\n")
            enabled.write_text(foundation+"CONFIG_SOUND=y\n"
                               "CONFIG_QCOM_SPMI_TEMP_ALARM=y\n")
            with self.assertRaisesRegex(ValueError,"SOUND"):
                r.compare(base,enabled)

    def test_parser_handles_both_kconfig_states(self):
        with tempfile.TemporaryDirectory() as td:
            f=pathlib.Path(td)/"sample"
            f.write_text("CONFIG_USB_DWC3=y\n# CONFIG_QCOM_SPMI_TEMP_ALARM is not set\n")
            actual=r.parse_config(f)
            self.assertEqual(actual["USB_DWC3"],"y")
            self.assertEqual(actual["QCOM_SPMI_TEMP_ALARM"],"n")

if __name__=="__main__":
    unittest.main()
