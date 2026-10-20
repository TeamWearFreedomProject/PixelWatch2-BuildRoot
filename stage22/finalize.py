#!/usr/bin/env python3
"""Verify Stage 22's linked payload and package its temporary-boot candidate."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from stage20.package_boot import CMDLINE, package
from stage20.verify_embedded import verify


def main():
    out = ROOT / 'stage22-artifacts'
    build = ROOT / 'stage22-work/out'
    pins = json.loads((ROOT / 'stage22/pins.json').read_text())
    rootfs = out / 'rootfs.cpio.gz'
    assert hashlib.sha256(rootfs.read_bytes()).hexdigest() == pins['stage20_files']['rootfs.cpio.gz']
    embedded = verify(build / 'vmlinux', rootfs)
    embedded.update(stage=22, rootfs_preserved_from_stage20=True)
    (out / 'embedded-rootfs.json').write_text(json.dumps(embedded, indent=2) + '\n')
    symbols = subprocess.check_output(['aarch64-linux-gnu-nm', '--defined-only', '--format=posix', str(build / 'vmlinux')], text=True)
    names = {line.split()[0] for line in symbols.splitlines() if line}
    for name in ('qnoc_probe', 'extcon_usb_shim_probe', 'extcon_usb_shim', 'extcon_usb_shim_init'):
        assert name in names, name
    calls = [n for n in names if n.startswith('__initcall') and 'extcon_usb_shim_init' in n]
    assert len(calls) == 1
    (out / 'usb-shim-link.json').write_text(json.dumps({'stage':22, 'linked':True, 'initcalls':calls,
                                                     'new_kernel_hardware_test':'NOT_PERFORMED'}, indent=2) + '\n')
    image = build / 'arch/arm64/boot/Image'
    data = package((ROOT / 'stage22-input/stage20/boot-stage20.img').read_bytes(), image.read_bytes())
    (out / 'boot-stage22.img').write_bytes(data)
    report = {'stage':22, 'project_commit':os.environ.get('PROJECT_COMMIT', 'UNKNOWN'),
              'boot_header':4, 'boot_bytes':len(data),
              'boot_sha256':hashlib.sha256(data).hexdigest(),
              'kernel_sha256':hashlib.sha256(image.read_bytes()).hexdigest(),
              'cmdline':CMDLINE.decode(), 'userspace':'unchanged Stage 20 ARM32 initramfs',
              'userspace_banner':'AURORA_STAGE20_USB_SHELL', 'kernel_build':22,
              'software_deadline_seconds':90, 'kasan_retained':True,
              'signature':'UNSIGNED_RESEARCH_IMAGE', 'new_kernel_hardware_test':'NOT_PERFORMED'}
    (out / 'boot-report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
