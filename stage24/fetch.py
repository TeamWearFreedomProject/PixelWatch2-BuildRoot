#!/usr/bin/env python3
"""Fetch the reviewed GitLab port and its inputs at immutable revisions."""
import argparse
import concurrent.futures
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import time
import urllib.request


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def destination(root, name):
    path = (root / name).resolve()
    if path == root or root not in path.parents:
        raise ValueError('Input destination escapes work directory')
    return path


def checkout(root, pin):
    if not re.fullmatch(r'[0-9a-f]{40}', pin['revision']):
        raise ValueError('Expected a complete Git commit')
    path = destination(root, pin['path'])
    path.mkdir(parents=True, exist_ok=True)
    def git(*args):
        return subprocess.run(['git', '-C', str(path), *args], check=True,
                              text=True, stdout=subprocess.PIPE).stdout.strip()
    git('init', '--quiet')
    if pin.get('sparse'):
        git('sparse-checkout', 'init', '--cone')
        git('sparse-checkout', 'set', *pin['sparse'])
    git('fetch', '--depth=1', '--no-tags', '--filter=blob:none',
        pin['url'], pin['revision'])
    git('checkout', '--detach', 'FETCH_HEAD')
    if git('rev-parse', 'HEAD') != pin['revision']:
        raise ValueError('Git revision mismatch')
    print('Pinned source: ' + pin['path'] + ' ' + pin['revision'], flush=True)


def download(root, pin):
    path = destination(root, 'inputs/' + pin['filename'])
    path.parent.mkdir(parents=True, exist_ok=True)
    def valid():
        return (path.is_file() and path.stat().st_size == pin['size']
                and digest(path) == pin['sha256'])
    if valid():
        print('Verified cached input: ' + pin['filename'], flush=True)
        return
    partial = path.with_name(path.name + '.part')
    for attempt in range(3):
        try:
            with urllib.request.urlopen(pin['url'], timeout=90) as r, partial.open('wb') as f:
                shutil.copyfileobj(r, f, 1024 * 1024)
            partial.replace(path)
            if not valid():
                raise ValueError('Downloaded input failed size/SHA256: ' + pin['filename'])
            print('Verified download: ' + pin['filename'], flush=True)
            return
        except (OSError, ValueError):
            partial.unlink(missing_ok=True)
            if attempt == 2:
                raise
            time.sleep(2 * (attempt + 1))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--work', type=Path, default=Path('stage24-work'))
    ap.add_argument('--phase', choices=['adaptation', 'assemble'], required=True)
    args = ap.parse_args()
    root = args.work.resolve()
    root.mkdir(parents=True, exist_ok=True)
    pins = json.loads(Path(__file__).with_name('pins.json').read_text())
    repos = pins['repositories']
    checkout(root, repos['port'])
    checkout(root, repos['tools'])
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        tasks = []
        if args.phase == 'adaptation':
            tasks += [pool.submit(checkout, root, p) for key, p in repos.items()
                      if key not in ('port', 'tools')]
        names = ['ramdisk'] if args.phase == 'adaptation' else ['rootfs', 'halium']
        tasks += [pool.submit(download, root, pins['downloads'][name]) for name in names]
        for task in tasks:
            task.result()
    # New generic tools default to Noble. This port is deliberately built for Focal.
    with (root / 'port/deviceinfo').open('a') as f:
        f.write('\n# Stage 24: explicit release, independent of generic-tool defaults.\n')
        f.write('deviceinfo_ubuntu_touch_release="focal"\n')
    if args.phase == 'adaptation':
        shutil.copyfile(root / 'inputs' / pins['downloads']['ramdisk']['filename'],
                        root / 'port/workdir/downloads/halium-boot-ramdisk.img')
    (root / 'sources.json').write_text(json.dumps(pins, indent=2) + '\n')


if __name__ == '__main__':
    main()
