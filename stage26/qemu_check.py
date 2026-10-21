#!/usr/bin/env python3
"""Boot the final kernel with a conflicting external /init in a diskless VM."""
import argparse
import gzip
import json
from pathlib import Path
import stat
import subprocess
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from stage7.pack_modules import encode,fresh
from stage25.package import image_parts


def check(log,rc):
    needed=('AURORA_STAGE26_TIMER_ARMED seconds=90','AURORA_STAGE26_SHELL_STARTED',
            'AURORA_STAGE26_DEADLINE','AURORA_STAGE26_RESTART2_BOOTLOADER')
    missing=[s for s in needed if s not in log]
    if missing or rc!=0 or 'WRONG_EXTERNAL_INIT_EXECUTED' in log:
        raise ValueError('QEMU PID1/deadline check failed: '+str({'missing':missing,'rc':rc}))


def main():
    ap=argparse.ArgumentParser();ap.add_argument('artifact_dir',type=Path);ap.add_argument('work',type=Path);a=ap.parse_args()
    a.work.mkdir(parents=True,exist_ok=True)
    kernel,ramdisk=image_parts((a.artifact_dir/'boot-stage26-usb.img').read_bytes())
    if ramdisk:raise ValueError('Expected zero external boot ramdisk')
    image=a.work/'Image';image.write_bytes(kernel)
    # Private embedded paths must keep working when external /init and /bin/sh conflict.
    records=[fresh('bin',b'',stat.S_IFDIR|0o755,1),
             fresh('bin/sh',b'INVALID EXTERNAL SHELL\n',stat.S_IFREG|0o755,2),
             fresh('init',b'#!/bin/sh\necho WRONG_EXTERNAL_INIT_EXECUTED\n',stat.S_IFREG|0o755,3),
             fresh('TRAILER!!!',b'',0,4)]
    poison=a.work/'conflicting-init.cpio.gz';poison.write_bytes(gzip.compress(b''.join(encode(r) for r in records),mtime=0))
    cmd=['qemu-system-aarch64','-machine','virt,virtualization=on,gic-version=3','-cpu','cortex-a53',
         '-m','768','-smp','2','-display','none','-serial','stdio','-monitor','none','-nic','none',
         '-no-reboot','-kernel',str(image),'-initrd',str(poison),'-append',
         'console=ttyAMA0 earlycon=pl011,0x09000000 ignore_loglevel kvm-arm.mode=none']
    start=time.monotonic()
    try:
        result=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=180,text=True,errors='replace')
        log=result.stdout;rc=result.returncode
    except subprocess.TimeoutExpired as e:
        data=e.stdout or b'';log=data.decode(errors='replace') if isinstance(data,bytes) else data;rc=-1
    elapsed=time.monotonic()-start
    (a.artifact_dir/'qemu-boot.log').write_text(log)
    print(log[-8000:])
    check(log,rc)
    report={'status':'PASS','final_boot_image_kernel_tested':True,'external_init_conflict_ignored':True,
            'static_PID1_and_shell_started':True,'actual_90_second_deadline_requested_reboot':True,
            'emulated_machine_reboot_observed':True,'elapsed_host_seconds':round(elapsed,2),
            'persistent_disks_attached':False,'watch_USB_tested':False,'watch_fastboot_tested':False}
    (a.artifact_dir/'qemu-check.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
