"""Quarantine ONLY local malformed staging files proven absent from pinned tar."""
from pathlib import Path
import hashlib,json,os,struct,tarfile,sys
work=Path(sys.argv[1]).resolve();source=work/'downloads/asteroid-sdk.sh'
pins=json.loads((Path(__file__).parent.parent/'stage28/pins.json').read_text())
h=hashlib.sha512()
with source.open('rb') as f:
    while data:=f.read(1024*1024):h.update(data)
assert h.hexdigest()==pins['sdk']['sha512']
root=work/'sdk/sysroots/x86_64-oesdk-linux';bad=[]
for p in root.rglob('*'):
    if p.is_symlink() or not p.is_file() or not os.access(p,os.X_OK):continue
    with p.open('rb') as f:b=f.read(64)
    if b[:6]==b'\x7fELF\x02\x01':
        offset=struct.unpack_from('<Q',b,40)[0];stride,count,index=struct.unpack_from('<HHH',b,58)
        if stride!=64 or not count or index>=count or offset+count*stride>p.stat().st_size:
            assert p.name.startswith('.'), 'Real executable malformed; no repair allowed'
            bad.append(p)
if not bad:print('No malformed staging files');raise SystemExit(0)
found={str(p.relative_to(work/'sdk')):False for p in bad}
with source.open('rb',buffering=0) as f:
    while f.readline()!=b'MARKER:\n':pass
    with tarfile.open(fileobj=f,mode='r|xz') as t:
        for m in t:
            name=m.name.removeprefix('./')
            if name in found:found[name]=True
assert not any(found.values()), 'Malformed file is in official archive; no repair allowed'
q=work/'quarantined-local-staging';q.mkdir(exist_ok=True)
for p in bad:p.rename(q/p.name)
(work/'local-extraction-audit.json').write_text(json.dumps({'absent_from_verified_archive':list(found)},indent=2))
print('Local unlisted staging files quarantined; strict relocation validator unchanged',len(bad))
