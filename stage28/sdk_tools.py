#!/usr/bin/env python3
"""Strict host-SDK relocation input validation for the SHA512-pinned SDK."""
import json
import os
from pathlib import Path
import shlex
import struct
import sys

# These truncated staging residues were observed during local SDK setup.
# They may be absent on a clean CI extraction. Never ignore other corruption.
RESIDUES = {
    'usr/bin/.qemu-system-mipsel.p8TF6q': 8126464,
    'usr/bin/.cmake.wc2B1G': 1572864,
    'usr/lib/.libLLVM.so.21.1.Pbq27p': 63963136,
    'usr/lib/.libclang-cpp.so.21.1.XFghf9': 41418752,
    'usr/libexec/arm-oe-linux-gnueabi/gcc/arm-oe-linux-gnueabi/15.2.0/.lto1.twArky': 24903680,
}


def executables(root):
    valid, skipped = [], []
    for path in sorted(root.rglob('*')):
        if path.is_symlink() or not path.is_file() or not os.access(path, os.X_OK):
            continue
        with path.open('rb') as source:
            header = source.read(64)
        relative = str(path.relative_to(root))
        malformed = False
        if header[:6] == b'\x7fELF\x02\x01':
            if len(header) != 64:
                malformed = True
            else:
                offset = struct.unpack_from('<Q', header, 40)[0]
                stride, count, strings = struct.unpack_from('<HHH', header, 58)
                malformed = stride != 64 or count == 0 or strings >= count or offset + count * stride > path.stat().st_size
        if malformed:
            if relative not in RESIDUES or path.stat().st_size != RESIDUES[relative]:
                raise ValueError('Unexpected malformed SDK ELF: ' + relative)
            counterpart = path.with_name(path.name[1:].rsplit('.', 1)[0])
            if not counterpart.is_file():
                raise ValueError('No complete counterpart for SDK residue: ' + relative)
            skipped.append(relative)
        else:
            if relative in RESIDUES:
                raise ValueError('SDK residue unexpectedly changed: ' + relative)
            valid.append(str(path))
    return valid, skipped


if __name__ == '__main__':
    root = Path(sys.argv[1]).resolve()
    valid, skipped = executables(root)
    if len(sys.argv) > 2:
        Path(sys.argv[2]).write_text(json.dumps({'validated_executables': len(valid), 'excluded_staging_files': skipped}, indent=2) + '\n')
    print(' '.join(shlex.quote(path) for path in valid))
