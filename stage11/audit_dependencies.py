#!/usr/bin/env python3
"""Stage 11 offline comparison of user-derived OEM module graph and Stage 7.
It never loads modules or communicates with any device.
"""
import argparse
import gzip
import hashlib
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "stage7"))
from pack_modules import read_records


def basename(value):
    return pathlib.PurePosixPath(value).name


def parse_depfile(data):
    result = {}
    for line in data.decode("utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            raise ValueError("Invalid depmod entry")
        module, deps = line.split(":", 1)
        name = basename(module.strip())
        if name in result:
            raise ValueError("Duplicate depmod module: " + name)
        result[name] = sorted(set(basename(x) for x in deps.split()))
    return result


def closure(names, graph):
    pending = list(names)
    seen = set(names)
    while pending:
        name = pending.pop()
        for dep in graph.get(name, []):
            if dep not in seen:
                seen.add(dep)
                pending.append(dep)
    return sorted(seen)


def verify_sha256(root):
    lines = (root / "SHA256SUMS").read_text().splitlines()
    checked = set()
    for line in lines:
        checksum, path = line.split(maxsplit=1)
        name = path.lstrip("*")
        if "/" in name or name in checked:
            raise ValueError("unsafe SHA256SUMS member")
        if hashlib.sha256((root / name).read_bytes()).hexdigest() != checksum:
            raise ValueError("Stage 7 checksum mismatch: " + name)
        checked.add(name)
    if "rootfs.cpio.gz" not in checked:
        raise ValueError("Stage 7 rootfs not authenticated with checksums")
    return sorted(checked)


def analyze(manifest, artifact):
    checksums = verify_sha256(artifact)
    expected = manifest["power_modules"]
    if len(expected) != 8 or len(set(expected)) != 8:
        raise ValueError("OEM manifest must include exactly eight unique power modules")
    stock = {k: sorted(set(v)) for k, v in manifest["stock_direct_module_deps"].items()}
    if set(stock) != set(expected):
        raise ValueError("OEM dependency graph keys not equal to OEM power modules")
    if set(closure(expected, stock)) != set(expected):
        raise ValueError("OEM power module graph has unexpected external .ko dependency")
    for profile in ("normal", "charger", "recovery"):
        positions = manifest["power_position_zero_based"][profile]
        if profile == "normal":
            if positions:
                raise ValueError("OEM normal profile unexpectedly lists power group")
        elif len(positions) != 8:
            raise ValueError("OEM "+profile+" power order is not complete")

    archive = gzip.decompress((artifact / "rootfs.cpio.gz").read_bytes())
    records = read_records(archive)
    rootfs = {}
    for entry in records:
        name = entry[2].removeprefix("./")
        if name in rootfs:
            raise ValueError("Duplicate initramfs member")
        rootfs[name] = entry[3]
    stored = sorted(basename(n) for n in rootfs if n.endswith(".ko"))
    if stored != sorted(expected):
        raise ValueError("Stage 7 module set differs from OEM 8 power modules: "+repr(stored))
    meta = json.loads((artifact / "integration-report.json").read_text())
    abi = json.loads((artifact / "abi-report.json").read_text())
    if meta.get("autoload") is not False:
        raise ValueError("Stage 7 modules must not autoload")
    if abi.get("failed_modules") != [] or len(abi.get("module_checks", {})) != 8:
        raise ValueError("Stage 7 ABI check is not complete")
    prefix = meta["module_base"]
    if prefix + "/modules.dep" not in rootfs:
        raise ValueError("Missing depmod metadata in Stage 7 rootfs")
    stage7 = parse_depfile(rootfs[prefix + "/modules.dep"])
    if set(stage7) != set(expected):
        raise ValueError("Stage 7 depmod entries do not match eight modules")
    comparisons = {}
    for name in expected:
        oem = set(stock[name])
        ours = set(stage7[name])
        comparisons[name] = {
            "OEM_direct_module_deps": sorted(oem),
            "Stage7_direct_module_deps": sorted(ours),
            "OEM_only_dependencies": sorted(oem - ours),
            "Stage7_only_dependencies": sorted(ours - oem),
            "exact_filename_dependency_match": oem == ours,
        }

    config = (artifact / "kernel.config").read_text().splitlines()
    select = ("CONFIG_QCOM_SCM", "CONFIG_SPMI", "CONFIG_REGMAP_SPMI",
              "CONFIG_USB_DWC3", "CONFIG_USB_GADGET", "CONFIG_USB_CONFIGFS_ACM",
              "CONFIG_PHY_QCOM", "CONFIG_THERMAL", "CONFIG_PINCTRL",
              "CONFIG_REGULATOR", "CONFIG_MODULES", "CONFIG_SOUND")
    found = {}
    for key in select:
        line = next((l for l in config if l.startswith(key+"=") or
                     l == "# "+key+" is not set"), None)
        found[key] = (line.split("=", 1)[1] if line and "=" in line
                      else ("n" if line else "unknown"))
    usb_oem = manifest["stock_recovery_usb"]
    return {
        "stage": 11,
        "test": "pinned Stage 7 static initramfs vs manually reviewed TWD9 OEM modules.dep metadata",
        "artifact_checksums_verified": checksums,
        "oem_image_sha256_provenance": manifest["oem_image_sha256"],
        "oem_stock_total_modules": manifest["stock_module_count"],
        "oem_load_counts": manifest["stock_load_count"],
        "oem_power_load_normal": 0,
        "oem_power_load_charger": 8,
        "oem_power_load_recovery": 8,
        "stage7_power_modules_in_initramfs": len(stored),
        "stage7_power_modules_autoload": False,
        "oem_power_module_graph_closure": closure(expected, stock),
        "stage7_power_module_graph_closure": closure(expected, stage7),
        "per_module_direct_dependency_comparison": comparisons,
        "kernel_config_selected": found,
        "oem_recovery_usb_module_dependencies": usb_oem,
        "oem_recovery_usb_module_positions_zero_based": manifest["stock_recovery_usb_position_zero_based"],
        "usb_oem_modules_stored_in_stage7_initramfs": sorted(set(stored).intersection(usb_oem)),
        "oem_other_modules_not_bundled_in_stage7_rootfs":
            manifest["stock_module_count"] - len(stored),
        "interpretation": [
            "A module not stored as .ko can be built into a kernel; absence in initramfs is not proof of missing functionality.",
            "Dependency names and a successful modpost do not establish SPMI/PMIC, thermal, charging or USB hardware readiness.",
            "Stock charger/recovery boot profiles and the custom Linux minimal system have different service and hardware initialization assumptions.",
            "OEM .ko files have another kernel ABI and MUST NOT be copied into Stage 7 Linux.",
        ],
        "runtime_hardware_tested": False,
        "physical_fastboot_boot_authorization": "BLOCKED",
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", type=pathlib.Path, required=True)
    ap.add_argument("--stage7-artifact", type=pathlib.Path, required=True)
    ap.add_argument("--output", type=pathlib.Path, required=True)
    args = ap.parse_args()
    report = analyze(json.loads(args.manifest.read_text()), args.stage7_artifact)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print("STAGE 11 OFFLINE COMPARISON COMPLETE")
    for name, entry in report["per_module_direct_dependency_comparison"].items():
        print(name, "match=", entry["exact_filename_dependency_match"],
              "OEM-only=", entry["OEM_only_dependencies"],
              "Stage7-only=", entry["Stage7_only_dependencies"])
    print("Physical fastboot boot:", report["physical_fastboot_boot_authorization"])


if __name__ == "__main__":
    main()
