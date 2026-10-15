#!/usr/bin/env python3
"""Offline CRC audit; does NOT establish working hardware or safe module loading."""
import argparse, json, pathlib, subprocess

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--kernel',type=pathlib.Path,required=True)
    p.add_argument('--group',type=pathlib.Path,action='append',default=[])
    p.add_argument('--module-dir',type=pathlib.Path,required=True)
    p.add_argument('--output',type=pathlib.Path,required=True)
    a=p.parse_args()
    exports={}
    for path in [a.kernel,*a.group]:
        if not path.is_file():
            raise ValueError('Missing kernel/module symvers: '+str(path))
        for line in path.read_text().splitlines():
            fields=line.split()
            if len(fields)<3:
                continue
            crc,name=int(fields[0],16),fields[1]
            if name in exports and exports[name]!=crc:
                raise ValueError('Conflicting CRC for export '+name)
            exports[name]=crc
    modules=sorted(a.module_dir.glob('*.ko'))
    expected={'gvotable.ko','logbuffer.ko','qpnp-smblite-main.ko',
              'qti-qbg-main.ko','google-bms.ko','google-battery.ko',
              'google-charger.ko','sw5100_bms.ko'}
    if {m.name for m in modules} != expected:
        raise ValueError('Expected exactly 8 known power modules; got '
                         +str([m.name for m in modules]))
    report={}
    errors=[]
    for module in modules:
        result=subprocess.run(['modprobe','--dump-modversions',str(module)],
                              check=True,capture_output=True,text=True)
        refs={}
        for row in result.stdout.splitlines():
            fields=row.split()
            if len(fields)!=2:
                raise ValueError('Malformed modprobe CRC record: '+row)
            crc,name=int(fields[0],16),fields[1]
            if name in refs and refs[name]!=crc:
                raise ValueError('Conflicting imported CRC: '+name)
            refs[name]=crc
        if not refs:
            raise ValueError('No version information in '+module.name)
        missing=sorted(name for name in refs if name not in exports)
        mismatched=sorted(name for name,crc in refs.items()
                          if name in exports and exports[name]!=crc)
        report[module.name]={'imported_symbols':len(refs),
                             'missing':missing,'mismatched':mismatched}
        if missing or mismatched:
            errors.append(module.name)
    result={'status':'OFFLINE_CRC_INTEGRITY_ONLY',
            'known_exports':len(exports),'module_checks':report,
            'failed_modules':errors,'hardware_verified':False}
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
    if errors:
        raise SystemExit('Module symbol CRCs unavailable or mismatched: '+', '.join(errors))

if __name__=='__main__':
    main()
