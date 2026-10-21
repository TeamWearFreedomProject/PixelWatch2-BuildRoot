#!/usr/bin/env python3
"""Adjust generated Kconfig only; leave the pinned kernel source tree clean."""
from pathlib import Path
import sys

CMDLINE_SUFFIX='rdinit=/aurora26/pid1 panic=10'


def configure(text, cpio):
    cpio=str(cpio)
    if any(c in cpio for c in ('"','\n','\\')):raise ValueError('Unsafe initramfs path')
    lines=text.splitlines()
    command=next(s for s in lines if s.startswith('CONFIG_CMDLINE='))
    if not command.endswith('"'):raise ValueError('Malformed CMDLINE')
    if 'rdinit=' in command:raise ValueError('Unexpected existing rdinit')
    settings={'CONFIG_INITRAMFS_SOURCE':'"'+cpio+'"',
              'CONFIG_INITRAMFS_COMPRESSION_GZIP':'y',
              'CONFIG_CMDLINE':command.split('=',1)[1][:-1]+' '+CMDLINE_SUFFIX+'"'}
    filtered=[]
    for line in lines:
        key=line.split('=',1)[0]
        if line.startswith('# CONFIG_') and line.endswith(' is not set'):
            key=line[2:-11]
        if key not in settings:filtered.append(line)
    return '\n'.join(filtered+[k+'='+v for k,v in settings.items()])+'\n'


if __name__=='__main__':
    path=Path(sys.argv[1]);cpio=Path(sys.argv[2]).resolve()
    if not cpio.is_file():raise SystemExit('Missing diagnostic CPIO')
    path.write_text(configure(path.read_text(),cpio))
