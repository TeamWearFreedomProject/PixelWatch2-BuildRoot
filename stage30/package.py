#!/usr/bin/env python3
import hashlib,json,shutil,subprocess,sys,zipfile
from pathlib import Path
REPO=Path(__file__).resolve().parent.parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main(out,work):
    report=json.loads((out/'native-check.json').read_text());assert report['status']=='PASS'
    bundle=out/'aurora-stage30'
    (bundle/'LICENSES').mkdir(exist_ok=True)
    shutil.copyfile(work/'launcher/lipstick/LICENSE.LGPL',bundle/'LICENSES/LGPL-2.1.txt')
    (bundle/'UPSTREAM.txt').write_text('AsteroidOS asteroid-launcher c8c4d4bd469c8ae5223f4bb7a58e3c96982eb1d9\nhttps://github.com/AsteroidOS/asteroid-launcher/tree/c8c4d4bd469c8ae5223f4bb7a58e3c96982eb1d9\nMatching source and licenses: aurora-stage30-source.zip included in this download and the GitHub artifact.\nOnly the entry URL in .rodata is redirected; see compositor-patch.json.\n')
    core='\n'.join(sha(p)+'  '+str(p.relative_to(bundle)) for p in sorted(bundle.rglob('*')) if p.is_file() and p.name not in ('build.json','SHA256SUMS'))+'\n'
    ident=hashlib.sha256(core.encode()).hexdigest()[:12]
    upload='/home/ceres/aurora-upload-'+ident;remote=upload+'/aurora-stage30'
    (bundle/'build.json').write_text(json.dumps({**report,'bundle_id':ident,'upload_parent':upload,'remote_package':remote,'installed_prefix':'/var/lib/aurora'},indent=2)+'\n')
    manifest='\n'.join(sha(p)+'  '+str(p.relative_to(bundle)) for p in sorted(bundle.rglob('*')) if p.is_file() and p.name!='SHA256SUMS')+'\n'
    (bundle/'SHA256SUMS').write_text(manifest)
    guide='''# Stage30 / Windows手順

時計の初期設定を終え、画面を点灯させ、Stage28/29等の独立プレビューを閉じておく。
ZIPを展開し、aurora-stage30フォルダーが見える場所でPowerShellを開く。
adb shell内ならexitでPowerShellへ戻る。WATCH_SERIALを時計のシリアルへ変更する。

```powershell
$watchSerial = 'WATCH_SERIAL'
$uploadBase = 'UPLOAD'
$remoteStage30 = "$uploadBase/aurora-stage30"
if ($watchSerial -eq 'WATCH_SERIAL') { throw 'Set the watch serial first' }
adb -s $watchSerial shell "mkdir -p '$uploadBase'"
adb -s $watchSerial push .\\aurora-stage30 "$uploadBase/"
adb -s $watchSerial shell "chmod -R a+rX '$remoteStage30'; chmod 755 '$remoteStage30/aurora-preview' '$remoteStage30/aurora-helper' '$remoteStage30/aurora-compositor'"
adb -s $watchSerial shell "$remoteStage30/aurora-preview --runtime-check"
adb -s $watchSerial shell "$remoteStage30/aurora-preview --session-check"
```

両方PASSなら、独立プレビューで画面・タップ・ハニカムのドラッグを確認する。
文字盤へ戻ってもう一度アプリ一覧を開くと、中央の位置へ戻る。

```powershell
adb -s $watchSerial shell "$remoteStage30/aurora-preview --watch-session"
```

プレビューはⓘ →「プレビューを閉じる」で終了する。
プレビューの通知データと、専用ヘルパーが必要なdmesg/USB切替はホーム導入後に確認する。

## システムの画面をAuroraへ切り替える

画面が再起動する。元のAsteroidOS V1実行ファイルは残し、専用コピーがAuroraの
メイン画面を直接読み込むように切り替える。systemdの専用追加設定を使う。
ルートが読み取り専用の場合は導入中だけ書き込み可能にし、元の状態へ戻す。

```powershell
adb -s $watchSerial shell "cd '$remoteStage30' && sh install.sh"
```

起動後、画面の準備完了と最初の描画を確認してから、独立したヘルパーへ通知する。
60秒以内に準備完了が来ない場合は、前のランチャーへ戻す。
再起動後も同じ起動確認を行う。実機のGPU/入力/復帰動作は初回確認となる。

## 操作

- 時計から上へスワイプ: ハニカム。戻るボタンで時計へ。
- 時計から下へ: コントロールセンター。右へ: 通知。左へ: カレンダー。
- 予定: 下の「＋ 予定」から追加。種類と15分単位の時刻を選び、時計内へ保存。
  同期済みカレンダーの予定も表示する。
- 設定 → USB: ADB、SSH / USBネットワーク、充電専用を選択。
  SSHと充電専用ではADBが切れる。時計のUSB画面から戻せる。
  今回は現在モードだけを変え、再接続時の既定設定は変更しない。
  SSHは時計に表示されたIPへ、既存の鍵・パスワードで接続する。認証設定は変更しない。
- 歩数: QtSensorsの実センサーを利用。未取得なら未取得と表示し、偽の値は出さない。
  このUIが記録した当日の値を保存する。起動前の履歴や未対応のHALの値は補えない。
- Linuxコンソール: dmesg、uname、uptime、network、システム画面からmemory/df。
  読み取り専用。dmesgは専用ヘルパーが非破壊で読む。GUIをrootで動かさない。

## 前のランチャーへ戻す

```powershell
adb -s $watchSerial shell "sh /var/lib/aurora/restore.sh"
```

Stage29を既定にしていた場合は、その設定を使う以前のランチャーへ戻る。
/var/lib/auroraを手動で消さず、復元コマンドを使う。
カーネル、boot/init_boot、パーティション、USBドライバーは変更しない。
実機USB切替・SSH認証・歩数・省電力・サスペンドは実機で確認が必要。
'''.replace('UPLOAD',upload)
    (out/'WINDOWS-STAGE30.md').write_text(guide)
    shutil.copyfile(REPO/'docs/STAGE30.md',out/'README-STAGE30.md')
    source=out/'aurora-stage30-source.zip'
    # The modified executable's matching upstream source and licenses accompany
    # our redirect tool. No SDK, rootfs or shared OS libraries are distributed.
    upstream=work/'launcher-source.tar'
    subprocess.run(['git','-C',str(work/'launcher'),'archive','--format=tar','--prefix=asteroid-launcher/','c8c4d4bd469c8ae5223f4bb7a58e3c96982eb1d9','-o',str(upstream)],check=True)
    with zipfile.ZipFile(source,'w',zipfile.ZIP_DEFLATED) as z:
        for folder in ('stage30','stage29','stage28','stage27/qml'):
            for p in sorted((REPO/folder).rglob('*')):
                if p.is_file() and '__pycache__' not in p.parts:z.write(p,str(p.relative_to(REPO)))
        for name in ('stage27/v1-pins.json','docs/STAGE30.md','.github/workflows/stage30-aurora-shell.yml'):z.write(REPO/name,name)
        z.write(upstream,'upstream/asteroid-launcher-c8c4d4bd46.tar')
    # Include the notice in the final integrity manifest.
    (bundle/'SHA256SUMS').write_text('\n'.join(sha(p)+'  '+str(p.relative_to(bundle)) for p in sorted(bundle.rglob('*')) if p.is_file() and p.name!='SHA256SUMS')+'\n')
    archive=out/'aurora-stage30-shell.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for p in sorted(bundle.rglob('*')):
            if p.is_file():z.write(p,str(p.relative_to(out)))
        for name in ('WINDOWS-STAGE30.md','README-STAGE30.md'):z.write(out/name,name)
        z.write(source,source.name)
    (out/'SHA256SUMS').write_text('\n'.join(sha(p)+'  '+str(p.relative_to(out)) for p in sorted(out.rglob('*')) if p.is_file() and p!=out/'SHA256SUMS')+'\n')
    print(json.dumps({'archive':archive.name,'sha256':sha(archive),'upload_parent':upload,'remote_package':remote}),flush=True)
if __name__=='__main__':main(Path(sys.argv[1]).resolve(),Path(sys.argv[2]).resolve())
