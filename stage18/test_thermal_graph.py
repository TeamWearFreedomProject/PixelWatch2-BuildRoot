import copy
import json
from pathlib import Path
import struct
import unittest

from thermal_graph import Tree, cells, graph
from report_contract import thermal_signature, verify_oem, verify_stage17


def u32(*args):
    return struct.pack(">" + "I" * len(args), *args)


def fdt(node):
    """Small spec-based fixture encoder independent of the reader."""
    names, offsets = bytearray(), {}
    def encode(name, item):
        props, children = item
        out = u32(1) + name.encode() + b"\0"
        out += b"\0" * (-len(out) % 4)
        for key, value in props.items():
            if key not in offsets:
                offsets[key] = len(names)
                names.extend(key.encode() + b"\0")
            out += u32(3, len(value), offsets[key]) + value + b"\0" * (-len(value) % 4)
        for child, sub in children.items():
            out += encode(child, sub)
        return out + u32(2)
    body = encode("", node) + u32(9)
    off = 56
    return u32(0xD00DFEED, off + len(body) + len(names), off, off + len(body), 40, 17, 16, 0, len(names), len(body)) + bytes(16) + body + names


def fixture():
    alarm = ({"compatible": b"qcom,spmi-temp-alarm\0", "phandle": u32(3),
              "#thermal-sensor-cells": u32(0), "reg": u32(0xA00),
              "interrupts": u32(0, 10, 0, 3), "io-channels": u32(4, 3),
              "io-channel-names": b"thermal\0"}, {})
    adc = ({"phandle": u32(4), "#io-channel-cells": u32(1), "compatible": b"qcom,spmi-adc5-gen3\0"}, {})
    pmic = ({"compatible": b"qcom,spmi-pmic\0"}, {"alarm@a00": alarm, "adc": adc})
    spmi = ({"compatible": b"qcom,spmi-pmic-arb\0", "phandle": u32(2),
             "#interrupt-cells": u32(4), "interrupt-controller": b""}, {"pmic": pmic})
    zone = ({"thermal-sensors": u32(3)}, {"trips": ({}, {"critical": (
        {"temperature": u32(115000), "hysteresis": u32(2000), "type": b"critical\0"}, {})})})
    return ({"compatible": b"fixture\0", "interrupt-parent": u32(1)}, {
        "gic": ({"phandle": u32(1), "#interrupt-cells": u32(3)}, {}),
        "soc": ({}, {"spmi": spmi}), "thermal-zones": ({}, {"pmic": zone})})


def alarm_props(tree):
    return tree[1]["soc"][1]["spmi"][1]["pmic"][1]["alarm@a00"][0]


class GraphTests(unittest.TestCase):
    def test_spmi_irq_uses_nearest_bus_not_root_gic(self):
        alarm = graph(fdt(fixture()))["thermal_alarms"][0]
        self.assertEqual(alarm["interrupts"][0]["provider"]["path"], "/soc/spmi")
        self.assertEqual(alarm["interrupts"][0]["args"], [0, 10, 0, 3])
        self.assertEqual(alarm["iio_channels"][0]["args"], [3])
        self.assertEqual(alarm["thermal_zones"][0]["trips"][0]["temperature_mC"], [115000])
        self.assertEqual(alarm["issues"], [])

    def test_optional_adc_absence_is_not_required_resource_error(self):
        t = fixture()
        alarm_props(t).pop("io-channels")
        alarm_props(t).pop("io-channel-names")
        alarm = graph(fdt(t))["thermal_alarms"][0]
        self.assertIn("CAN_ESTIMATE", alarm["adc_declaration"])
        self.assertEqual(alarm["issues"], [])

    def test_disabled_provider_and_disabled_parent_are_visible(self):
        t = fixture()
        t[1]["soc"][1]["spmi"][0]["status"] = b"disabled\0"
        alarm = graph(fdt(t))["thermal_alarms"][0]
        self.assertFalse(alarm["available_with_ancestors"])
        self.assertFalse(alarm["iio_channels"][0]["provider"]["available_with_ancestors"])

    def test_extended_irq_takes_priority(self):
        t = fixture()
        alarm_props(t)["interrupts-extended"] = u32(1, 0, 32, 4)
        alarm = graph(fdt(t))["thermal_alarms"][0]
        self.assertEqual(alarm["interrupts"][0]["provider"]["path"], "/gic")
        self.assertEqual(alarm["interrupts"][0]["args"], [0, 32, 4])

    def test_unresolved_iio_reference_is_reported(self):
        t = fixture()
        alarm_props(t)["io-channels"] = u32(999, 3)
        self.assertTrue(any("Unresolved phandle" in x for x in graph(fdt(t))["thermal_alarms"][0]["issues"]))

    def test_missing_irq_and_zone_are_not_silently_passed(self):
        t = fixture()
        alarm_props(t).pop("interrupts")
        t[1].pop("thermal-zones")
        issues = graph(fdt(t))["thermal_alarms"][0]["issues"]
        self.assertIn("Missing/unresolved required IRQ", issues)
        self.assertIn("No available thermal-zone reference for driver sensor ID 0", issues)

    def test_sensor_arguments_respect_provider_cells(self):
        t = fixture()
        alarm_props(t)["#thermal-sensor-cells"] = u32(1)
        t[1]["thermal-zones"][1]["pmic"][0]["thermal-sensors"] = u32(3, 5)
        alarm = graph(fdt(t))["thermal_alarms"][0]
        self.assertEqual(alarm["thermal_zones"][0]["sensor_args"], [5])
        self.assertFalse(alarm["thermal_zones"][0]["matches_driver_sensor_id_0"])
        self.assertIn("No available thermal-zone reference for driver sensor ID 0", alarm["issues"])

    def test_truncation_invalid_cells_and_duplicate_phandle_fail(self):
        data = fdt(fixture())
        for bad in (b"", data[:39], data[:-1], b"xxxx" + data[4:]):
            with self.assertRaises(ValueError):
                Tree(bad)
        with self.assertRaises(ValueError):
            cells(b"123")
        t = fixture()
        alarm_props(t)["phandle"] = u32(1)
        with self.assertRaises(ValueError):
            Tree(fdt(t))


class ProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parents[1]
        self.oem = json.loads((self.root / "stage18/oem-thermal-graphs.json").read_text())
        self.metadata = json.loads((self.root / "stage12/twd9-dtb-derived.json").read_text())

    def test_actual_reduced_extraction_has_all_candidates(self):
        verify_oem(self.oem, self.metadata)
        self.assertEqual(len(self.oem["candidate_combinations"]), 22)
        self.assertTrue(all(c["merge"] == "SUCCEEDED_OFFLINE" for c in self.oem["candidate_combinations"]))
        signatures = {thermal_signature(self.oem["graphs"][c["graph_sha256"]]) for c in self.oem["candidate_combinations"]}
        self.assertEqual(len(signatures), 1)
        for g in self.oem["graphs"].values():
            self.assertEqual(len(g["thermal_alarms"]), 1)
            self.assertEqual(g["thermal_alarms"][0]["issues"], [])

    def test_wrong_hash_missing_pair_or_claimed_selection_fail(self):
        for change in ("hash", "pair", "selection"):
            r = copy.deepcopy(self.oem)
            if change == "hash":
                r["input_sha256"]["dtbo"] = "0" * 64
            elif change == "pair":
                r["candidate_combinations"].pop()
            else:
                r["candidate_combinations"][0]["selected_on_watch"] = True
            with self.assertRaises(ValueError):
                verify_oem(r, self.metadata)

    def test_corrupted_stage17_evidence_is_rejected(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "thermal-object-evidence.json").write_text("{}")
            with self.assertRaisesRegex(ValueError, "checksum"):
                verify_stage17(Path(d), {"stage17_report_sha256": "0" * 64})


if __name__ == "__main__":
    unittest.main()
