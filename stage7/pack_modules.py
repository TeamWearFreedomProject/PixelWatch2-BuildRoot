#!/usr/bin/env python3
"""Preserve Stage 5 newc CPIO and append Stage 6 ARM64 modules, offline only."""
import argparse
import gzip
import hashlib
import json
import pathlib
import stat

REQUIRED = {'gvotable.ko', 'logbuffer.ko', 'qpnp-smblite-main.ko',
            'google-bms.ko', 'google-battery.ko', 'google-charger.ko',
            'sw5100_bms.ko'}

def pad4(n):
    return (n + 3) & ~3

def read_records(data):
    result, pos = [], 0
    for _ in range(100000):
        if len(data) - pos < 110:
            raise ValueError('truncated CPIO header')
        header = data[pos:pos + 110]
        magic = header[:6]
        if magic not in (b'070701', b'070702'):
            raise ValueError('CPIO header is not newc/crc')
        vals = [int(header[6+i*8:14+i*8], 16) for i in range(13)]
        pos += 110
        size, namesize = vals[6], vals[11]
        if not 1 <= namesize <= 4096 or pos + namesize > len(data):
            raise ValueError('invalid CPIO name length')
        namebytes = data[pos:pos+namesize]
        if namebytes[-1:] != b'\0':
            raise ValueError('unterminated CPIO filename')
        name = namebytes[:-1].decode('utf-8')
        pos = pad4(pos + namesize)
        if pos + size > len(data):
            raise ValueError('truncated CPIO content')
        body = data[pos:pos+size]
        pos = pad4(pos+size)
        if magic == b'070702' and (sum(body) & 0xffffffff) != vals[12]:
            raise ValueError('CPIO CRC error')
        if name == 'TRAILER!!!':
            return result
        if name.startswith('/') or '..' in pathlib.PurePosixPath(name).parts:
            raise ValueError('unsafe CPIO name')
        result.append((magic, vals, name, body))
    raise ValueError('no CPIO trailer')

def encode(record):
    magic, values, name, data = record
    nameb = name.encode('utf-8') + b'\0'
    vals = list(values)
    vals[6], vals[11] = len(data), len(nameb)
    vals[12] = (sum(data) & 0xffffffff) if magic == b'070702' else 0
    if any(not 0 <= v <= 0xffffffff for v in vals):
        raise ValueError('CPIO numeric field overflow')
    buf = magic + ''.join(f'{v:08x}' for v in vals).encode() + nameb
    buf += b'\0' * (pad4(len(buf)) - len(buf))
    buf += data
    return buf + b'\0' * (pad4(len(buf)) - len(buf))

def fresh(name, data, mode, ino):
    values = [ino, mode, 0, 0, 2 if stat.S_ISDIR(mode) else 1,
              0, len(data), 0, 0, 0, 0, len(name.encode())+1, 0]
    return (b'070701', values, name, data)

def add(records, registry, path, data, mode, ino):
    parts = pathlib.PurePosixPath(path).parts
    for length in range(1, len(parts)):
        directory = '/'.join(parts[:length])
        if directory not in registry:
            ino += 1
            rec = fresh(directory, b'', stat.S_IFDIR | 0o755, ino)
            records.append(rec)
            registry[directory] = rec
        elif not stat.S_ISDIR(registry[directory][1][1]):
            raise ValueError(f'parent not a directory: {directory}')
    if path in registry:
        raise ValueError(f'overwriting existing entry prohibited: {path}')
    ino += 1
    rec = fresh(path, data, mode, ino)
    records.append(rec)
    registry[path] = rec
    return ino

def main():
    ap = argparse.ArgumentParser()
    for opt in ('input', 'output', 'modules', 'metadata', 'report'):
        ap.add_argument('--'+opt, type=pathlib.Path, required=True)
    ap.add_argument('--kernel-release', required=True)
    args = ap.parse_args()
    if not args.kernel_release or '/' in args.kernel_release or '..' in args.kernel_release:
        raise ValueError('unsafe kernel release')
    records = read_records(gzip.decompress(args.input.read_bytes()))
    reg = {r[2].removeprefix('./'): r for r in records}
    if len(records) != len(reg):
        raise ValueError('duplicate CPIO members')
    for path in ('init', 'bin/busybox', 'usr/bin/adbd', 'etc/inittab',
                 'usr/sbin/aurora-acm'):
        if path not in reg:
            raise ValueError(f'missing Stage 5 rootfs member: {path}')
    if b'ttyGS0' not in reg['etc/inittab'][3]:
        raise ValueError('Stage 5 serial getty absent')
    modules = sorted(args.modules.glob('*.ko'))
    if {f.name for f in modules} != REQUIRED:
        raise ValueError(f'expecting exactly seven power .ko, found {[f.name for f in modules]}')
    if 'lib' in reg and stat.S_ISLNK(reg['lib'][1][1]):
        target = reg['lib'][3].decode().removeprefix('./').lstrip('/')
        if target != 'usr/lib':
            raise ValueError(f'unexpected /lib symlink: {target}')
        base = 'usr/lib/modules/' + args.kernel_release
    else:
        base = 'lib/modules/' + args.kernel_release
    ino = max([r[1][0] for r in records] + [0])
    digests = {}
    for f in modules:
        content = f.read_bytes()
        if not (content[:4] == b'\x7fELF' and content[4:6] == b'\x02\x01'
                and int.from_bytes(content[18:20], 'little') == 183):
            raise ValueError(f'{f.name} is not AArch64 ELF')
        digests[f.name] = hashlib.sha256(content).hexdigest()
        ino = add(records, reg, f'{base}/extra/{f.name}', content,
                  stat.S_IFREG | 0o644, ino)
    metas = sorted(f for f in args.metadata.glob('modules.*') if f.is_file())
    if not any(f.name == 'modules.dep' for f in metas):
        raise ValueError('depmod modules.dep not generated')
    for f in metas:
        ino = add(records, reg, f'{base}/{f.name}', f.read_bytes(),
                  stat.S_IFREG | 0o644, ino)
    newc = b''.join(encode(r) for r in records)
    newc += encode(fresh('TRAILER!!!', b'', 0, ino+1))
    roundtrip = read_records(newc)
    lookup = {r[2].removeprefix('./'): r for r in roundtrip}
    if len(roundtrip) != len(records):
        raise ValueError('newc verification count mismatch')
    for f in modules:
        actual = lookup[f'{base}/extra/{f.name}'][3]
        if hashlib.sha256(actual).hexdigest() != digests[f.name]:
            raise ValueError('module changed during packing')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('wb') as stream:
        with gzip.GzipFile(fileobj=stream, mode='wb', filename='', mtime=0) as gz:
            gz.write(newc)
    report = {'status':'OFFLINE_STAGE7_ONLY', 'kernel_release':args.kernel_release,
              'module_base':base, 'modules':digests,
              'metadata':[f.name for f in metas],
              'rootfs_sha256':hashlib.sha256(args.output.read_bytes()).hexdigest(),
              'autoload':False, 'device_tested':False,
              'boot_safe':False, 'flash_safe':False}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))

if __name__ == '__main__':
    main()
