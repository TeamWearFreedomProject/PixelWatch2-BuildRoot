#!/usr/bin/env python3
"""Offline-only Stage 3 audit of a pinned Stage 2 GitHub Actions artifact.

Exit nonzero for corrupted/invalid artifacts. Hardware readiness blockers
are *reported*, not treated as image format failures. Never flashes devices.
"""
import argparse
import gzip
import hashlib
import json
import pathlib
import struct


def entries_from_cpio(data):
    """Read names/content from a cpio newc archive without elevated privileges."""
    found = {}
    offset = 0
    for _ in range(150000):
        if offset + 110 > len(data):
            raise ValueError("Truncated CPIO entry header")
        head = data[offset : offset + 110]
        if head[:6] not in (b"070701", b"070702"):
            raise ValueError(f"Unexpected CPIO format at byte {offset}")
        size = int(head[54:62], 16)
        name_size = int(head[94:102], 16)
        if not (1 <= name_size <= 4096):
            raise ValueError("Invalid CPIO filename length")
        offset += 110
        if offset + name_size > len(data):
            raise ValueError("Truncated CPIO entry name")
        name = data[offset : offset + name_size - 1].decode("utf-8", "replace")
        offset = (offset + name_size + 3) & ~3
        if offset + size > len(data):
            raise ValueError("Truncated CPIO entry data")
        blob = data[offset : offset + size]
        offset = (offset + size + 3) & ~3
        if name == "TRAILER!!!":
            return found
        found[name.removeprefix("./").lstrip("/")] = blob
    raise ValueError("Too many CPIO entries / missing TRAILER!!!")


def main():
    arg = argparse.ArgumentParser()
    arg.add_argument("--artifact-dir", type=pathlib.Path, required=True)
    arg.add_argument("--output-dir", type=pathlib.Path, required=True)
    args = arg.parse_args()
    src, out = args.artifact_dir, args.output_dir
    out.mkdir(parents=True, exist_ok=True)
    expected_names = ("boot.img", "rootfs.cpio.gz", "kernel.config")
    for file in (*expected_names, "SHA256SUMS", "SOURCES.txt"):
        if not (src / file).is_file():
            raise SystemExit(f"Missing required artifact file: {file}")
    checksums = {}
    for line in (src / "SHA256SUMS").read_text().splitlines():
        parts = line.split()
        if len(parts) != 2:
            raise SystemExit("Invalid SHA256SUMS line")
        checksums[pathlib.Path(parts[1].lstrip("*")).name] = parts[0]
    for file in expected_names:
        actual = hashlib.sha256((src / file).read_bytes()).hexdigest()
        if checksums.get(file) != actual:
            raise SystemExit(f"SHA256 mismatch: {file}")

    boot = (src / "boot.img").read_bytes()
    if not (0 < len(boot) <= 67108864):
        raise SystemExit("boot.img exceeds 64 MiB or empty")
    if boot[:8] != b"ANDROID!":
        raise SystemExit("Android boot magic missing")
    kernel_size, ramdisk_size, _, header_size = struct.unpack_from("<4I", boot, 8)
    header_version = struct.unpack_from("<I", boot, 40)[0]
    if header_version != 4 or header_size != 1584 or ramdisk_size != 0:
        raise SystemExit("Unexpected boot header, size, or ramdisk")
    kernel = boot[4096:4096 + kernel_size]
    if len(kernel) != kernel_size or struct.unpack_from("<I", kernel, 56)[0] != 0x644D5241:
        raise SystemExit("Invalid or truncated ARM64 uncompressed Image")

    config = (src / "kernel.config").read_text()
    rootfs = entries_from_cpio(gzip.decompress((src / "rootfs.cpio.gz").read_bytes()))
    if "init" not in rootfs or "bin/busybox" not in rootfs:
        raise SystemExit("Rootfs lacks /init or /bin/busybox")
    busybox = rootfs["bin/busybox"]
    if busybox[:5] != b"\x7fELF\x01" or struct.unpack_from("<H", busybox, 18)[0] != 40:
        raise SystemExit("BusyBox is not ARM32 ELF")
    if "CONFIG_ARM64=y" not in config or "CONFIG_COMPAT=y" not in config:
        raise SystemExit("Wrong kernel architecture or missing AArch32 compat")

    blockers = []
    power = ["QCOM_POWER_SUPPLY", "QPNP_SMBLITE", "QTI_QBG"]
    for sym in power:
        if f"CONFIG_{sym}=y" not in config and f"CONFIG_{sym}=m" not in config:
            blockers.append(f"Battery/power driver {sym} unavailable (out-of-tree integration required)")
    if not any(p in rootfs for p in ("usr/bin/adbd", "bin/adbd", "sbin/adbd")):
        blockers.append("adbd binary absent; USB ADB unavailable")
    if "CONFIG_SOUND=y" in config or "CONFIG_SND=y" in config:
        blockers.append("Sound subsystem enabled; speaker silence NOT enforced")
    if "CONFIG_USB_CONFIGFS=y" not in config and "CONFIG_USB_CONFIGFS=m" not in config:
        blockers.append("USB ConfigFS gadget availability not established")
    sources = (src / "SOURCES.txt").read_text()
    if "experimental QUSB SCM helper" in sources:
        blockers.append("QUSB secure-monitor helper is experimental and unverified")
    blockers.extend([
        "Vendor module loading, DTB/DTBO, UDC, screen and touch not verified on hardware",
        "Bootloader acceptance and battery/charging safety not validated",
    ])
    report = {
        "result": "STRUCTURE_VERIFIED_HARDWARE_BLOCKED",
        "source_run_id": "38520538421",
        "boot_header": 4,
        "boot_bytes": len(boot),
        "kernel_bytes": kernel_size,
        "userland": "ARM32 BusyBox/musl",
        "ramdisk_in_boot_header": ramdisk_size,
        "initramfs_entries": len(rootfs),
        "adbd_present": any(p in rootfs for p in ("usr/bin/adbd", "bin/adbd", "sbin/adbd")),
        "sound_subsystem_enabled": "CONFIG_SOUND=y" in config or "CONFIG_SND=y" in config,
        "boot_ready": False,
        "flash_ready": False,
        "blockers": blockers,
    }
    (out / "audit.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    text = [
        "# Aurora Stage 3 — offline readiness audit",
        "",
        "**STRUCTURE VERIFIED; HARDWARE BOOT BLOCKED — DO NOT FLASH OR BOOT.**",
        "",
        f"- Source Actions run: {report['source_run_id']}",
        f"- Android header version: {header_version}",
        f"- boot.img: {len(boot):,} bytes, kernel: {kernel_size:,} bytes",
        f"- Rootfs: ARM32 BusyBox; {len(rootfs)} CPIO entries",
        "- Integrity: SHA256 PASS; ARM64 Image header PASS",
        "",
        "## Unresolved blockers",
    ] + [f"- {x}" for x in blockers] + [
        "",
        "Passing this check is NOT permission to use the image on the watch.",
        "No partition or device was accessed by this CI.",
    ]
    (out / "README.md").write_text("\n".join(text) + "\n")
    print("\n".join(text))


if __name__ == "__main__":
    main()
