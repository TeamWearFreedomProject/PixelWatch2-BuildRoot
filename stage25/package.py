#!/usr/bin/env python3
"""Preserve the Stage 24 kernel/initrd and append an exclusive USB diagnostic."""
import argparse
import ctypes
import ctypes.util
import hashlib
import json
from pathlib import Path
import stat
import struct
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from stage7.pack_modules import add, encode, fresh, read_records

HERE = Path(__file__).resolve().parent
CAPACITY = 67108864
CMDLINE = b'rdinit=/aurora-stage25-init panic=10'
LEGACY = 0x184C2102


def sha(data):
    return hashlib.sha256(data).hexdigest()


def legacy_streams(src):
    """Bounded decoding of concatenated legacy LZ4 streams; no filesystem writes."""
    lib = ctypes.CDLL(ctypes.util.find_library('lz4') or 'liblz4.so.1')
    lib.LZ4_decompress_safe.argtypes = [ctypes.c_char_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
    lib.LZ4_decompress_safe.restype = ctypes.c_int
    pos, total, streams = 0, 0, []
    while pos < len(src):
        if len(src)-pos < 4 or struct.unpack_from('<I', src, pos)[0] != LEGACY:
            raise ValueError('Expected legacy LZ4 magic')
        pos += 4
        data = bytearray()
        while pos < len(src):
            if len(src)-pos < 4:
                raise ValueError('Truncated legacy LZ4 block length')
            n = struct.unpack_from('<I', src, pos)[0]
            if n == LEGACY:
                break
            pos += 4
            if n == 0:
                break
            if n > 8421520 or pos+n > len(src):
                raise ValueError('Invalid/truncated legacy LZ4 block')
            buf = ctypes.create_string_buffer(8*1024*1024)
            used = lib.LZ4_decompress_safe(src[pos:pos+n], buf, n, len(buf))
            if used <= 0:
                raise ValueError('Corrupt legacy LZ4 block')
            total += used
            if total > 64*1024*1024:
                raise ValueError('Initramfs exceeds decompression limit')
            data.extend(buf.raw[:used])
            pos += n
        if not data:
            raise ValueError('Empty legacy LZ4 stream')
        streams.append(bytes(data))
    return streams


def image_parts(data):
    if len(data) < 4096 or data[:8] != b'ANDROID!':
        raise ValueError('Missing Android boot header')
    k, r = struct.unpack_from('<II', data, 8)
    if struct.unpack_from('<I', data, 20)[0] != 1584 or struct.unpack_from('<I', data, 40)[0] != 4:
        raise ValueError('Expected Android boot v4')
    start = 4096 + ((k+4095)//4096)*4096
    if start+r > len(data):
        raise ValueError('Truncated boot payload')
    return data[4096:4096+k], data[start:start+r]


def static_arm64(data):
    if len(data) < 64 or data[:6] != b'\x7fELF\x02\x01' or struct.unpack_from('<HH', data, 16) != (2, 183):
        raise ValueError('Recovery helper must be static ARM64 ET_EXEC')
    off = struct.unpack_from('<Q', data, 32)[0]
    size, count = struct.unpack_from('<HH', data, 54)
    if not count or size != 56 or off+count*size > len(data):
        raise ValueError('Invalid ELF program headers')
    if any(struct.unpack_from('<I', data, off+i*size)[0] == 3 for i in range(count)):
        raise ValueError('Recovery helper must not require an ELF interpreter')


def make_overlay(helper):
    static_arm64(helper)
    records, registry, ino = [], {}, 900000
    for p in sorted((HERE/'overlay').rglob('*')):
        if p.is_file():
            name = p.relative_to(HERE/'overlay').as_posix()
            mode = 0o644 if name.startswith('etc/') else 0o755
            ino = add(records, registry, name, p.read_bytes(), stat.S_IFREG | mode, ino)
    ino = add(records, registry, 'init', (HERE/'overlay/aurora-stage25-init').read_bytes(), stat.S_IFREG | 0o755, ino)
    ino = add(records, registry, 'usr/sbin/aurora-return', helper, stat.S_IFREG | 0o755, ino)
    # Async children redirect stdin before devtmpfs is mounted.
    ino = add(records, registry, 'dev/null', b'', stat.S_IFCHR | 0o666, ino)
    registry['dev/null'][1][9:11] = [1, 3]
    return b''.join(encode(r) for r in records) + encode(fresh('TRAILER!!!', b'', 0, ino+1))


def combined_boot(template, kernel, ramdisk):
    if len(kernel) < 64 or kernel[56:60] != b'ARM\x64':
        raise ValueError('Expected uncompressed ARM64 Linux Image')
    image_parts(template)
    page = bytearray(template[:4096])
    struct.pack_into('<II', page, 8, len(kernel), len(ramdisk))
    struct.pack_into('<I', page, 1580, 0)  # Unsigned temporary boot; no stale signature.
    page[44:1580] = CMDLINE + bytes(1536-len(CMDLINE))
    result = bytes(page) + kernel + bytes(-len(kernel)%4096) + ramdisk + bytes(-len(ramdisk)%4096)
    if len(result) > CAPACITY:
        raise ValueError('Temporary boot exceeds historical 64-MiB capacity')
    if image_parts(result) != (kernel, ramdisk):
        raise ValueError('Packaged payload changed')
    return result


def prepare(source, helper_path, out):
    pins = json.loads((HERE/'pins.json').read_text())
    boot, init = (source/'boot.img').read_bytes(), (source/'init_boot.img').read_bytes()
    if sha(boot) != pins['boot_sha256'] or sha(init) != pins['init_boot_sha256']:
        raise ValueError('Stage 24 input SHA256 mismatch')
    kernel, old_r = image_parts(boot)
    old_k, base = image_parts(init)
    if old_r or old_k or sha(kernel) != pins['kernel_sha256']:
        raise ValueError('Stage 24 kernel/init_boot layout mismatch')
    streams = legacy_streams(base)
    base_records = [read_records(s) for s in streams]
    busybox = None
    for records in base_records:
        targets = [r for r in records if r[2] == 'bin/busybox']
        if targets:
            target = targets[-1]
            busybox = next((r[3] for r in records if r[1][0] == target[1][0]
                            and r[1][7:9] == target[1][7:9] and r[3]), None)
    if not busybox or busybox[:6] != b'\x7fELF\x02\x01' or struct.unpack_from('<H', busybox, 18)[0] != 183:
        raise ValueError('Missing ARM64 BusyBox hardlink payload')
    overlay = make_overlay(helper_path.read_bytes())
    compressed = subprocess.run(['lz4', '-l', '-9', '-c'], input=overlay, capture_output=True, check=True).stdout
    new_ramdisk = base + compressed
    decoded = legacy_streams(new_ramdisk)
    if decoded[:-1] != streams or decoded[-1] != overlay:
        raise ValueError('Initramfs stream roundtrip failed')
    files = {r[2]: r for r in read_records(decoded[-1])}
    if files['init'][3] != files['aurora-stage25-init'][3]:
        raise ValueError('Diagnostic PID1 replacement mismatch')
    final = combined_boot(boot, kernel, new_ramdisk)
    out.mkdir(parents=True, exist_ok=True)
    (out/'boot-stage25-usb.img').write_bytes(final)
    # Check applets with qemu-user in CI, never run init or the reboot branch.
    (out/'busybox-for-check').write_bytes(busybox)
    (out/'busybox-for-check').chmod(0o755)
    report = {'stage': 25, 'purpose': 'USB-first RAM diagnostic using unchanged Stage24 kernel',
              'priority': ['USB recovery', 'Aurora UI', 'speaker disablement'],
              'input': pins, 'kernel_sha256': sha(kernel), 'boot_sha256': sha(final),
              'boot_bytes': len(final), 'header_version': 4, 'cmdline': CMDLINE.decode(),
              'base_initrd_preserved': True, 'base_lz4_streams': len(streams),
              'diagnostic_entrypoints': ['/init', '/aurora-stage25-init'],
              'vendor_modules': 'bootloader-supplied active-slot modules only; not bundled or forced',
              'rootfs_mounted_by_diagnostic': False, 'software_deadline_seconds': 90,
              'hardware_watchdog': False, 'bootloader_acceptance_tested': False,
              'usb_enumeration_tested': False, 'ut_runtime_usb_recovered': False,
              'speaker_disabled': False, 'flash_supported': False,
              'timer_limitation': 'Only starts if diagnostic PID1 runs; cannot recover a kernel/bootloader hang'}
    (out/'audit.json').write_text(json.dumps(report, indent=2)+'\n')
    (out/'sources.json').write_text(json.dumps(pins, indent=2)+'\n')
    (out/'SHA256SUMS').write_text(''.join(sha((out/n).read_bytes())+'  '+n+'\n'
                                        for n in ('boot-stage25-usb.img','audit.json','sources.json')))
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('source', type=Path)
    ap.add_argument('helper', type=Path)
    ap.add_argument('output', type=Path)
    args = ap.parse_args()
    prepare(args.source, args.helper, args.output)
