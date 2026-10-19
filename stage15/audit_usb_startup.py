#!/usr/bin/env python3
"""Stage 15 static USB CDC ACM / login-chain audit.

No USB gadget is activated; no device access, mounts, login or user code is
executed. A structural shell/profile check is not physical USB readiness.
"""
import argparse
import gzip
import hashlib
import json
import pathlib
import re
import sys

sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/"stage7"))
from pack_modules import read_records

SHELL = "usr/sbin/aurora-acm"
SERVICE = "etc/init.d/S90aurora-acm"
INITTAB = "etc/inittab"
MARKER = "etc/aurora/dev-acm-enabled"

def get_config(root):
    result={}
    for line in (root/"kernel.config").read_text().splitlines():
        hit=re.fullmatch(r"CONFIG_([A-Za-z0-9_]+)=(.*)",line)
        if hit:
            result[hit.group(1)]=hit.group(2)
        hit=re.fullmatch(r"# CONFIG_([A-Za-z0-9_]+) is not set",line)
        if hit:
            result[hit.group(1)]="n"
    return result

def source_digest_check(root):
    seen=set()
    for item in (root/"SHA256SUMS").read_text().splitlines():
        parts=item.split(maxsplit=1)
        if len(parts)!=2 or not re.fullmatch(r"[0-9a-f]{64}",parts[0]):
            raise ValueError("invalid artifact SHA256SUMS line")
        name=parts[1].lstrip("*")
        if name in seen or "/" in name:
            raise ValueError("duplicate/unsafe SHA256 file")
        seen.add(name)
        if hashlib.sha256((root/name).read_bytes()).hexdigest()!=parts[0]:
            raise ValueError("Checksum mismatch: "+name)
    if not {"rootfs.cpio.gz","kernel.config","boot.img"}.issubset(seen):
        raise ValueError("Stage 7 rootfs/config missing verified checksum")

def audit(artifact, stage14=None):
    source_digest_check(artifact)
    archive = read_records(gzip.decompress((artifact/"rootfs.cpio.gz").read_bytes()))
    members={}
    for entry in archive:
        name=entry[2].removeprefix("./")
        if name in members:
            raise ValueError("Duplicate initramfs path: "+name)
        members[name]=entry[3]
    for item in (SHELL,SERVICE,INITTAB):
        if item not in members:
            raise ValueError("Required USB shell entry absent: "+item)
    gadget=members[SHELL].decode("utf-8")
    service=members[SERVICE].decode("utf-8")
    init=members[INITTAB].decode("utf-8")
    enabled=MARKER in members
    checks={
        "USB_GADGET":"y","USB_DWC3":"y","USB_CONFIGFS":"y",
        "USB_CONFIGFS_ACM":"y","USB_F_ACM":"y",
        "USB_DWC3_MSM":"y",
    }
    config=get_config(artifact)
    mismatches={key:{"expected":value,"actual":config.get(key,"unknown")}
                for key,value in checks.items()
                if config.get(key)!=value}
    if mismatches:
        raise ValueError("Missing necessary Stage 7 USB Kconfig: "+repr(mismatches))
    indicators={
        "startup_service_exists":True,
        "starts_gadget_script_on_init":("/usr/sbin/aurora-acm" in service and "start)" in service),
        "rootfs_contains_development_enable_marker":enabled,
        "udc_presence_guard":("/sys/class/udc" in gadget and
                              "[ -e \"$1\" ]" in gadget),
        "configfs_mount_attempt":("mount -t configfs" in gadget),
        "acm_function_creation":("functions/acm.GS0" in gadget),
        "udc_bind_attempt":('echo "$UDC" > "$G/UDC"' in gadget),
        "serial_getty":("ttyGS0::respawn:" in init),
        "dev_example_linux_foundation_vendor_id":("0x1d6b" in gadget),
        "dev_example_product_id":("0x0104" in gadget),
    }
    if not all((indicators["starts_gadget_script_on_init"],
                indicators["udc_presence_guard"],indicators["acm_function_creation"],
                indicators["serial_getty"],indicators["udc_bind_attempt"])):
        raise ValueError("Research USB gadget script behavior changed unexpectedly")
    if not enabled:
        raise ValueError("Development USB script marker absent: audit assumptions changed")
    on_boot_attempt = bool(enabled and indicators["starts_gadget_script_on_init"])
    power= json.loads((artifact/"integration-report.json").read_text())
    if power.get("autoload") is not False:
        raise ValueError("Power drivers unexpectedly autoloaded")
    report={
        "stage":15, "static_usb_audit":"PASS",
        "gadget_and_console_findings":indicators,
        "stage7_usb_configs":{key:config[key] for key in checks},
        "gadget_script_would_be_invoked_on_boot":on_boot_attempt,
        "gadget_script_runs_only_if_dev_enable_file_present":True,
        "gadget_registers_only_if_runtime_udc_available":"DESIGNED_GUARD_BUT_UNTESTED",
        "physical_usb_enumeration":"NOT_TESTED",
        "serial_login_security":"NOT_AUDITED_ON_DEVICE",
        "actual_adbd_runtime":"NOT_TESTED",
        "example_usb_ids_assigned_for_public_distribution":False,
        "OEM_recovery_dwc3_phy_integration":"NOT_VERIFIED",
        "boot_kernel_or_gadget_executed":False,
        "module_autoload_changed":False,
        "unresolved": [
            "Development marker in Stage 7 rootfs causes startup service to attempt USB configuration when UDC appears.",
            "Test VID/PID are demonstration values; do not use for a released device.",
            "Unvalidated physical QUSB secure monitor helper, PHY clocks, DWC3 UDC and product DT overlay.",
            "BusyBox ttyGS0 getty accessibility and credential hardening not demonstrated on the watch.",
            "Battery/thermal and charger drivers remain untested and NOT autoloaded; startup safety is not established.",
        ],
        "physical_fastboot_boot_authorization":"BLOCKED"
    }
    if stage14 is not None:
        previous=json.loads(stage14.read_text())
        if previous.get("stage")!=14 or previous.get("physical_fastboot_boot_authorization")!="BLOCKED":
            raise ValueError("Missing verified Stage 14 offline build-path findings")
        report["stage14_linkage_still_unverified_at_runtime"]=True
    return report

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--stage7-artifact",type=pathlib.Path,required=True)
    ap.add_argument("--stage14-report",type=pathlib.Path)
    ap.add_argument("--output",type=pathlib.Path,required=True)
    a=ap.parse_args()
    report=audit(a.stage7_artifact,a.stage14_report)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(report,indent=2)+"\n")
    for name,value in report["gadget_and_console_findings"].items():
        print("USB_AUDIT",name,value)
    print("STAGE15_STATIC_USB_CONSOLE_AUDIT: PASS; PHYSICAL BOOT BLOCKED")

if __name__=="__main__":
    main()
