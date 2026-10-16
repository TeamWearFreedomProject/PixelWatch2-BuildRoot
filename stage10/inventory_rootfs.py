#!/usr/bin/env python3
"""Static Stage 10 inventory for an existing Stage 7 research initramfs.

Never accesses a physical device, mounts partitions, or authorizes boot.
"""
import argparse
import gzip
import hashlib
import json
import pathlib
import stat
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "stage7"))
from pack_modules import read_records

MODULES = {
    "gvotable.ko", "logbuffer.ko", "qpnp-smblite-main.ko",
    "qti-qbg-main.ko", "google-bms.ko", "google-battery.ko",
    "google-charger.ko", "sw5100_bms.ko"
}

def audit(root):
    cpio = root / "rootfs.cpio.gz"
    archive = cpio.read_bytes()
    members = read_records(gzip.decompress(archive))
    lookup = {r[2].removeprefix("./"): r for r in members}
    if len(lookup) != len(members):
        raise ValueError("Duplicate member names in newc CPIO")
    required = ("init", "bin/busybox", "usr/bin/adbd",
                "usr/sbin/aurora-acm", "etc/inittab")
    for path in required:
        if path not in lookup:
            raise ValueError("Missing ARM32 rootfs file: "+path)
    for _, vals, name, data in members:
        normalized = pathlib.PurePosixPath(name.removeprefix("./"))
        if normalized.is_absolute() or ".." in normalized.parts:
            raise ValueError("Unsafe archive path")
        if stat.S_ISLNK(vals[1]):
            link = data.decode("utf-8")
            if "\x00" in link or not link:
                raise ValueError("Invalid symlink in CPIO")
    if b"ttyGS0::" not in lookup["etc/inittab"][3]:
        raise ValueError("USB serial getty not configured")
    elf32 = []
    for name in ("bin/busybox", "usr/bin/adbd"):
        data = lookup[name][3]
        if not (len(data) >= 20 and data[:6] == b"\x7fELF\x01\x01"
                and int.from_bytes(data[18:20], "little") == 40):
            raise ValueError("Not ARM32 little-endian ELF: "+name)
        elf32.append(name)
    found = {pathlib.PurePosixPath(name).name for name in lookup if name.endswith(".ko")}
    if found != MODULES:
        raise ValueError("Power .ko archive contents changed: "+repr(sorted(found)))
    integration = json.loads((root / "integration-report.json").read_text())
    abi = json.loads((root / "abi-report.json").read_text())
    if integration.get("autoload") is not False:
        raise ValueError("Stage 7 did not disable module autoload")
    if abi.get("failed_modules") != []:
        raise ValueError("Stage 7 reported ABI validation failures")
    config = (root / "kernel.config").read_text()
    if "# CONFIG_SOUND is not set" not in config.splitlines():
        raise ValueError("Expected Stage 7 config SOUND=n")
    report = {
        "stage": 10, "status": "STATIC_ROOTFS_INVENTORY_PASS",
        "cpio_sha256": hashlib.sha256(archive).hexdigest(),
        "cpio_members": len(members),
        "arm32_executables": elf32,
        "serial_getty_profile": True,
        "power_module_count": len(found),
        "power_modules_stored_not_loaded": True,
        "qemu_shell_test": "SEPARATE_ACTIONS_STEP",
        "kernel_or_watch_booted": False,
        "hardware_boot_authorization": "BLOCKED",
        "known_unresolved": [
            "Stage 7 has no physical device test",
            "Vendor boot DTB/DTBO, power and thermal safety not verified",
            "USB CDC ACM enumeration and QUSB SCM not verified",
            "QEMU ARM32 user mode cannot emulate Pixel Watch 2 SoC or PMIC",
        ],
    }
    return report

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--artifact",type=pathlib.Path,required=True)
    parser.add_argument("--output",type=pathlib.Path,required=True)
    args=parser.parse_args()
    report=audit(args.artifact)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2)+"\n")
    print("Stage 10: ARM32 rootfs inventory PASS, real boot BLOCKED.")
    print("Rootfs member count:",report["cpio_members"])

if __name__=="__main__":
    main()
