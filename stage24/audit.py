#!/usr/bin/env python3
"""Fail a build on malformed boot images, wrong userspace ABI, or incomplete rootfs."""
import argparse
import json
from pathlib import Path
import re
import struct
import subprocess


def boot_image(path, kernel_expected, capacity):
    size = path.stat().st_size
    if size > capacity or size < 4096:
        raise ValueError('Boot image outside partition bounds: ' + path.name)
    with path.open('rb') as f:
        header = f.read(1584)
        if header[:8] != b'ANDROID!':
            raise ValueError('Missing Android boot magic')
        kernel, ramdisk = struct.unpack_from('<II', header, 8)
        header_size = struct.unpack_from('<I', header, 20)[0]
        version = struct.unpack_from('<I', header, 40)[0]
        if version != 4 or header_size != 1584:
            raise ValueError('Expected boot header v4')
        end = 4096 + ((kernel + 4095) // 4096) * 4096 + ramdisk
        if end > size:
            raise ValueError('Truncated Android boot payload')
        if kernel_expected:
            if kernel < 64 or ramdisk != 0:
                raise ValueError('Expected kernel-only boot.img')
            f.seek(4096)
            prefix = f.read(64)
            if prefix[56:60] != b'ARM\x64':
                raise ValueError('Expected ARM64 Linux Image')
        elif kernel != 0 or ramdisk == 0:
            raise ValueError('Expected ramdisk-only init_boot.img')
    return {'bytes': size, 'header_version': version, 'kernel_bytes': kernel,
            'ramdisk_bytes': ramdisk}


def config_values(text):
    return dict(re.findall(r'^CONFIG_([A-Z0-9_]+)=(.*)$', text, re.M))


def audit_boot(directory):
    pins = json.loads((directory / 'sources.json').read_text())
    target = pins['target']
    cfg = config_values((directory / 'kernel.config').read_text())
    if cfg.get('ARM64') != 'y' or cfg.get('COMPAT') != 'y':
        raise ValueError('Kernel must support ARM64 and ARM32 userspace')
    return {'kind': 'upstream-ut-adaptation',
            'boot': boot_image(directory / 'boot.img', True, target['boot_partition_size']),
            'init_boot': boot_image(directory / 'init_boot.img', False, target['init_boot_partition_size']),
            'usb_config': {k: cfg.get(k, 'n') for k in (
                'USB_GADGET', 'USB_DWC3', 'USB_DWC3_MSM', 'USB_CONFIGFS',
                'USB_CONFIGFS_ACM', 'USB_CONFIGFS_RNDIS', 'EXTCON_GOOGLE_USB_SHIM')},
            'sound_config': cfg.get('SOUND', 'n'),
            'hardware_boot_tested': False, 'usb_enumeration_tested': False,
            'speaker_disabled': False, 'automatic_fastboot_timer': False}


def debugfs(image, command):
    r = subprocess.run(['debugfs', '-R', command, str(image)],
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    if b'File not found' in r.stderr or b'not found by ext2_lookup' in r.stderr:
        raise ValueError('Missing file in rootfs: ' + command)
    return r.stdout


def arm32(data):
    if (len(data) < 20 or data[:6] != b'\x7fELF\x01\x01'
            or struct.unpack_from('<H', data, 18)[0] != 40):
        raise ValueError('Expected little-endian ARM32 ELF executable')


def audit_rootfs(image):
    with image.open('rb') as f:
        f.seek(1024)
        sb = f.read(1024)
    if sb[56:58] != b'\x53\xef':
        raise ValueError('Expected raw ext4 filesystem')
    blocks = struct.unpack_from('<I', sb, 4)[0]
    block_size = 1024 << struct.unpack_from('<I', sb, 24)[0]
    if blocks * block_size > image.stat().st_size:
        raise ValueError('Truncated ext4 filesystem')
    release = debugfs(image, 'cat /usr/lib/os-release').decode()
    if 'VERSION_ID="20.04"' not in release:
        raise ValueError('Expected explicitly selected Focal rootfs')
    for name in ['apt', 'dpkg']:
        arm32(debugfs(image, 'cat /usr/bin/' + name))
    for name in ['/.writable_image', '/var/lib/lxc/android/android-rootfs.img',
                 '/opt/halium-overlay/etc/deviceinfo/devices/halium.yaml']:
        if b'Inode:' not in debugfs(image, 'stat ' + name):
            raise ValueError('Incomplete rootfs: ' + name)
    return {'kind': 'ubuntu-touch-focal-rw-host', 'bytes': image.stat().st_size,
            'filesystem': 'ext4', 'block_size': block_size,
            'userspace': 'armhf', 'apt_elf': 'ELF32 ARM', 'dpkg_elf': 'ELF32 ARM',
            'writable_image_marker': True, 'android_container_image_present': True,
            'native_apt_runtime_tested': False, 'hardware_boot_tested': False,
            'usb_enumeration_tested': False, 'speaker_disabled': False,
            'gui': 'upstream Lomiri retained', 'automatic_fastboot_timer': False}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('kind', choices=['boot', 'rootfs'])
    ap.add_argument('input', type=Path)
    ap.add_argument('--output', required=True, type=Path)
    args = ap.parse_args()
    report = audit_boot(args.input) if args.kind == 'boot' else audit_rootfs(args.input)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
