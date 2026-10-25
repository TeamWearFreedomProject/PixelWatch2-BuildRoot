#!/usr/bin/env python3
import importlib.util,json,subprocess,sys
from pathlib import Path
REPO=Path(__file__).resolve().parent.parent
spec=importlib.util.spec_from_file_location('runtime29',REPO/'stage29/prepare_runtime.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

def prepare(work):
    module.extend(work)
    root=work/'v1-runtime';image=work/'downloads/v1.ext4'
    extra=[]
    for directory in ('/usr/share/applications','/usr/share/lipstick','/etc/xdg'):
        stat=subprocess.run(['debugfs','-R','stat '+directory,str(image)],capture_output=True,text=True,check=True)
        if 'Type: directory' not in stat.stdout:continue
        parent=root/Path(directory).parent.relative_to('/');parent.mkdir(parents=True,exist_ok=True)
        subprocess.run(['debugfs','-R','rdump '+directory+' '+str(parent),str(image)],check=True,capture_output=True)
        extra.append(directory)
    (work/'v1-shell-assets.json').write_text(json.dumps({'source':'SHA256-verified V1','extra_read_only_paths':extra},indent=2)+'\n')
    print('V1 shell assets extracted for tests',flush=True)
if __name__=='__main__':prepare(Path(sys.argv[1]).resolve())
