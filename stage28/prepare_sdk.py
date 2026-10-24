#!/usr/bin/env python3
"""Verify/extract official SDK, excluding only pinned broken staging residues."""
import hashlib
import json
from pathlib import Path
import re
import shlex
import subprocess
import sys

HERE = Path(__file__).resolve().parent


def prepare(work):
    pins = json.loads((HERE / 'pins.json').read_text())
    installer = work / 'downloads/asteroid-sdk.sh'
    digest = hashlib.sha512()
    with installer.open('rb') as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    if digest.hexdigest() != pins['sdk']['sha512']:
        raise ValueError('SDK source checksum mismatch')
    sdk = work / 'sdk'
    marker = sdk / '.aurora-payload-unpacked.json'
    if marker.exists() and json.loads(marker.read_text()).get('sha512') != pins['sdk']['sha512']:
        raise ValueError('Existing SDK comes from a different payload')
    with installer.open('rb', buffering=0) as source:
        lines = []
        while True:
            line = source.readline()
            if not line or source.tell() > 1024 * 1024:
                raise ValueError('SDK payload marker not found')
            if line == b'MARKER:\n':
                break
            lines.append(line)
        header = b''.join(lines).decode()
        offset = source.tell()
        if not marker.exists():
            sdk.mkdir(parents=True, exist_ok=True)
            print('Extract official verified SDK payload', flush=True)
            subprocess.run(['tar', '-mxJf', '-', '-C', str(sdk)], stdin=source, check=True)
            marker.write_text(json.dumps({'sha512': pins['sdk']['sha512'], 'payload_offset': offset}) + '\n')
    qt_header = sdk / 'sysroots/armv7vehf-neon-oe-linux-gnueabi/usr/include/QtCore/qtcoreversion.h'
    version = re.search(r'QTCORE_VERSION_STR "([^"]+)"', qt_header.read_text()).group(1)
    if version != pins['expected_qt']:
        raise ValueError('SDK Qt mismatch: ' + version)
    # Retain upstream setup/relocation logic. Extraction already completed above.
    begin = header.index('printf "Extracting SDK..."')
    end = header.index('printf "Setting it up..."', begin)
    header = header[:begin] + 'echo "Using verified extracted SDK payload"\n' + header[end:]
    original = 'executable_files=$($SUDO_EXEC find $native_sysroot -type f \\\n\t\\( -perm -0100 -o -perm -0010 -o -perm -0001 \\) -printf "\'%h/%f\' ")'
    if original not in header:
        raise ValueError('Pinned SDK relocation block changed')
    report = work / 'sdk-relocation-inputs.json'
    replacement = 'executable_files=$(' + shlex.quote(sys.executable) + ' ' + shlex.quote(str(HERE / 'sdk_tools.py')) + ' "$native_sysroot" ' + shlex.quote(str(report)) + ')'
    header = header.replace(original, replacement, 1)
    resumed = work / 'sdk-setup-validated.sh'
    resumed.write_text(header + '\nMARKER:\n')
    print('Relocate complete SDK tools; omit five validated non-runtime staging residues', flush=True)
    subprocess.run(['sh', str(resumed), '-y', '-d', str(sdk)], check=True)
    (work / 'sdk-preparation.json').write_text(json.dumps({
        'original_sdk_sha512': pins['sdk']['sha512'], 'qt_version': version,
        'header_adjustment': 'extract once; validate host ELFs and exclude only five pinned truncated staging files',
        'setup_header_sha256': hashlib.sha256(resumed.read_bytes()).hexdigest(),
        'target_libraries_modified': False,
    }, indent=2) + '\n')


if __name__ == '__main__':
    prepare(Path(sys.argv[1]).resolve())
