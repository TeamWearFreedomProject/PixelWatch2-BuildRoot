#!/usr/bin/env python3
"""Test the final ARM32 executable against verified V1 runtime libraries."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile

REPO = Path(__file__).resolve().parent.parent


def guest(work, executable, args, timeout=90):
    host = work / 'sdk/sysroots/x86_64-oesdk-linux/usr/bin/qemu-arm'
    command = [str(host), '-cpu', 'cortex-a15', '-L', str(work / 'v1-runtime')]
    values = {'LD_BIND_NOW': '1', 'LD_LIBRARY_PATH': '/usr/lib:/lib',
              'QT_QPA_PLATFORM': 'offscreen', 'QT_QUICK_BACKEND': 'software',
              'QML_IMPORT_PATH': str(work / 'v1-runtime/usr/lib/qml'), 'QML_DISABLE_DISK_CACHE': '1', 'QT_IM_MODULE': 'none',
              'DBUS_SESSION_BUS_ADDRESS': 'disabled:', 'DBUS_SYSTEM_BUS_ADDRESS': 'disabled:'}
    for key, name in (('HOME', 'guest-home'), ('XDG_RUNTIME_DIR', 'guest-runtime')):
        directory = work / name
        directory.mkdir(exist_ok=True, mode=0o700)
        directory.chmod(0o700)
        values[key] = str(directory)
    env = os.environ.copy()
    for key in ('LD_LIBRARY_PATH', 'LD_PRELOAD', 'QT_PLUGIN_PATH', 'QML_IMPORT_PATH', 'QML2_IMPORT_PATH', 'QT_QPA_PLATFORM_PLUGIN_PATH'):
        env.pop(key, None)
    # Keep AF_UNIX fixture paths below sun_path's 108-byte limit even on long CI paths.
    with tempfile.TemporaryDirectory(prefix='a28-') as temporary:
        values['TMPDIR'] = temporary
        for key, value in values.items():
            command.extend(['-E', key + '=' + value])
        command.extend([str(executable), *args])
        return subprocess.run(command, capture_output=True, text=True, errors="backslashreplace", timeout=timeout, env=env)


def check(work, out):
    out.mkdir(parents=True, exist_ok=True)
    pins = json.loads((REPO / 'stage28/pins.json').read_text())
    bundle = out / 'aurora-stage29'
    bundle.mkdir(exist_ok=True)
    executable = bundle / 'aurora-home'
    shutil.copyfile(work / 'arm32-home/aurora-home', executable)
    executable.chmod(0o755)
    strip = work / 'sdk/sysroots/x86_64-oesdk-linux/usr/bin/arm-oe-linux-gnueabi/arm-oe-linux-gnueabi-strip'
    subprocess.run([str(strip), '--strip-unneeded', str(executable)], check=True)
    shutil.copytree(work / 'arm32-home/qml', bundle / 'qml', dirs_exist_ok=True)
    if (bundle / 'qml/Main.qml').read_bytes() != (REPO / 'stage29/qml/Main.qml').read_bytes():
        raise ValueError('Stale QML entry point')
    with executable.open('rb') as binary:
        header = binary.read(64)
    if header[:6] != b'\x7fELF\x01\x01' or struct.unpack_from('<H', header, 18)[0] != 40:
        raise ValueError('Expected little-endian ARM32 ELF')
    flags = struct.unpack_from('<I', header, 36)[0]
    if flags & 0xFF000400 != 0x05000400:
        raise ValueError('Expected ARM EABI5 hard-float ABI')
    dynamic = subprocess.check_output(['readelf', '-d', str(executable)], text=True)
    if '(RUNPATH)' in dynamic or '(RPATH)' in dynamic:
        raise ValueError('Unexpected embedded runtime search path')
    (out / 'elf-dynamic.txt').write_text(dynamic)
    runtime = guest(work, executable, ['--runtime-check'])
    (out / 'runtime-check.log').write_text(runtime.stdout + runtime.stderr)
    if runtime.returncode != 0:
        raise ValueError('V1 dynamic-link/runtime check failed')
    data = json.loads(runtime.stdout)
    if data.get('bits') != 32 or data.get('qt_build') != pins['expected_qt'] or data.get('qt_runtime') != pins['expected_qt']:
        raise ValueError('V1 runtime version/bitness mismatch')
    tests = guest(work, work / 'arm32-home/aurora-session-tests', [])
    (out / 'session-tests.log').write_text(tests.stdout + tests.stderr)
    if tests.returncode != 0 or '7 live-session' not in tests.stdout:
        raise ValueError('Live-session discovery/refusal tests failed')
    home_tests = guest(work, work / 'arm32-home/aurora-home-tests', [])
    (out / 'home-tests.log').write_text(home_tests.stdout + home_tests.stderr)
    if home_tests.returncode != 0 or '7 home activation' not in home_tests.stdout:
        raise ValueError('Home transaction checks failed')
    for mode in ('--session-check', '--watch-session', '--activate-home', '--restore-home', '--home-status'):
        refused = guest(work, executable, [mode])
        (out / (mode[2:] + '-no-session.log')).write_text(refused.stdout + refused.stderr)
        response = json.loads(refused.stdout)
        if refused.returncode != 2 or response.get('status') != 'FAIL' or response.get('gui_started') is not False:
            raise ValueError('Missing GUI session was not refused before display startup')
    captures = out / 'screenshots'
    captures.mkdir(exist_ok=True)
    result = guest(work, executable, ['--capture-dir', str(captures)])
    (out / 'arm32-gui.log').write_text(result.stdout + result.stderr)
    if result.returncode != 0:
        raise ValueError('ARM32 Qt 6.11.3 offscreen GUI check failed')
    for page in ('clock', 'apps', 'control', 'settings', 'stopwatch', 'style', 'timer', 'calculator', 'about'):
        image = captures / (page + '.png')
        if not image.exists() or image.stat().st_size < 500:
            raise ValueError('Missing rendered ARM32 page: ' + page)
    if '3 real Qt Quick input checks passed' not in result.stderr:
        raise ValueError('Real Qt Quick gesture checks missing')
    integrated = out / 'integrated-screenshots'
    integrated.mkdir(exist_ok=True)
    native = guest(work, executable, ['--capture-native', str(integrated)])
    (out / 'integration.log').write_text(native.stdout + native.stderr)
    if native.returncode != 0:
        raise ValueError('Native home/apps/quick-panel fixture failed')
    for page in ('clock','apps','control','settings'):
        if (integrated / (page+'.png')).stat().st_size < 500:
            raise ValueError('Missing integrated page: '+page)
    inputs = json.loads((work / 'inputs.json').read_text())
    report = {'status': 'PASS', 'bits': 32, 'machine': 'ARM', 'eabi': 5, 'hard_float': True,
              'binary_sha256': hashlib.sha256(executable.read_bytes()).hexdigest(),
              'qt_build': data['qt_build'], 'qt_runtime': data['qt_runtime'],
              'runtime_libraries': 'SHA256-verified public AsteroidOS V1',
              'ld_bind_now': True, 'session_discovery_checks': 7,
              'missing_session_refused': True, 'offscreen_pages_rendered': 9, 'integrated_pages_rendered': 4, 'home_transaction_checks':7, 'real_qt_input_checks':3, 'panel_attach_restore_fixture':True,
              'offscreen_navigation_pixels_checked': True,
              'stage28_watch_display_reported_working': True, 'stage29_watch_display_tested': False, 'watch_session_tested': False,
              'kernel_or_rootfs_replaced': False, 'inputs': inputs}
    (out / 'native-check.json').write_text(json.dumps(report, indent=2) + '\n')
    for name in ('sdk-preparation.json', 'sdk-relocation-inputs.json'):
        shutil.copyfile(work / name, out / name)
    shutil.copyfile(work / 'v1-runtime/.aurora-runtime.json', out / 'v1-runtime.json')
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    check(Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve())
