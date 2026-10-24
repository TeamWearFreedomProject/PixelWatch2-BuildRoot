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
    bundle = out / 'aurora-stage29'
    files = sorted(p for p in bundle.rglob('*') if p.is_file() and p.name not in ('build.json', 'SHA256SUMS'))
    core_manifest = '\n'.join(sha(p) + '  ' + str(p.relative_to(bundle)) for p in files) + '\n'
    bundle_id = hashlib.sha256(core_manifest.encode()).hexdigest()[:12]
    remote = '/home/ceres/aurora-home-' + bundle_id
    (bundle / 'build.json').write_text(json.dumps({**report, 'bundle_id': bundle_id,
                                                 'remote_directory': remote}, indent=2) + '\n')
    sums = '\n'.join(sha(p) + '  ' + str(p.relative_to(bundle)) for p in sorted(bundle.rglob('*'))
                     if p.is_file() and p != bundle / 'SHA256SUMS') + '\n'
    (bundle / 'SHA256SUMS').write_text(sums)
    guide = '# Stage29 / Aurora Home\n\nStage28のプレビューを「i → デモを閉じる」で終了しておく。\nZIPを展開し、aurora-stage29フォルダーが見える場所でPowerShellを開く。\n時計側のshプロンプトなら、先にexitでPowerShellへ戻る。\nWATCH_SERIALをadb devices -lに表示される時計のシリアルへ置き換える。\n\n```powershell\n$watchSerial = \'WATCH_SERIAL\'\n$remoteHome = \'REMOTE\'\nif ($watchSerial -eq \'WATCH_SERIAL\') { throw \'Set the watch serial first\' }\nif ((Get-FileHash .\\aurora-stage29\\aurora-home -Algorithm SHA256 -ErrorAction Stop).Hash -ne \'BINARY_SHA\') { throw \'SHA256 mismatch\' }\nadb -s $watchSerial shell "mkdir -p \'$remoteHome/qml\'"\nadb -s $watchSerial push .\\aurora-stage29\\aurora-home "$remoteHome/aurora-home"\nadb -s $watchSerial push .\\aurora-stage29\\qml "$remoteHome/"\nadb -s $watchSerial shell "chmod 755 \'$remoteHome\' \'$remoteHome/aurora-home\'; chmod -R a+rX \'$remoteHome/qml\'"\nadb -s $watchSerial shell "$remoteHome/aurora-home --runtime-check"\nadb -s $watchSerial shell "$remoteHome/aurora-home --session-check"\n```\n\n両方PASSなら、最初に独立プレビューでタップとドラッグを試す。\n\n```powershell\nadb -s $watchSerial shell "$remoteHome/aurora-home --watch-session"\n```\n\nプレビューはi →「プレビューを閉じる」で終了する。\nハニカムは指でドラッグ。小さい外周アイコンは1回目で中央に寄り、もう一度タップで開く。\n上の戻るボタンで時計に戻る。時計上部のボタンからコントロールセンターを開く。\n設定の一覧は上下スクロール。Wi-Fi/BT/明るさ/自動の明るさ/常時表示はOSの設定に接続。\nアクセント色とアニメーションの設定は保存される。音声設定には触れない。\n\n## デフォルトのホームへ設定\n\n独立プレビューを閉じた状態で実行する。\n\n```powershell\nadb -s $watchSerial shell "$remoteHome/aurora-home --home-status"\nadb -s $watchSerial shell "$remoteHome/aurora-home --activate-home"\n```\n\n元の文字盤とアプリ一覧をGUIユーザーの.local/share/aurora-ui/home-backup.jsonへ保存する。\nAuroraの文字盤・アプリ一覧のURLを設定し、再起動後もこの設定が残る。\n両コンポーネントから12秒以内に準備完了通知が来なければ、元の設定へ戻してFAILを返す。\nAsteroidのコンポジターはそのまま使い、カーネル・USB・systemdサービスは置換しない。\n\nホームでは上から下へスワイプで新しいコントロールセンター。\n下から上へスワイプでハニカム。ハニカム内はドラッグ専用で、上の戻るボタンで時計に戻る。\n時計に入っている実際のアプリも一覧に追加し、Asteroidの通常起動処理へ渡す。\n標準の通知・消灯・サスペンド処理を引き続き利用する。\n\n## 元のホームへ戻す\n\n```powershell\nadb -s $watchSerial shell "$remoteHome/aurora-home --restore-home"\n```\n\nPASSを確認するまで、時計側のREMOTEフォルダーを移動・削除しない。\n設定後に他の文字盤等へ変更した場合、restoreはその変更を上書きせずFAILを返す。\nその場合は出力を記録する。\n\nCIはV1実ライブラリ/ARM32での描画、入力イベント、コンポジター用の模擬コンテキスト、\n設定保存・復元のロジックまで。Stage29の実機統合とOS設定変更は初回試験となる。\n'.replace('REMOTE', remote).replace('BINARY_SHA', report['binary_sha256'])
    (out / 'WINDOWS-STAGE29.md').write_text(guide)
    shutil.copyfile(REPO / 'docs/STAGE29.md', out / 'README-STAGE29.md')
    archive = out / 'aurora-stage29-home.zip'
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for path in sorted(bundle.rglob('*')):
            if path.is_file(): zip_file.write(path, str(path.relative_to(out)))
        for name in ('WINDOWS-STAGE29.md', 'README-STAGE29.md'):
            zip_file.write(out / name, name)
    source = out / 'aurora-stage29-source.zip'
    with zipfile.ZipFile(source, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for directory in ('stage29', 'stage28', 'stage27/qml'):
            for path in sorted((REPO / directory).rglob('*')):
                if path.is_file() and '__pycache__' not in path.parts:
                    zip_file.write(path, str(path.relative_to(REPO)))
        for name in ('stage27/v1-pins.json', 'docs/STAGE29.md', '.github/workflows/stage29-aurora-home.yml'):
            zip_file.write(REPO / name, name)
    manifest = '\n'.join(sha(p) + '  ' + str(p.relative_to(out))
                         for p in sorted(out.rglob('*')) if p.is_file() and p != out / 'SHA256SUMS') + '\n'
    (out / 'SHA256SUMS').write_text(manifest)
    print(json.dumps({'archive': archive.name, 'sha256': sha(archive),
                      'binary_sha256': report['binary_sha256'], 'remote_directory': remote}), flush=True)


if __name__ == '__main__':
    package(Path(sys.argv[1]).resolve())
