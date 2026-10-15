#!/usr/bin/env python3
"""Offline Stage 8 integrity check. It NEVER authorizes a hardware boot.

Produces separate format_ok and hardware_gate fields so that CI success
cannot be mistaken for approval to run an image on a physical watch.
"""
import argparse
import gzip
import hashlib
import json
import pathlib
import struct

EXPECTED = {
    'gvotable.ko', 'logbuffer.ko', 'qpnp-smblite-main.ko',
    'qti-qbg-main.ko', 'google-bms.ko', 'google-battery.ko',
    'google-charger.ko', 'sw5100_bms.ko'
}
REQUIRED = (
    'boot.img', 'rootfs.cpio.gz', 'kernel.config', 'Module.symvers',
    'abi-report.json', 'integration-report.json', 'SOURCES.txt',
    'README-FIRST-DO-NOT-BOOT.txt', 'SHA256SUMS'
)
BLOCKERS = [
    ('firmware', 'Exact on-watch EOS build/bootloader, active slot, and boot/vendor_boot/dtbo provenance are not verified together'),
    ('device_tree', 'No independently reviewed matching vendor_boot DTB and dtbo overlay evidence for this kernel'),
    ('runtime_power', 'Battery gauge, charge limit, watchdog, PMIC and thermal controls have no device-side validation; eight power modules are not autoloaded'),
    ('usb_shell', 'QUSB SCM/PHY, UDC enumeration and ttyGS0 login have not been demonstrated on this Linux kernel'),
    ('fallback', 'Non-destructive recovery path, stock partition backups and hard reboot behavior have not been independently verified for the current firmware'),
    ('secure_boot', 'Bootloader acceptance and firmware/AVB/vendor ramdisk interaction are unknown'),
]

def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def check_checksums(directory):
    seen = set()
    for line in (directory / 'SHA256SUMS').read_text().splitlines():
        pieces = line.split(maxsplit=1)
        if len(pieces) != 2 or len(pieces[0]) != 64:
            raise ValueError('Invalid SHA256SUMS record')
        filename = pieces[1].lstrip('*')
        if '/' in filename or filename in seen:
            raise ValueError('Duplicate or unsafe SHA256 entry')
        seen.add(filename)
        if sha256(directory / filename) != pieces[0]:
            raise ValueError('SHA256 mismatch: ' + filename)
    for name in ('boot.img', 'rootfs.cpio.gz', 'kernel.config','Module.symvers'):
        if name not in seen:
            raise ValueError('Missing signed-off Stage 7 checksum: ' + name)
    return sorted(seen)

def cpio_members(data):
    pos = 0
    output = {}
    for _ in range(100000):
        if pos + 110 > len(data):
            raise ValueError('Truncated CPIO header')
        h = data[pos:pos+110]
        if h[:6] not in (b'070701', b'070702'):
            raise ValueError('Unsupported CPIO header')
        fields = [int(h[6+i*8:14+i*8], 16) for i in range(13)]
        size, nlen = fields[6], fields[11]
        pos += 110
        if not (1 <= nlen <= 4096) or pos+nlen > len(data):
            raise ValueError('Bad CPIO filename size')
        name_bytes = data[pos:pos+nlen]
        if not name_bytes.endswith(b'\x00'):
            raise ValueError('Invalid CPIO name termination')
        name = name_bytes[:-1].decode('utf-8').removeprefix('./')
        pos = (pos+nlen+3) & ~3
        if pos+size > len(data):
            raise ValueError('Truncated CPIO body')
        body = data[pos:pos+size]
        pos = (pos+size+3) & ~3
        if h[:6] == b'070702' and sum(body) & 0xffffffff != fields[12]:
            raise ValueError('Invalid CPIO CRC')
        if name == 'TRAILER!!!':
            return output
        if name in output or name.startswith('/') or '..' in pathlib.PurePosixPath(name).parts:
            raise ValueError('CPIO duplicate or unsafe name')
        output[name] = body
    raise ValueError('Missing CPIO trailer')

def audit(directory):
    for name in REQUIRED:
        if not (directory / name).is_file():
            raise ValueError('Missing Stage 7 artifact: ' + name)
    checks = check_checksums(directory)
    boot = (directory / 'boot.img').read_bytes()
    if len(boot) > 67108864 or boot[:8] != b'ANDROID!':
        raise ValueError('Invalid Android boot image magic or over 64 MiB CI limit')
    kernel_size, ramdisk_size, _os_version, header_size = struct.unpack_from('<4I', boot, 8)
    header_version = struct.unpack_from('<I', boot, 40)[0]
    if header_version != 4 or header_size != 1584 or ramdisk_size != 0:
        raise ValueError('Unexpected Android v4 header or ramdisk')
    kernel = boot[4096:4096+kernel_size]
    if kernel_size == 0 or len(kernel) != kernel_size:
        raise ValueError('Truncated kernel payload')
    if struct.unpack_from('<I', kernel, 56)[0] != 0x644D5241:
        raise ValueError('No AArch64 Image magic')
    config = (directory / 'kernel.config').read_text()
    for setting in ('CONFIG_ARM64=y', 'CONFIG_COMPAT=y',
                    'CONFIG_MODULES=y', 'CONFIG_MODVERSIONS=y',
                    '# CONFIG_SOUND is not set',
                    '# CONFIG_TRIM_UNUSED_KSYMS is not set',
                    'CONFIG_USB_CONFIGFS_ACM=y'):
        if setting not in config.splitlines():
            raise ValueError('Stage 7 kernel config missing: ' + setting)
    members = cpio_members(gzip.decompress((directory / 'rootfs.cpio.gz').read_bytes()))
    if 'etc/inittab' not in members or b'ttyGS0' not in members['etc/inittab']:
        raise ValueError('Stage 5 USB serial getty missing')
    if 'usr/sbin/aurora-acm' not in members or 'usr/bin/adbd' not in members:
        raise ValueError('Stage 5 shell research binaries missing')
    module_paths = {name: body for name, body in members.items() if name.endswith('.ko')}
    actual = {pathlib.PurePosixPath(name).name for name in module_paths}
    if actual != EXPECTED or len(module_paths) != len(EXPECTED):
        raise ValueError('Power modules mismatch: ' + repr(sorted(actual)))
    for name, data in module_paths.items():
        if not data.startswith(b'\x7fELF\x02\x01') or int.from_bytes(data[18:20], 'little') != 183:
            raise ValueError('Non-AArch64 .ko stored in rootfs: ' + name)
    abi = json.loads((directory / 'abi-report.json').read_text())
    integration = json.loads((directory / 'integration-report.json').read_text())
    if abi.get('failed_modules') != [] or len(abi.get('module_checks', {})) != len(EXPECTED):
        raise ValueError('ABI report is incomplete or reports mismatches')
    if integration.get('autoload') is not False or integration.get('status') != 'OFFLINE_STAGE7_ONLY':
        raise ValueError('Unexpected power module autoload or integration report')
    if integration.get('rootfs_sha256') != sha256(directory / 'rootfs.cpio.gz'):
        raise ValueError('Rootfs changed after integration report')
    if len((directory / 'Module.symvers').read_text().splitlines()) < 1000:
        raise ValueError('Kernel export table unexpectedly pruned')
    if 'DO NOT BOOT' not in (directory / 'README-FIRST-DO-NOT-BOOT.txt').read_text():
        raise ValueError('Safety marker is absent')
    return {
        'stage': 8, 'format_and_static_integrity': 'PASS',
        'physical_boot_authorization': 'BLOCKED',
        'boot_image_bytes': len(boot), 'android_boot_header': header_version,
        'kernel_payload_bytes': kernel_size,
        'stored_power_modules': sorted(EXPECTED),
        'sha256_verified': checks, 'module_auto_load': False,
        'rootfs_sha256': sha256(directory / 'rootfs.cpio.gz'),
        'vendor_boot_dtb_verification': 'NOT PROVIDED',
        'actual_partition_size_verified': False,
        'device_ever_tested_by_this_ci': False,
        'blockers': [{'id': key, 'reason': reason} for key, reason in BLOCKERS],
        'note': 'No physical boot permission; a green CI means artifact checks only.'
    }

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', required=True, type=pathlib.Path)
    parser.add_argument('--output', required=True, type=pathlib.Path)
    args = parser.parse_args()
    report = audit(args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
    print('Stage 8 offline static audit PASS; hardware readiness BLOCKED.')
    for b in report['blockers']:
        print('BLOCKER '+b['id']+': '+b['reason'])

if __name__ == '__main__':
    main()
