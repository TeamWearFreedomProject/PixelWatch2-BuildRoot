#!/usr/bin/env python3
"""Verify the final linked initramfs and config delta before temporary packaging."""
import argparse
import gzip
import json
from pathlib import Path
import re
import struct
import subprocess
import sys
import zlib

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from stage20.verify_embedded import locate
from stage25.package import image_parts, sha

PROJECT=Path(__file__).resolve().parents[1]
ENTRY=b'rdinit=/aurora26/pid1 panic=10'
EXPECTED_RELEASE='5.15.144-g063840c5aae1'
ALLOWED={'INITRAMFS_SOURCE','INITRAMFS_ROOT_UID','INITRAMFS_ROOT_GID','CMDLINE',
         'INITRAMFS_COMPRESSION_GZIP','INITRAMFS_COMPRESSION_BZIP2','INITRAMFS_COMPRESSION_LZMA',
         'INITRAMFS_COMPRESSION_XZ','INITRAMFS_COMPRESSION_LZO','INITRAMFS_COMPRESSION_LZ4',
         'INITRAMFS_COMPRESSION_ZSTD','INITRAMFS_COMPRESSION_NONE'}


def config(text):
    return dict(re.findall(r'^CONFIG_([A-Z0-9_]+)=(.*)$',text,re.M))


def config_delta(before,after):
    a,b=config(before),config(after)
    changes={k:{'before':a.get(k,'n'),'after':b.get(k,'n')}
             for k in a.keys()|b.keys() if a.get(k,'n')!=b.get(k,'n')}
    if set(changes)-ALLOWED:raise ValueError('Unexpected kernel config changes: '+str(set(changes)-ALLOWED))
    if b.get('INITRAMFS_COMPRESSION_GZIP')!='y' or ENTRY.decode() not in b.get('CMDLINE',''):
        raise ValueError('Missing embedded initramfs configuration or dedicated rdinit')
    if b.get('CMDLINE_EXTEND')!='y':raise ValueError('Expected CMDLINE_EXTEND')
    return changes


def boot_image(kernel):
    if len(kernel)<64 or kernel[56:60]!=b'ARM\x64':raise ValueError('Expected raw ARM64 Image')
    page=bytearray(4096);page[:8]=b'ANDROID!'
    struct.pack_into('<I',page,8,len(kernel));struct.pack_into('<I',page,20,1584)
    struct.pack_into('<I',page,40,4);page[44:44+len(ENTRY)]=ENTRY
    data=bytes(page)+kernel+bytes(-len(kernel)%4096)
    if len(data)>67108864:raise ValueError('Boot exceeds historical 64-MiB capacity')
    if image_parts(data)!=(kernel,b''):raise ValueError('Boot payload mismatch')
    return data


def verify_linked(obj,expected,image):
    lines=subprocess.check_output(['aarch64-linux-gnu-nm','--defined-only','--format=posix',str(obj/'vmlinux')],text=True).splitlines()
    starts=[s.split() for s in lines if s.startswith('__initramfs_start ')]
    if len(starts)!=1:raise ValueError('Missing unique __initramfs_start')
    elf=(obj/'vmlinux').read_bytes();start,end=locate(elf,int(starts[0][2],16))
    d=zlib.decompressobj(16+zlib.MAX_WBITS);cpio=d.decompress(elf[start:end],32*1024*1024)
    if not d.eof or cpio!=expected:raise ValueError('Final vmlinux initramfs mismatch')
    used=end-start-len(d.unused_data);compressed=elf[start:start+used]
    if compressed not in image:raise ValueError('Final ARM64 Image does not contain verified linked initramfs')
    return {'vmlinux':'MATCH','raw_ARM64_Image':'MATCH','cpio_sha256':sha(cpio),'compressed_bytes':used}


def main():
    ap=argparse.ArgumentParser();ap.add_argument('work',type=Path);ap.add_argument('out',type=Path);a=ap.parse_args()
    work=a.work.resolve();port=work/'port';obj=port/'workdir/downloads/KERNEL_OBJ';diag=work/'diagnostic'
    kernel_dir=port/'workdir/downloads/kernel-for-google-eos'
    release=(obj/'include/config/kernel.release').read_text().strip()
    if release!=EXPECTED_RELEASE:raise ValueError('Unexpected kernel release: '+release)
    subprocess.run(['git','-C',str(kernel_dir),'diff','--exit-code'],check=True,stdout=subprocess.DEVNULL)
    pins=json.loads((PROJECT/'stage24/pins.json').read_text())
    head=subprocess.check_output(['git','-C',str(kernel_dir),'rev-parse','HEAD'],text=True).strip()
    if head!=pins['repositories']['kernel']['revision']:raise ValueError('Kernel source revision mismatch')
    text=(obj/'.config').read_text();delta=config_delta((diag/'baseline.config').read_text(),text)
    kernel=(obj/'arch/arm64/boot/Image').read_bytes();cpio=(diag/'diagnostic.cpio').read_bytes()
    linked=verify_linked(obj,cpio,kernel);boot=boot_image(kernel)
    out=a.out;out.mkdir(parents=True,exist_ok=True)
    (out/'boot-stage26-usb.img').write_bytes(boot)
    (out/'kernel.config').write_text(text)
    report={'stage':26,'kernel_release':release,'kernel_source_revision':head,
            'stage24_same_pinned_source_and_toolchain':True,'kernel_binary_rebuilt':True,
            'kernel_sha256':sha(kernel),'boot_sha256':sha(boot),'boot_bytes':len(boot),
            'header_version':4,'external_boot_ramdisk_bytes':0,'entrypoint':'/aurora26/pid1',
            'embedded_initramfs':linked,'config_changes':delta,
            'software_deadline_seconds':90,'timer_starts_before_shell':True,'hardware_watchdog':False,
            'watch_boot_tested':False,'usb_enumeration_tested':False,'vendor_module_compatibility_tested':False,
            'ut_runtime_usb_recovered':False,'speaker_disabled':False,'flash_supported':False}
    (out/'audit.json').write_text(json.dumps(report,indent=2)+'\n')
    (out/'sources.json').write_text(json.dumps(pins,indent=2)+'\n')
    (out/'initramfs.json').write_bytes((diag/'initramfs.json').read_bytes())
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
