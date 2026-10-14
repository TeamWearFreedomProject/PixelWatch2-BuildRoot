#!/usr/bin/env python3
"""Inspect Android boot header v4 without using a device.

This validates only basic format and embedded kernel bytes.
It does NOT establish hardware compatibility, image authentication or bootability.
"""
import argparse
import pathlib
import struct


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--boot", type=pathlib.Path, required=True)
    parser.add_argument("--kernel", type=pathlib.Path, required=True)
    parser.add_argument("--max-bytes", type=int, default=67108864)
    args = parser.parse_args()

    image = args.boot.read_bytes()
    kernel = args.kernel.read_bytes()
    if len(image) > args.max_bytes:
        raise SystemExit(f"ERROR: boot image exceeds {args.max_bytes} bytes")
    if image[:8] != b"ANDROID!":
        raise SystemExit("ERROR: not an Android boot image")
    kernel_size, ramdisk_size, os_ver, header_size = struct.unpack_from("<4I", image, 8)
    version = struct.unpack_from("<I", image, 40)[0]
    if version != 4:
        raise SystemExit(f"ERROR: header v{version} is not v4")
    if not (1580 <= header_size <= 4096):
        raise SystemExit(f"ERROR: invalid header size {header_size}")
    if kernel_size != len(kernel) or kernel_size == 0:
        raise SystemExit("ERROR: embedded kernel size mismatch")
    if ramdisk_size != 0:
        raise SystemExit("ERROR: unexpected Android boot ramdisk (expected built-in initramfs)")
    if len(kernel) < 64 or struct.unpack_from("<I", kernel, 56)[0] != 0x644D5241:
        raise SystemExit("ERROR: kernel is not an uncompressed ARM64 Image")
    page = 4096
    if image[page:page + len(kernel)] != kernel:
        raise SystemExit("ERROR: boot.img kernel payload differs from compiled Image")
    print(f"ANDROID! header={version} header_size={header_size} kernel={kernel_size} bytes")
    print(f"ARM64 Image header confirmed; boot ramdisk={ramdisk_size}; image={len(image)} bytes")
    print("UNVERIFIED: kernel/runtime, vendor partitions, DTB/DTBO and hardware boot not tested")


if __name__ == "__main__":
    main()
