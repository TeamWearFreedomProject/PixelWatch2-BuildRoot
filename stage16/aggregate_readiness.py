#!/usr/bin/env python3
"""Stage 16 final off-device static integration and boot safety gate.

A green Stage 16 CI is only proof that this independent audit completed.
It must never be represented as authorization for a physical fastboot boot.
"""
import argparse
import hashlib
import json
import pathlib
import re
import struct

BLOCKERS = [
    {"id":"pmic_thermal","severity":"critical",
     "reason":"No hardware-demonstrated charger, PMIC, battery-gauge, thermal alarm or safe shutdown. Power modules stored in rootfs, not autoloaded."},
    {"id":"dtbo_overlay","severity":"critical",
     "reason":"Stock vendor_kernel_boot has multiple base DTBs and 11 overlays; effective selected overlay, board revision and runtime device-tree are unknown."},
    {"id":"usb_observability","severity":"critical",
     "reason":"USB PHY, DWC3 gadget enumeration and accessible physical serial shell not demonstrated. QUSB SCM helper experimental."},
    {"id":"stock_recovery","severity":"critical",
     "reason":"Verified return-to-stock and forced restart under power failure not established for the watch's actual slot/build."},
    {"id":"bootloader_runtime","severity":"critical",
     "reason":"Stock vendor boot, DTBO, bootconfig and all boot-image dependencies not validated against this custom kernel at runtime."},
    {"id":"prototype_usb_id","severity":"warning",
     "reason":"Stage 7 initramfs enables a research gadget start script with example USB VID/PID; this is not a production USB identity."},
    {"id":"sound_isolation","severity":"warning",
     "reason":"CONFIG_SOUND=n does not prove physical speaker/haptic silence."},
]

def read_json(path):
    value=json.loads(path.read_text())
    if not isinstance(value,dict):
        raise ValueError("Expected object in "+str(path))
    return value

def check_sha(folder):
    manifest=folder/"SHA256SUMS"
    names=set()
    for line in manifest.read_text().splitlines():
        chunks=line.split(maxsplit=1)
        if len(chunks)!=2 or not re.fullmatch("[0-9a-f]{64}",chunks[0]):
            raise ValueError("Malformed Stage 7 checksums")
        name=chunks[1].lstrip("*")
        if "/" in name or name in names:
            raise ValueError("Unsafe/duplicate Stage 7 checksum path")
        names.add(name)
        if hashlib.sha256((folder/name).read_bytes()).hexdigest()!=chunks[0]:
            raise ValueError("Corrupted Stage 7 artifact: "+name)
    if not {"boot.img","kernel.config","rootfs.cpio.gz","Module.symvers"}.issubset(names):
        raise ValueError("Stage 7 artifact incomplete")
    return names

def evaluate(stage7,stage13,stage14,stage15,oem):
    checks=check_sha(stage7)
    for name,value,phase in (
        ("stage13",stage13,13),("stage14",stage14,14),("stage15",stage15,15)):
        if value.get("stage")!=phase:
            raise ValueError("Wrong stage: "+name)
        if value.get("physical_fastboot_boot_authorization")!="BLOCKED":
            raise ValueError("Unsafe hardware authorization in "+name)
    if stage13.get("static_scan_completed") is not True:
        raise ValueError("Stage 13 source inspection incomplete")
    if stage14.get("static_kbuild_tracing")!="COMPLETED":
        raise ValueError("Stage 14 Kbuild tracing incomplete")
    if stage15.get("static_usb_audit")!="PASS":
        raise ValueError("Stage 15 USB inventory incomplete")
    if not stage15.get("gadget_script_would_be_invoked_on_boot"):
        raise ValueError("USB gadget autostart assumption changed; re-audit")
    if stage15.get("boot_kernel_or_gadget_executed") is not False:
        raise ValueError("Stage 15 is not offline only")
    if len(stage13.get("nodes",[]))!=16 or len(stage14.get("all_compatible_traces",[]))!=16:
        raise ValueError("OF match target count unexpectedly changed")
    if stage13.get("source_revisions")!=stage14.get("stage13_commit_sources"):
        raise ValueError("Stage 13 source pins do not match Stage 14 source audit")
    cfg=(stage7/"kernel.config").read_text().splitlines()
    if "# CONFIG_SOUND is not set" not in cfg:
        raise ValueError("Sound config changed")
    power=read_json(stage7/"integration-report.json")
    abi=read_json(stage7/"abi-report.json")
    if power.get("autoload") is not False or len(power.get("modules",{}))!=8:
        raise ValueError("Missing Stage 7 power non-autoload gate")
    if abi.get("failed_modules")!=[]:
        raise ValueError("Stage 7 ABI failure")
    if len(oem["overlay_entries"])!=11 or len(oem["stock_base_dtbs"])!=2:
        raise ValueError("OEM device tree metadata mismatched")
    if stage14["kconfig_safety_relevant"]["CONFIG_SOUND"]!="n":
        raise ValueError("Stage 14 sound isolation changed")
    boot=(stage7/"boot.img").read_bytes()
    if len(boot)>64*1024*1024 or boot[:8]!=b"ANDROID!":
        raise ValueError("Research boot.img malformed or over 64MiB")
    header_version=struct.unpack_from("<I",boot,40)[0]
    if header_version!=4:
        raise ValueError("Stage 7 research header is not v4")
    if stage15.get("physical_usb_enumeration")!="NOT_TESTED":
        raise ValueError("Static gadget scan cannot claim physical USB test")

    return {
        "stage":16,
        "static_regression_gate":"PASS",
        "physical_boot_readiness":"NO_GO",
        "physical_fastboot_boot_authorization":"BLOCKED",
        "image_size_bytes":len(boot),
        "boot_header_version":header_version,
        "prior_reports_checked":[13,14,15],
        "oem_build":oem["provenance"]["build"],
        "stock_base_dtbs":oem["stock_base_dtbs"],
        "stock_dtbo_count":len(oem["overlay_entries"]),
        "stock_dtbo_selected":"UNKNOWN",
        "eight_matching_abi_power_modules_stored":True,
        "power_modules_auto_loaded":False,
        "qemu_arm32_shell_previously_tested":True,
        "arm64_pixel_watch_kernel_ever_booted_on_real_hardware":False,
        "shell_usb_gadget_attempt_on_boot":True,
        "physical_watch_access_in_this_stage":False,
        "firmware_user_provided_bootloader":"eos-0.4-11366482",
        "firmware_user_provided_baseband":"g5100-00439-230602-B-10247614",
        "user_reported_current_slot":"b",
        "observed_boot_partition_size_bytes":67108864,
        "boot_image_fits_reported_partition_size":len(boot)<=67108864,
        "module_source_of_match_static_evidence_only":True,
        "blockers":BLOCKERS,
        "next_offline_work":[
            "Audit effective DT overlay selection and exact Qualcomm PMIC/thermal bindings (do not infer from compile success).",
            "Assess possible alternative safe Linux kernel hardware diagnostics and recovery with an independent device-port reviewer.",
            "Validate gadget UDC/PHY dependencies and revise demo USB IDs/auto-activation before production use.",
            "Verify currently installed stock recovery path, partition backups, and current firmware before proposing any hardware test.",
        ],
        "limitations":[
            "A successful CI check does not authorize fastboot boot or flash.",
            "No live watch, charging, USB, power, thermal, battery or reboot experiment was performed.",
            "User-reported fastboot details were not automatically re-queried in this CI.",
            "All OEM data committed to this branch are reduced metadata, not proprietary boot binaries.",
        ],
        "stage7_sha256_checks_verified":sorted(checks),
    }

def main():
    p=argparse.ArgumentParser()
    for name in ("stage7-artifact","stage13-report","stage14-report",
                 "stage15-report","oem-manifest","output"):
        p.add_argument("--"+name,type=pathlib.Path,required=True)
    a=p.parse_args()
    report=evaluate(a.stage7_artifact,read_json(a.stage13_report),
        read_json(a.stage14_report),read_json(a.stage15_report),
        read_json(a.oem_manifest))
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(report,indent=2)+"\n")
    print("STAGE16_STATIC_REGRESSION_PASS")
    print("PHYSICAL_BOOT:",report["physical_boot_readiness"])
    for item in report["blockers"]:
        print("BLOCKER",item["id"],item["severity"],item["reason"])
if __name__=="__main__":
    main()
