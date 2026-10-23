#!/usr/bin/env python3
"""Inspect pinned public V1 images with debugfs, without mounts or execution."""
import hashlib
import json
import os
from pathlib import Path
import posixpath
import re
import struct
import subprocess
import sys
import time
import urllib.request

HERE = Path(__file__).resolve().parent


def download(asset, directory):
    target = directory / asset['name']
    url = ('https://github.com/TeamWearFreedomProject/'
           'Pixel-Watch-2-Asteroid-OS-Beta/releases/download/V1/' + asset['name'])
    for attempt in range(3):
        try:
            digest = hashlib.sha256()
            count = 0
            request = urllib.request.Request(url, headers={'User-Agent': 'Aurora-Stage27-baseline-audit'})
            with urllib.request.urlopen(request, timeout=90) as response, target.open('wb') as output:
                while chunk := response.read(1024 * 1024):
                    count += len(chunk)
                    if count > asset['bytes']:
                        raise ValueError('Asset exceeds expected size: ' + asset['name'])
                    digest.update(chunk)
                    output.write(chunk)
            if count != asset['bytes'] or digest.hexdigest() != asset['sha256']:
                raise ValueError('Pinned SHA256/size mismatch: ' + asset['name'])
            return target
        except (OSError, ValueError):
            target.unlink(missing_ok=True)
            if attempt == 2:
                raise
            time.sleep(2 * (attempt + 1))


class Ext4:
    def __init__(self, image):
        self.image = image

    def command(self, command):
        # debugfs is read-only without -w. No image content is executed.
        result = subprocess.run(['debugfs', '-R', command, str(self.image)],
                                check=True, capture_output=True, timeout=40)
        errors = result.stderr.decode(errors='replace')
        if 'File not found' in errors or 'not a directory' in errors.lower():
            return None
        return result.stdout.decode(errors='replace')

    def resolve(self, path):
        for _ in range(8):
            data = self.command('stat ' + path)
            if not data or 'Inode:' not in data:
                return None
            link = re.search(r'Fast link dest: "([^"]+)"', data)
            if not link:
                return path
            path = posixpath.normpath(posixpath.join(posixpath.dirname(path), link.group(1)))
        raise ValueError('Symlink loop: ' + path)

    def read(self, path):
        resolved = self.resolve(path)
        return self.command('cat ' + resolved) if resolved else None

    def listing(self, path):
        data = self.command('ls -p ' + path) or ''
        return [line.split('/')[5] for line in data.splitlines()
                if line.startswith('/') and len(line.split('/')) > 6
                and line.split('/')[5] not in ('.', '..', '')]


def audit(work, out):
    work.mkdir(parents=True, exist_ok=True)
    out.mkdir(parents=True, exist_ok=True)
    pins = json.loads((HERE / 'v1-pins.json').read_text())
    report = {'source': pins['release'], 'assets': [],
              'user_hardware_report': pins['user_hardware_report'],
              'images_mounted': False, 'watch_binaries_executed': False,
              'watch_modified': False, 'gui_test_on_watch': False}
    images = {}
    for asset in pins['assets']:
        print('Verify ' + asset['name'], flush=True)
        image = download(asset, work)
        images[asset['name']] = image
        report['assets'].append({**asset, 'verified': True})
        if asset['name'] in ('boot.img', 'init_boot.img'):
            with image.open('rb') as source:
                header = source.read(4096)
            if header[:8] != b'ANDROID!' or struct.unpack_from('<I', header, 40)[0] != 4:
                raise ValueError('Unexpected Android boot header')
    root = images[pins['assets'][0]['name']]
    with root.open('rb') as source:
        source.seek(1080)
        if source.read(2) != b'\x53\xef':
            raise ValueError('Expected ext4 rootfs')
    fs = Ext4(root)
    texts = {}
    for path in ('/etc/os-release', '/usr/lib/os-release', '/etc/passwd', '/etc/fstab'):
        data = fs.read(path)
        if data:
            texts[path] = data[:65536]
    report['system_files'] = texts
    status = None
    for path in ('/usr/lib/opkg/status', '/var/lib/opkg/status'):
        status = fs.read(path)
        if status:
            report['package_database'] = path
            break
    if not status:
        raise ValueError('No opkg package database found in verified V1')
    packages = []
    for paragraph in status.split('\n\n'):
        fields = dict(line.split(': ', 1) for line in paragraph.splitlines() if ': ' in line and not line.startswith(' '))
        if re.search(r'asteroid-launcher|qml-asteroid|qtbase|qtdeclarative|qtquick|qtwayland|qmlscene|lipstick|font', fields.get('Package', '')):
            packages.append({key: fields.get(key) for key in ('Package', 'Version', 'Architecture', 'Status')})
    report['selected_packages'] = packages
    report['runtime_candidates'] = {path: fs.resolve(path) for path in (
        '/usr/bin/qmlscene', '/usr/bin/qml', '/usr/bin/asteroid-launcher',
        '/usr/bin/qt5/qmlscene', '/usr/lib/qt5/bin/qmlscene')}
    report['qml_directories'] = {path: fs.listing(path) for path in (
        '/usr/lib/qt5/qml', '/usr/lib/qml', '/usr/share/asteroid-launcher',
        '/usr/share/asteroid-launcher/watchfaces')}
    services = {}
    for directory in ('/usr/lib/systemd/user', '/lib/systemd/user', '/usr/lib/systemd/system', '/lib/systemd/system'):
        for name in fs.listing(directory):
            if re.search(r'asteroid|lipstick|compositor', name) and name.endswith('.service'):
                path = directory + '/' + name
                services[path] = (fs.read(path) or '')[:65536]
    report['launcher_services'] = services
    report['status'] = 'PASS'
    (out / 'v1-baseline.json').write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({'status': 'PASS', 'packages': packages,
                      'runtime_candidates': report['runtime_candidates']}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    audit(Path(sys.argv[1]), Path(sys.argv[2]))
