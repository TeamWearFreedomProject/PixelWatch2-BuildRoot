#!/usr/bin/env python3
"""Reuse the verified research v4 header with a newly compiled Image.

The template is Stage 7's public research boot.img, not OEM firmware.
The result is an unsigned candidate; bootloader acceptance is untested.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct

CMDLINE = b"rdinit=/init panic=10 fw_devlink=permissive"


def package(template, kernel):
    if len(template) < 4096 or template[:8] != b"ANDROID!":
        raise ValueError("Not an Android boot template")
    old_kernel, ramdisk, _, header = struct.unpack_from("<4I", template, 8)
    if (header, struct.unpack_from("<I", template, 40)[0], ramdisk,
        struct.unpack_from("<I", template, 1580)[0]) != (1584, 4, 0, 0):
        raise ValueError("Expected unsigned v4 research header with no Android ramdisk")
    if old_kernel == 0 or 4096 + old_kernel > len(template):
        raise ValueError("Template kernel out of range")
    if len(kernel) < 64 or kernel[56:60] != b"ARM\x64":
        raise ValueError("Expected uncompressed ARM64 Image")
    page = bytearray(template[:4096])
    struct.pack_into("<I", page, 8, len(kernel))
    page[44:1580] = CMDLINE + bytes(1536 - len(CMDLINE))
    result = bytes(page) + kernel + bytes(-len(kernel) % 4096)
    if len(result) > 67108864:
        raise ValueError("Boot candidate exceeds historical 64-MiB boot partition capacity")
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for arg in ("template", "kernel", "output", "report"):
        p.add_argument("--" + arg, type=Path, required=True)
    a = p.parse_args()
    data = package(a.template.read_bytes(), a.kernel.read_bytes())
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_bytes(data)
    r = {"stage": 20, "boot_header": 4, "boot_bytes": len(data),
         "boot_sha256": hashlib.sha256(data).hexdigest(), "kernel_sha256": hashlib.sha256(a.kernel.read_bytes()).hexdigest(),
         "cmdline": CMDLINE.decode(), "ramdisk": "ARM32 initramfs built into ARM64 Image",
         "signature": "UNSIGNED_RESEARCH_IMAGE", "watch_bootloader_acceptance": "NOT_TESTED"}
    a.report.write_text(json.dumps(r, indent=2) + "\n")
    print(json.dumps(r, indent=2))


if __name__ == "__main__":
    main()
