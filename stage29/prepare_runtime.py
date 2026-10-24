#!/usr/bin/env python3
"""Read V1's icon assets for native icon rendering tests; never redistribute."""
import json
from pathlib import Path
import subprocess
import sys

REPO=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(REPO/'stage28'))
from prepare_runtime import prepare

def extend(work):
    root=prepare(work)
    destination=root/'usr/share/icons'
    destination.mkdir(parents=True,exist_ok=True)
    subprocess.run(['debugfs','-R','rdump /usr/share/icons/asteroid '+str(destination),
                    str(work/'downloads/v1.ext4')],check=True,capture_output=True)
    for name in ('ios-musical-notes','ios-calendar','ios-cloud','ios-heart','ios-alarm','ios-settings'):
        path=destination/'asteroid'/(name+'.svg')
        if not path.is_file() or b'<svg' not in path.read_bytes():
            raise ValueError('Missing V1 native icon: '+name)
    report={'source':'SHA256-verified V1 rootfs','read_only_source':True,
            'directory':'/usr/share/icons/asteroid','svg_files':len(list(destination.rglob('*.svg'))),
            'redistributed':False}
    (work/'v1-ui-assets.json').write_text(json.dumps(report,indent=2)+'\n')
    print('V1 native icons extracted for tests; not included in app ZIP',flush=True)

if __name__=='__main__':extend(Path(sys.argv[1]).resolve())
