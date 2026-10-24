#!/usr/bin/env python3
"""Package a standalone QML preview; no kernel/rootfs/service replacements."""
import hashlib
import json
from pathlib import Path
import shutil
import sys
import zipfile

repo = Path(__file__).resolve().parent.parent
out = Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)
shutil.copyfile(repo / 'docs/STAGE27.md', out / 'README-STAGE27.md')
archive = out / 'aurora-stage27-qml-preview.zip'
with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as bundle:
    for source in sorted((repo / 'stage27/qml').glob('*.qml')):
        bundle.write(source, 'stage27/qml/' + source.name)
    for source in sorted((repo / 'stage27/native').iterdir()):
        if source.is_file():
            bundle.write(source, 'stage27/native/' + source.name)
    bundle.write(repo / 'docs/STAGE27.md', 'README-STAGE27.md')
    bundle.write(repo / 'stage27/v1-pins.json', 'v1-pins.json')
    bundle.write(out / 'v1-baseline.json', 'v1-baseline.json')
for name in ('clock', 'apps', 'stopwatch', 'style', 'timer', 'calculator'):
    source = out / (name + '.png')
    if not source.is_file() or source.stat().st_size < 500:
        raise ValueError('Missing rendered screenshot: ' + name)
manifest = []
for source in sorted(out.iterdir()):
    if source.is_file() and source.name != 'SHA256SUMS':
        manifest.append(hashlib.sha256(source.read_bytes()).hexdigest() + '  ' + source.name)
(out / 'SHA256SUMS').write_text('\n'.join(manifest) + '\n')
print(json.dumps({'archive': archive.name, 'sha256': hashlib.sha256(archive.read_bytes()).hexdigest(),
                  'contains_boot_images': False, 'installs_or_autostarts_services': False}))
