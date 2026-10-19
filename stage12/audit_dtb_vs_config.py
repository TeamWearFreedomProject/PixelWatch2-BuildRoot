#!/usr/bin/env python3
"""Offline compare OEM-derived base DTB + DTBO clues to Stage 7 config.

Only suggests kernel Kconfig inspection targets. It never infers an actual
OF match, a selected overlay, safe PMIC/charger behavior or boot permission.
"""
import argparse
import gzip
import hashlib
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "stage7"))
from pack_modules import read_records

EXPECTED_POWER = {
    "gvotable.ko", "logbuffer.ko", "qpnp-smblite-main.ko",
    "qti-qbg-main.ko", "google-bms.ko", "google-battery.ko",
    "google-charger.ko", "sw5100_bms.ko"
}
EXPECTED_OVERLAY = {
    "google,battery", "google,charger",
    "google,extcon-usb-shim", "google,smblite-hvdcp"
}

def validate_manifest(manifest):
    prov = manifest["provenance"]
    for field in ("vendor_kernel_boot_sha256", "dtbo_sha256"):
        if not re.fullmatch(r"[0-9a-f]{64}", prov[field]):
            raise ValueError("Missing OEM SHA256 provenance: " + field)
    bases = manifest["stock_base_dtbs"]
    if len(bases) != 2 or {r["compatible"] for r in bases} != {"qcom,monaco", "qcom,monacop"}:
        raise ValueError("Expected two distinct OEM Monaco-family base DTBs")
    targets = manifest["target_compatibles"]
    compatible_set = {r["compatible"] for r in targets}
    if len(targets) != len(compatible_set):
        raise ValueError("Duplicate OEM compatible record")
    for name in ("qcom,qbg", "qcom,qpnp-pm5100-smblite", "qcom,dwc-usb3-msm",
                 "snps,dwc3", "qcom,usb-hsphy-snps-femto"):
        if name not in compatible_set:
            raise ValueError("Missing important device tree compatible: " + name)
    by_name = {r["compatible"]:r for r in targets}
    if by_name["qcom,qbg"]["base_status"] != "disabled":
        raise ValueError("Wrong OEM QBG baseline; do not silently infer enabled")
    for node in targets:
        if node["base_status"] not in ("disabled", "ok", "okay", "unspecified"):
            raise ValueError("Invalid device tree status")
        if not node["config_hints"] or not all(re.fullmatch(r"[A-Z0-9_]+", v) for v in node["config_hints"]):
            raise ValueError("Invalid Kconfig audit hint")
    overlays = manifest["overlay_entries"]
    if len(overlays) != 11 or [r["index"] for r in overlays] != list(range(11)):
        raise ValueError("OEM DTBO table requires exactly 11 indexed records")
    if len({(r["board_id"],r["revision"]) for r in overlays}) != 11:
        raise ValueError("Duplicate DTBO board ID / revision")
    if set(manifest["overlay_required_compatibles"]) != EXPECTED_OVERLAY:
        raise ValueError("Wrong expected OEM overlay compatible list")
    for ov in overlays:
        if set(ov["found_compatible"]) != EXPECTED_OVERLAY:
            raise ValueError("Missing OEM battery/USB node in overlay " + str(ov["index"]))

def parse_config(data):
    config = {}
    for line in data.splitlines():
        if line.startswith("CONFIG_") and "=" in line:
            key, value = line.split("=",1)
            config[key.removeprefix("CONFIG_")] = value
        else:
            hit = re.fullmatch(r"# CONFIG_([A-Za-z0-9_]+) is not set", line)
            if hit:
                config[hit.group(1)] = "n"
    return config

def verify_artifact(folder):
    members = set()
    for line in (folder / "SHA256SUMS").read_text().splitlines():
        fields = line.split(maxsplit=1)
        if len(fields) != 2:
            raise ValueError("Bad Stage 7 SHA256SUMS line")
        sha, name = fields
        name = name.lstrip("*")
        if not re.fullmatch(r"[0-9a-f]{64}", sha) or "/" in name or name in members:
            raise ValueError("Unsafe or duplicated checksum path")
        data = (folder / name).read_bytes()
        if hashlib.sha256(data).hexdigest() != sha:
            raise ValueError("Stage 7 integrity mismatch: " + name)
        members.add(name)
    for required in ("kernel.config", "rootfs.cpio.gz", "Module.symvers", "boot.img"):
        if required not in members:
            raise ValueError("Stage 7 missing checksum for " + required)
    archive = read_records(gzip.decompress((folder / "rootfs.cpio.gz").read_bytes()))
    paths = [rec[2].removeprefix("./") for rec in archive]
    found = {pathlib.PurePosixPath(p).name for p in paths if p.endswith(".ko")}
    if found != EXPECTED_POWER or len([p for p in paths if p.endswith(".ko")]) != 8:
        raise ValueError("Stage 7 stored power modules no longer match eight expected")
    integration = json.loads((folder / "integration-report.json").read_text())
    if integration.get("autoload") is not False:
        raise ValueError("Unexpected Stage 7 module autoload enabled")
    abi = json.loads((folder / "abi-report.json").read_text())
    if abi.get("failed_modules") != []:
        raise ValueError("Stage 7 ABI test has unresolved failures")
    return parse_config((folder / "kernel.config").read_text()), sorted(found)

def run(manifest, config, stored):
    validate_manifest(manifest)
    essentials = ("ARM64", "COMPAT", "MODULES", "MODVERSIONS", "SPMI", "REGMAP_SPMI",
                  "USB_DWC3", "USB_GADGET", "USB_CONFIGFS_ACM", "QCOM_SCM",
                  "REGULATOR", "THERMAL")
    missing = [key for key in essentials if config.get(key) != "y"]
    if missing:
        raise ValueError("Unexpected absence of previously built core config: " + ", ".join(missing))
    if config.get("SOUND") != "n":
        raise ValueError("Stage 7 speaker-disabled research config unexpectedly changed")
    if set(stored) != EXPECTED_POWER:
        raise ValueError("Unexpected stored modules")

    nodes = []
    for node in manifest["target_compatibles"]:
        hints = {key: config.get(key, "not present in config") for key in node["config_hints"]}
        nodes.append({
            "category": node["category"],
            "oem_compatible": node["compatible"],
            "base_status": node["base_status"],
            "stage7_kconfig_search_hints": hints,
            "exact_source_of_match_checked": False,
            "merged_overlay_checked": False,
            "driver_binds_on_watch": "UNKNOWN"
        })
    return {
        "stage": 12,
        "static_manifest_and_config": "PASS",
        "physical_fastboot_boot_authorization": "BLOCKED",
        "provenance": manifest["provenance"],
        "base_dtbs": manifest["stock_base_dtbs"],
        "overlay_total": len(manifest["overlay_entries"]),
        "overlay_board_id_revision": [
            {"index":r["index"],"board_id":r["board_id"],"revision":r["revision"]}
            for r in manifest["overlay_entries"]],
        "overlay_selected_by_this_watch": "UNKNOWN",
        "oem_overlays_all_contain": manifest["overlay_required_compatibles"],
        "stage7_eight_power_modules": sorted(stored),
        "stage7_power_module_autoload": False,
        "stage7_core_kernel_configs": {key:config[key] for key in essentials},
        "device_tree_nodes":nodes,
        "crucial_findings":[
            "Both OEM base FDTs mark QBG disabled; final merged status after actual DTBO is unknown.",
            "All eleven OEM DTBO entries add charger/battery/extcon nodes; no overlay is yet identified as the one the bootloader selects.",
            "Qualcomm USB PHY and DWC3 node presence does not prove the specific driver binds, the clock/PHY initializes, or CDC ACM enumerates.",
            "Eight matching external modules with valid depmod ABI are stored, but are not loaded. Missing charging/thermal runtime proof prevents a safe boot claim.",
            "Kconfig candidates are search hints, not proofs of matching of_device_id entries or driver readiness."
        ],
        "further_evidence_required":[
            "Exact OEM overlay selection and offline merged FDT for this watch hardware revision",
            "Exact EOS kernel source OF match tables and enabled driver objects for all critical compatibles",
            "Regulator, SPMI, PMIC, ADC, watchdog and battery safety behavior; no device-side verification",
            "Physical USB PHY/UDC and non-destructive recovery path",
        ],
        "watch_used": False,
        "code_or_power_modules_loaded": False
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--manifest", type=pathlib.Path, required=True)
    p.add_argument("--stage7-artifact",type=pathlib.Path,required=True)
    p.add_argument("--output",type=pathlib.Path,required=True)
    a=p.parse_args()
    manifest=json.loads(a.manifest.read_text())
    config,stored=verify_artifact(a.stage7_artifact)
    report=run(manifest,config,stored)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("STAGE12_STATIC_CONFIG_AND_OEM_FDT_MANIFEST: PASS")
    print("OEM base DTB: monacop + monaco; overlays:",report["overlay_total"])
    for node in report["device_tree_nodes"]:
        print("DT_NODE",node["oem_compatible"],"base_status="+node["base_status"],
              "config_hints="+str(node["stage7_kconfig_search_hints"]))
    print("HARDWARE_BOOT:",report["physical_fastboot_boot_authorization"])

if __name__ == "__main__":
    main()
