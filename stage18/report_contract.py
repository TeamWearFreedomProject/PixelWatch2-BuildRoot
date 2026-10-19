#!/usr/bin/env python3
"""Compare locally extracted OEM thermal declarations with pinned EOS source.

The reviewed contract below is not a general C control-flow analyzer.
Immutable source hashes and exact source anchors keep its claims auditable.
CI checks the committed local extraction, not private OEM firmware bytes.
"""
import argparse
import base64
import concurrent.futures
import hashlib
import json
from pathlib import Path
import sys
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from stage17.report_compile import parse_config

DRIVER = "drivers/thermal/qcom/qcom-spmi-temp-alarm.c"
REQUIREMENTS = (
    ("parent_regmap", "required", "dev_get_regmap(pdev->dev.parent, NULL)"),
    ("reg", "required", 'of_property_read_u32(node, "reg", &res)'),
    ("irq_index_0", "required", "platform_get_irq(pdev, 0)"),
    ("thermal_iio_channel", "optional_except_probe_defer", 'devm_iio_channel_get(&pdev->dev, "thermal")'),
    ("iio_probe_defer", "retry_when_provider_not_ready", "if (ret == -EPROBE_DEFER)"),
    ("sensor_registration", "required", "devm_thermal_zone_of_sensor_register("),
    ("hardware_peripheral_type", "runtime_read_required", "type != QPNP_TM_TYPE"),
    ("threaded_irq", "required", "devm_request_threaded_irq(&pdev->dev, chip->irq, NULL,"),
    ("alarm_enable", "register_write_during_init", "reg = ALARM_CTRL_FORCE_ENABLE;"),
    ("adc_temperature", "measurement_path", "iio_read_channel_processed(chip->adc, &mili_celsius)"),
    ("default_temperature", "not_a_measurement", "#define DEFAULT_TEMP\t\t\t37000"),
)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def verify_stage17(folder, pins):
    report_data = (folder / "thermal-object-evidence.json").read_bytes()
    if sha(report_data) != pins["stage17_report_sha256"]:
        raise ValueError("Stage 17 report checksum mismatch")
    report = json.loads(report_data)
    if report["source_git_revision"] != pins["kernel_revision"] or not report["compile_object_verified"]:
        raise ValueError("Wrong Stage 17 kernel/object evidence")
    for filename, key in (("baseline-kernel.config", "baseline_config_sha256"),
                          ("thermal-research.config", "research_config_sha256")):
        if sha((folder / filename).read_bytes()) != report[key]:
            raise ValueError("Stage 17 config checksum mismatch: " + filename)
    return report, parse_config(folder / "baseline-kernel.config"), parse_config(folder / "thermal-research.config")


def fetch_sources(folder, pins):
    def fetch(item):
        path, expected = item
        target = folder / path
        if not target.is_file():
            url = "https://android.googlesource.com/kernel/msm/+/" + pins["kernel_revision"] + "/" + path + "?format=TEXT"
            with urllib.request.urlopen(url, timeout=60) as response:
                data = base64.b64decode(response.read(), validate=True)
            if sha(data) != expected:
                raise ValueError("Downloaded source checksum mismatch: " + path)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        if sha(target.read_bytes()) != expected:
            raise ValueError("Pinned source checksum mismatch: " + path)
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(fetch, pins["files"].items()))


def contract(source, revision):
    text = (source / DRIVER).read_text()
    evidence = []
    for name, requirement, anchor in REQUIREMENTS:
        if anchor not in text:
            raise ValueError("Reviewed driver anchor missing: " + name)
        line = text.count("\n", 0, text.index(anchor)) + 1
        evidence.append({"resource": name, "requirement": requirement, "line": line,
                         "source": DRIVER, "anchor": anchor,
                         "url": "https://android.googlesource.com/kernel/msm/+/" + revision + "/" + DRIVER + "#" + str(line)})
    return evidence


def verify_oem(oem, metadata):
    for label in ("vendor_kernel_boot", "dtbo"):
        if oem["input_sha256"][label] != metadata["provenance"][label + "_sha256"]:
            raise ValueError("Local OEM extraction provenance mismatch")
    expected_bases = metadata["stock_base_dtbs"]
    if len(oem["base_dtbs"]) != len(expected_bases):
        raise ValueError("Missing base DTB")
    for base in oem["base_dtbs"]:
        if oem["graphs"][base["graph_sha256"]]["root_compatible"] != [expected_bases[base["index"]]["compatible"]]:
            raise ValueError("Base DTB compatible mismatch")
    expected_pairs = {(i, j) for i in range(len(expected_bases)) for j in range(len(metadata["overlay_entries"]))}
    records = oem["candidate_combinations"]
    if {(c["base_index"], c["overlay_index"]) for c in records} != expected_pairs or len(records) != len(expected_pairs):
        raise ValueError("Missing/duplicate base-overlay candidate")
    for c in records:
        entry = metadata["overlay_entries"][c["overlay_index"]]
        if (c["board_id"], c["revision"]) != (entry["board_id"], entry["revision"]):
            raise ValueError("Overlay board identity mismatch")
        if c["selected_on_watch"] != "UNKNOWN":
            raise ValueError("Offline extraction cannot identify bootloader selection")
        if c["merge"] == "SUCCEEDED_OFFLINE" and c["graph_sha256"] not in oem["graphs"]:
            raise ValueError("Missing merged graph")
    if oem["selected_overlay"] != "UNKNOWN" or oem["firmware_binaries_published"]:
        raise ValueError("Invalid OEM publication/selection state")


def thermal_signature(g):
    # Whole-DTB equality is NOT claimed: compare only the extracted alarm graph.
    alarms = json.loads(json.dumps(g["thermal_alarms"]))
    for alarm in alarms:
        alarm["ancestors"] = [p for p in alarm["ancestors"] if p["path"] != "/"]
    return sha(json.dumps(alarms, sort_keys=True).encode())


def build_report(oem, metadata, pins, source, stage17_dir):
    stage17, baseline, research = verify_stage17(stage17_dir, pins)
    verify_oem(oem, metadata)
    fetch_sources(source, pins)
    signatures, combinations = set(), []
    for c in oem["candidate_combinations"]:
        entry = {k: c[k] for k in ("base_index", "overlay_index", "board_id", "revision", "merge")}
        if c["merge"] == "SUCCEEDED_OFFLINE":
            g = oem["graphs"][c["graph_sha256"]]
            sig = thermal_signature(g)
            signatures.add(sig)
            entry.update({"thermal_signature": sig, "alarms": len(g["thermal_alarms"]),
                          "issues": [issue for alarm in g["thermal_alarms"] for issue in alarm["issues"]]})
        combinations.append(entry)
    symbols = ("OF", "SPMI", "REGMAP_SPMI", "IIO", "THERMAL", "THERMAL_OF", "QCOM_SPMI_TEMP_ALARM",
               "QCOM_TSENS", "QCOM_SPMI_ADC5_GEN3", "SOUND")
    return {"stage": 18, "scope": "PINNED_SOURCE_CONTRACT_AND_HISTORICAL_LOCAL_OEM_DT_GRAPHS",
            "kernel_revision": pins["kernel_revision"],
            "source_sha256": pins["files"], "stage17_report_sha256": pins["stage17_report_sha256"],
            "stage17_parent_routing": stage17["scratch_parent_kbuild_routing"],
            "reviewed_probe_contract": contract(source, pins["kernel_revision"]),
            "config_comparison": {s: {"baseline": baseline.get(s, "missing"), "stage17": research.get(s, "missing")}
                                  for s in symbols},
            "oem_extraction": {"provenance": oem["input_sha256"], "candidate_pairs": len(combinations),
                               "successful_merges": sum(c["merge"] == "SUCCEEDED_OFFLINE" for c in combinations),
                               "distinct_reduced_thermal_graphs": len(signatures), "candidates": combinations},
            "runtime_probe": "NOT_TESTED", "selected_overlay": "UNKNOWN",
            "battery_temperature_and_charger_policy": "OUTSIDE_PMIC_DIE_ALARM_SCOPE",
            "boot_image_changed": False, "modules_autoload_changed": False,
            "physical_fastboot_boot_authorization": "BLOCKED",
            "limits": ["The OEM graph was extracted locally from hash-matched private firmware; CI cannot re-extract the private bytes.",
                       "All 22 base/overlay pairs are hypothetical; libfdt merge success does not establish hardware applicability.",
                       "Graph equivalence concerns only PMIC thermal resources, not the whole DT or other peripherals.",
                       "PMIC die alarm thresholds are not battery temperature or charging limits.",
                       "IIO is optional to this alarm probe except EPROBE_DEFER; present ADC nodes/configs do not establish readings.",
                       "SPMI regmap, peripheral type/subtype, interrupts and thermal registration still need runtime validation."]}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for arg in ("oem-graphs", "metadata", "pins", "source-dir", "stage17-dir", "output"):
        p.add_argument("--" + arg, type=Path, required=True)
    a = p.parse_args()
    r = build_report(json.loads(a.oem_graphs.read_text()), json.loads(a.metadata.read_text()),
                     json.loads(a.pins.read_text()), a.source_dir, a.stage17_dir)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(r, indent=2) + "\n")
    print("STAGE18_SOURCE_AND_OEM_THERMAL_GRAPH_COMPLETE")
    print(json.dumps(r["oem_extraction"], indent=2))
    print("Runtime probe:", r["runtime_probe"], "selected overlay:", r["selected_overlay"])


if __name__ == "__main__":
    main()
