#!/usr/bin/env python3
"""Build a self-contained, static diagnostic CPIO in a private /aurora26 tree."""
import argparse
import gzip
import json
from pathlib import Path
import stat
import struct
import subprocess
import sys
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from stage7.pack_modules import add, encode, fresh, read_records
from stage25.package import legacy_streams, image_parts, sha, static_arm64

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent


def busybox_from_init(data):
    _, ramdisk = image_parts(data)
    for stream in legacy_streams(ramdisk):
        records = read_records(stream)
        for target in records:
            if target[2] == 'bin/busybox':
                for r in records:
                    if r[1][0] == target[1][0] and r[1][7:9] == target[1][7:9] and r[3]:
                        static_arm64(r[3])
                        return r[3]
    raise ValueError('No static ARM64 BusyBox hardlink payload')


def archive(bb, pid1, applets):
    static_arm64(bb); static_arm64(pid1)
    required = {'sh','getty','mount','sleep','cat','ln','modprobe','grep','dmesg','uname','ls','mkdir','head'}
    if not required <= set(applets):
        raise ValueError('BusyBox missing required applets: '+str(required-set(applets)))
    records, registry, ino = [], {}, 910000
    def put(name, data, mode=stat.S_IFREG | 0o755):
        nonlocal ino
        ino = add(records, registry, name, data, mode, ino)
    put('aurora26/busybox', bb)
    put('aurora26/pid1', pid1)
    put('aurora26/init', (HERE/'overlay/init').read_bytes())
    put('aurora26/modules.load', (PROJECT/'stage25/overlay/etc/aurora-stage25.modules').read_bytes(), stat.S_IFREG | 0o644)
    for name, source in [('acm','aurora-acm25'),('console','aurora-console25'),('info','aurora-info25')]:
        text = (PROJECT/'stage25/overlay/usr/sbin'/source).read_text()
        text = text.replace('#!/bin/sh', '#!/aurora26/busybox sh')
        text = text.replace('aurora-info25', 'aurora-info26')
        text = text.replace('stage25','stage26').replace('STAGE25','STAGE26')
        text = text.replace('PATH=/sbin:/usr/sbin:/bin:/usr/bin', 'PATH=/aurora26/bin')
        text = text.replace('UT Stage24 kernel / RAM-only USB diagnostic.', 'Embedded UT-source kernel / RAM-only USB diagnostic.')
        text = text.replace('exec /bin/sh -i', 'exec /aurora26/busybox sh -i')
        put('aurora26/'+name, text.encode())
    for applet in sorted(set(applets)):
        if '/' in applet or applet in ('.','..') or not applet:
            raise ValueError('Invalid BusyBox applet name')
        put('aurora26/bin/'+applet, b'../busybox', stat.S_IFLNK | 0o777)
    for name, target in [('aurora-info26','../info'),('aurora-return','../pid1')]:
        put('aurora26/bin/'+name, target.encode(), stat.S_IFLNK | 0o777)
    for d in ('proc','sys','run','tmp'):
        put(d, b'', stat.S_IFDIR | 0o755)
    for name, major, minor in [('null',1,3),('console',5,1),('kmsg',1,11)]:
        put('dev/'+name, b'', stat.S_IFCHR | 0o600)
        registry['dev/'+name][1][9:11] = [major,minor]
    blob = b''.join(encode(r) for r in records)+encode(fresh('TRAILER!!!',b'',0,ino+1))
    check = {r[2]:r for r in read_records(blob)}
    if check['aurora26/pid1'][3] != pid1 or check['aurora26/busybox'][3] != bb:
        raise ValueError('Static payload roundtrip failed')
    if any(n.endswith('.ko') or n == 'init' or n.startswith(('bin/','lib/')) for n in check):
        raise ValueError('Diagnostic is not isolated under /aurora26')
    return blob


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('stage24_zip',type=Path);ap.add_argument('pid1',type=Path);ap.add_argument('output',type=Path)
    a=ap.parse_args();pins=json.loads((PROJECT/'stage25/pins.json').read_text())
    if sha(a.stage24_zip.read_bytes()) != pins['artifact_sha256']:
        raise ValueError('Stage24 ZIP hash mismatch')
    with zipfile.ZipFile(a.stage24_zip) as z:
        data=z.read('init_boot.img')
        if sha(data) != pins['init_boot_sha256']:raise ValueError('Stage24 init_boot hash mismatch')
        baseline=z.read('kernel.config')
    a.output.mkdir(parents=True,exist_ok=True)
    bb=busybox_from_init(data);(a.output/'busybox').write_bytes(bb);(a.output/'busybox').chmod(0o755)
    applets=subprocess.check_output(['qemu-aarch64',str(a.output/'busybox'),'--list'],text=True).splitlines()
    blob=archive(bb,a.pid1.read_bytes(),applets)
    (a.output/'diagnostic.cpio').write_bytes(blob)
    (a.output/'diagnostic.cpio.gz').write_bytes(gzip.compress(blob,mtime=0))
    (a.output/'baseline.config').write_bytes(baseline)
    report={'stage':26,'cpio_sha256':sha(blob),'busybox_sha256':sha(bb),
            'static_pid1_sha256':sha(a.pid1.read_bytes()),'all_dependencies_under':'/aurora26',
            'arm64_static_userspace':True,'software_deadline_seconds':90,
            'stage25_hardware_result':{'com_enumerated':False,'automatic_fastboot_after_90s':False,
                                      'forced_reboot_to_fastboot':True,'root_cause_confirmed':False}}
    (a.output/'initramfs.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
