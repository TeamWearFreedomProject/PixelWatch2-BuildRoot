#!/usr/bin/env python3
"""Build the exact Google USB extcon shim into the diagnostic kernel."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import subprocess
import time
import urllib.request


def integrate(source, pin, output):
    path=source/'drivers/extcon/google-extcon-usb-shim.c'
    if path.exists(): raise ValueError('USB shim target already exists')
    url=pin['repository']+'/+/'+pin['revision']+'/'+pin['path']+'?format=TEXT'
    for attempt in range(4):
        try:
            with urllib.request.urlopen(url,timeout=45) as response:
                data=base64.b64decode(response.read(),validate=True)
            break
        except OSError:
            if attempt==3: raise
            time.sleep(2*(attempt+1))
    if hashlib.sha256(data).hexdigest()!=pin['sha256']: raise ValueError('USB shim source checksum mismatch')
    text=data.decode()
    for anchor in ('google,extcon-usb-shim','shim->force_report_connected = true;',
                   'supplier_notification_setup(shim)','module_platform_driver(extcon_usb_shim)'):
        if anchor not in text: raise ValueError('USB shim contract changed: '+anchor)
    makefile=source/'drivers/extcon/Makefile';kconfig=source/'drivers/extcon/Kconfig'
    if 'EXTCON_GOOGLE_USB_SHIM' in makefile.read_text()+kconfig.read_text():
        raise ValueError('USB shim routing already present')
    path.write_bytes(data)
    with makefile.open('a') as f: f.write('\nobj-$(CONFIG_EXTCON_GOOGLE_USB_SHIM) += google-extcon-usb-shim.o\n')
    with kconfig.open('a') as f:
        f.write('\nconfig EXTCON_GOOGLE_USB_SHIM\n\tbool "Google EOS USB extcon debug shim"\n\tdepends on EXTCON && OF\n\thelp\n\t  Forward the OEM USB extcon route, including its upstream debug\n\t  fallback when the supplier driver is unavailable.\n')
    subprocess.run(['git','-C',str(source),'add','-N','drivers/extcon/google-extcon-usb-shim.c'],check=True)
    output.write_text(json.dumps({'stage':20,'upstream':pin,'integration':'BUILTIN_EXTCON_GOOGLE_USB_SHIM',
                                 'supplier_failure_behavior':'upstream force_report_connected debug fallback',
                                 'physical_usb':'NOT_TESTED'},indent=2)+'\n')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for arg in ('kernel-source','pins','output'):p.add_argument('--'+arg,type=Path,required=True)
    a=p.parse_args();integrate(a.kernel_source,json.loads(a.pins.read_text())['usb_shim'],a.output)


if __name__=='__main__':main()
