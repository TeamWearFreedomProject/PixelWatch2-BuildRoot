#!/usr/bin/env python3
"""Compare the embedded gzip initramfs in final ELF64 vmlinux to our rootfs."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import zlib


def locate(data, address):
    if data[:6] != b'\x7fELF\x02\x01':
        raise ValueError('Not ELF64 little endian')
    phoff=struct.unpack_from('<Q',data,32)[0]
    entsize,count=struct.unpack_from('<HH',data,54)
    if entsize!=56 or phoff+entsize*count>len(data):
        raise ValueError('Invalid ELF program table')
    for i in range(count):
        kind,_,offset,vaddr,_,filesz,_,_=struct.unpack_from('<IIQQQQQQ',data,phoff+i*entsize)
        if kind==1 and vaddr<=address<vaddr+filesz:
            if offset+filesz>len(data): raise ValueError('ELF load segment out of range')
            return offset+(address-vaddr),offset+filesz
    raise ValueError('Initramfs symbol is outside ELF load segments')


def verify(vmlinux, rootfs, nm='aarch64-linux-gnu-nm'):
    output=subprocess.check_output([nm,'--defined-only','--format=posix',str(vmlinux)],text=True)
    rows=[l.split() for l in output.splitlines() if l.startswith('__initramfs_start ')]
    if len(rows)!=1: raise ValueError('No unique linked initramfs start symbol')
    data=vmlinux.read_bytes();pos,end=locate(data,int(rows[0][2],16))
    decoder=zlib.decompressobj(16+zlib.MAX_WBITS)
    unpacked=decoder.decompress(data[pos:end],64*1024*1024)
    if not decoder.eof: raise ValueError('Linked initramfs is not a complete gzip archive')
    expected=gzip.decompress(rootfs.read_bytes())
    if unpacked!=expected: raise ValueError('Final vmlinux contains a different initramfs')
    return {'stage':20,'initramfs_in_final_vmlinux':'MATCH',
            'uncompressed_cpio_sha256':hashlib.sha256(unpacked).hexdigest(),
            'rootfs_gzip_sha256':hashlib.sha256(rootfs.read_bytes()).hexdigest()}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for arg in ('vmlinux','rootfs','output'): p.add_argument('--'+arg,type=Path,required=True)
    a=p.parse_args();r=verify(a.vmlinux,a.rootfs)
    a.output.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))


if __name__=='__main__': main()
