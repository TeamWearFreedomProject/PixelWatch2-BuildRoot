#!/usr/bin/env python3
"""Extract public V1 runtime libraries/fonts for QEMU; no mounts or OS writes."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

REPO = Path(__file__).resolve().parent.parent


def prepare(work):
    source = work / 'downloads/v1.ext4'
    pin = json.loads((REPO / 'stage27/v1-pins.json').read_text())['assets'][0]
    digest = hashlib.sha256()
    with source.open('rb') as image:
        while data := image.read(1024 * 1024):
            digest.update(data)
    if digest.hexdigest() != pin['sha256'] or source.stat().st_size != pin['bytes']:
        raise ValueError('V1 rootfs input changed')
    sysroot = work / 'v1-runtime'
    marker = sysroot / '.aurora-runtime.json'
    if marker.exists():
        if json.loads(marker.read_text())['rootfs_sha256'] != pin['sha256']:
            raise ValueError('Existing runtime input mismatch')
        return sysroot
    for name in ('usr', 'usr/share', 'etc', 'var/cache/fontconfig', 'tmp', 'var/tmp'):
        (sysroot / name).mkdir(parents=True, exist_ok=True)
    logs = []
    for directory, destination in (
        ('/usr/lib', sysroot / 'usr'), ('/usr/share/fonts', sysroot / 'usr/share'),
        ('/usr/share/fontconfig', sysroot / 'usr/share'), ('/etc/fonts', sysroot / 'etc')
    ):
        result = subprocess.run(['debugfs', '-R', 'rdump ' + directory + ' ' + str(destination), str(source)],
                                capture_output=True, check=True, timeout=180)
        logs.append(result.stderr.decode(errors='replace'))
    # V1 /lib is the relative symlink usr/lib (verified in Stage27).
    stat = subprocess.run(['debugfs', '-R', 'stat /lib', str(source)], check=True,
                          capture_output=True, text=True).stdout
    if 'Fast link dest: "usr/lib"' not in stat:
        raise ValueError('Pinned V1 /lib layout changed')
    (sysroot / 'lib').symlink_to('usr/lib')
    rewrites = 0
    for path in sysroot.rglob('*'):
        if path.is_symlink():
            target = path.readlink()
            if target.is_absolute():
                relative = os.path.relpath(sysroot / str(target).lstrip('/'), path.parent)
                path.unlink()
                path.symlink_to(relative)
                rewrites += 1
    for name in ('libQt6Core.so.6', 'libQt6Gui.so.6', 'libQt6Qml.so.6', 'libQt6Quick.so.6', 'libc.so.6'):
        path = sysroot / 'usr/lib' / name
        with path.open('rb') as library:
            if library.read(6) != b'\x7fELF\x01\x01':
                raise ValueError('Expected ARM32 runtime library: ' + name)
    marker.write_text(json.dumps({'rootfs_sha256': pin['sha256'], 'images_mounted': False,
                                 'extracted_paths': ['/usr/lib', '/usr/share/fonts', '/usr/share/fontconfig', '/etc/fonts'],
                                 'absolute_symlinks_made_relative': rewrites,
                                 'original_image_modified': False}, indent=2) + '\n')
    (work / 'v1-extract.log').write_text('\n'.join(logs))
    print('Verified V1 ARM32 runtime libraries/fonts extracted; no image mounted', flush=True)
    return sysroot


if __name__ == '__main__':
    prepare(Path(sys.argv[1]).resolve())
