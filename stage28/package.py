#!/usr/bin/env python3
"""Package only our ARM32 executable, QML, matching source and reports."""
import hashlib
import json
from pathlib import Path
import shutil
import sys
import zipfile

REPO = Path(__file__).resolve().parent.parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def package(out):
    report = json.loads((out / 'native-check.json').read_text())
    if report['status'] != 'PASS':
        raise ValueError('Cannot package unverified executable')
    bundle = out / 'aurora-stage28'
    files = sorted(p for p in bundle.rglob('*') if p.is_file() and p.name not in ('build.json', 'SHA256SUMS'))
    core_manifest = '\n'.join(sha(p) + '  ' + str(p.relative_to(bundle)) for p in files) + '\n'
    bundle_id = hashlib.sha256(core_manifest.encode()).hexdigest()[:12]
    remote = '/home/ceres/aurora-preview-' + bundle_id
    (bundle / 'build.json').write_text(json.dumps({**report, 'bundle_id': bundle_id,
                                                 'remote_directory': remote}, indent=2) + '\n')
    sums = '\n'.join(sha(p) + '  ' + str(p.relative_to(bundle)) for p in sorted(bundle.rglob('*'))
                     if p.is_file() and p != bundle / 'SHA256SUMS') + '\n'
    (bundle / 'SHA256SUMS').write_text(sums)
    guide = '''# Stage28 / Windowsから独立プレビューを起動する

時計の初期設定を済ませて、AsteroidOSの通常画面を出す。
ZIPを展開し、`aurora-stage28`フォルダーが見える場所でPowerShellを開く。
ADB shellの中にいる場合は先に`exit`でPowerShellへ戻る。
この例のWATCH_SERIALを、`adb devices -l`で確認した時計のシリアルへ置き換える。

```powershell
$watchSerial = 'WATCH_SERIAL'
$remotePreview = 'REMOTE'
if ($watchSerial -eq 'WATCH_SERIAL') { throw 'Set the watch serial first' }
if ((Get-FileHash .\\aurora-stage28\\aurora-preview -Algorithm SHA256 -ErrorAction Stop).Hash -ne 'BINARY_SHA') { throw 'SHA256 mismatch' }
adb -s $watchSerial shell "mkdir -p '$remotePreview/qml'"
adb -s $watchSerial push .\\aurora-stage28\\aurora-preview "$remotePreview/aurora-preview"
adb -s $watchSerial push .\\aurora-stage28\\qml "$remotePreview/"
adb -s $watchSerial shell "chmod 755 '$remotePreview' '$remotePreview/aurora-preview'; chmod -R a+rX '$remotePreview/qml'"
adb -s $watchSerial shell "$remotePreview/aurora-preview --runtime-check"
adb -s $watchSerial shell "$remotePreview/aurora-preview --session-check"
```

runtime-checkが32bit・Qt 6.11.3、session-checkがPASSになったら起動する。
session-checkがFAILの場合はその出力を記録する。GUIユーザーやWaylandソケットを推測で指定しない。

```powershell
adb -s $watchSerial shell "$remotePreview/aurora-preview --watch-session"
```

起動後もこのPowerShellを開いておく。終了はアプリ一覧のiアイコン →「デモを閉じる」。
またはPowerShellでCtrl+Cを押す。AsteroidOSのランチャーを停止・置換する処理はない。
画面と起動時出力を記録する。実機GUIは今回が初試験で、CIはARM32のオフスクリーン描画まで。
Wi-Fi/Bluetoothの設定、カーネル、起動イメージ、音声サービスは変更しない。
'''.replace('REMOTE', remote).replace('BINARY_SHA', report['binary_sha256'])
    (out / 'WINDOWS-STAGE28.md').write_text(guide)
    shutil.copyfile(REPO / 'docs/STAGE28.md', out / 'README-STAGE28.md')
    archive = out / 'aurora-stage28-arm32.zip'
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for path in sorted(bundle.rglob('*')):
            if path.is_file(): zip_file.write(path, str(path.relative_to(out)))
        for name in ('WINDOWS-STAGE28.md', 'README-STAGE28.md'):
            zip_file.write(out / name, name)
    source = out / 'aurora-stage28-source.zip'
    with zipfile.ZipFile(source, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for directory in ('stage28', 'stage27/qml'):
            for path in sorted((REPO / directory).rglob('*')):
                if path.is_file() and '__pycache__' not in path.parts:
                    zip_file.write(path, str(path.relative_to(REPO)))
        for name in ('stage27/v1-pins.json', 'docs/STAGE28.md', '.github/workflows/stage28-arm32-preview.yml'):
            zip_file.write(REPO / name, name)
    manifest = '\n'.join(sha(p) + '  ' + str(p.relative_to(out))
                         for p in sorted(out.rglob('*')) if p.is_file() and p != out / 'SHA256SUMS') + '\n'
    (out / 'SHA256SUMS').write_text(manifest)
    print(json.dumps({'archive': archive.name, 'sha256': sha(archive),
                      'binary_sha256': report['binary_sha256'], 'remote_directory': remote}), flush=True)


if __name__ == '__main__':
    package(Path(sys.argv[1]).resolve())
