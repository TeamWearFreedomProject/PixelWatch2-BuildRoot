#!/usr/bin/env python3
"""Redirect a SHA256-pinned copy's QML entry URL, preserving every code byte."""
import hashlib,json,struct,subprocess,sys
from pathlib import Path

ORIGINAL_SHA='fa6ba6d39c3ae682417d777462241811b230fb9d2acdca0299234fcfee580f54'
OLD=b'qrc:/Launcher/compositor.qml\0'
NEW=b'file:/var/lib/aurora/ui.qml\0'

def redirect(data,expected=ORIGINAL_SHA):
    if hashlib.sha256(data).hexdigest()!=expected:raise ValueError('Unexpected original compositor')
    if data[:6]!=b'\x7fELF\x01\x01' or struct.unpack_from('<H',data,18)[0]!=40:raise ValueError('Expected V1 ARM32 ELF')
    if data.count(OLD)!=1 or len(NEW)>len(OLD):raise ValueError('QML entry URL is not unique')
    offset=data.index(OLD)
    table=struct.unpack_from('<I',data,32)[0];stride,count,strings=struct.unpack_from('<HHH',data,46)
    if stride!=40 or table+count*stride>len(data):raise ValueError('Invalid ELF sections')
    headers=[struct.unpack_from('<10I',data,table+i*stride) for i in range(count)]
    names=data[headers[strings][4]:headers[strings][4]+headers[strings][5]]
    valid=False
    for h in headers:
        name=names[h[0]:].split(b'\0',1)[0]
        if name==b'.rodata' and h[4]<=offset and offset+len(OLD)<=h[4]+h[5]:valid=True
    if not valid:raise ValueError('Entry URL is not wholly inside .rodata')
    replacement=NEW.ljust(len(OLD),b'\0')
    result=data[:offset]+replacement+data[offset+len(OLD):]
    assert len(result)==len(data) and result[:offset]==data[:offset] and result[offset+len(OLD):]==data[offset+len(OLD):]
    return result,{'original_sha256':expected,'modified_sha256':hashlib.sha256(result).hexdigest(),'bytes':len(result),'offset':offset,'section':'.rodata','changed_span':len(OLD),'machine_code_modified':False,'entry_url':NEW.rstrip(b'\0').decode()}

def main(work,out):
    root=work/'downloads/v1.ext4'
    pins=json.loads((Path(__file__).resolve().parent.parent/'stage27/v1-pins.json').read_text())['assets'][0]
    if root.stat().st_size!=pins['bytes']:raise ValueError('V1 image size mismatch')
    h=hashlib.sha256()
    with root.open('rb') as f:
        while chunk:=f.read(1024*1024):h.update(chunk)
    if h.hexdigest()!=pins['sha256']:raise ValueError('V1 image checksum mismatch')
    original=work/'v1-compositor'
    subprocess.run(['debugfs','-R','dump /usr/bin/asteroid-launcher '+str(original),str(root)],capture_output=True,check=True)
    modified,report=redirect(original.read_bytes());out.mkdir(parents=True,exist_ok=True)
    target=out/'aurora-compositor';target.write_bytes(modified);target.chmod(0o755)
    (out/'compositor-patch.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report),flush=True)

if __name__=='__main__':main(Path(sys.argv[1]).resolve(),Path(sys.argv[2]).resolve())
