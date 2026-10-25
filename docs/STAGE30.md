# Stage30: Aurora system scene

通知、カレンダーと時計内予定、USB切替、歩数、Linuxコンソールを加え、
メイン画面からAuroraを直接読み込む段階です。ハニカムは文字盤へ戻ると破棄し、
再び開くと中央位置から作成します。旧MainScreenや旧パネルは生成しません。

## 読み込み構成

対象は公開AsteroidOS V1、BUILD_ID 20261005064926、32bit、Qt6.11.3です。
V1のasteroid-launcherを読み取り、SHA256・ELF・.rodataを検査したコピーの
メインQML URLだけを同じ長さの領域で変更します。機械語、動的リンク情報、
元の/usr/bin/asteroid-launcherは変更しません。Qtの非公開ABIを利用する表示基盤、
Wayland、MCE、通知受信、アプリ起動はV1の実行コードを引き継ぎます。

- 元実行ファイル SHA256: fa6ba6d39c3ae682417d777462241811b230fb9d2acdca0299234fcfee580f54
- 変更領域: .rodata、offset 691292、29 bytes（終端・埋め草を含む）
- 新エントリ: file:/var/lib/aurora/ui.qml

ホーム、通知リストとポップアップ、予定、設定、コントロールセンター、Bluetoothの
確認ダイアログ、終了画面はAurora側で描画します。従来のUIを退避するパネル操作は使いません。
外部アプリはそのアプリ自身の画面を表示します。

## 実データ

通知は既存NotificationListModelとorg.freedesktop.Notificationsに接続。
カレンダーはorg.nemomobile.calendarの同期済みデータと、Auroraのローカル予定を表示します。
ローカル予定は種類と時刻を選んで保存・削除できます。ファイル破損時は元データを上書きしません。

USBはusb-modedのset_modeを使い、adb_mode/developer_mode/charging_onlyを選びます。
現在モードだけを変更し、再接続時の設定にはset_configを書きません。
SSHは既存sshd.socketを起動し、既存の認証を使います。鍵・パスワードは変更しません。

歩数はQtSensors QStepCounterSensorを利用します。未取得と0歩を区別し、
このUIで計測した当日の値を保存します。起動前の履歴やHALの欠落は補いません。

Linuxコンソールは読み取り専用です。dmesg、uname、uptime、network、memory、dfを表示。
カーネルログは固定操作だけを受ける専用rootヘルパーが非破壊で読み、GUIへ渡します。
任意コマンド・任意ファイル・ログの消去は受け付けません。

## 導入と復元

専用コピーとQMLはroot所有の/var/lib/auroraに置き、ユーザーサービスの専用追加設定で
起動先を切り替えます。元サービスの描画・入力用環境を継承します。
専用rootヘルパーは起動後のシーンと最初の描画の確認を待ちます。60秒で確認が来なければ
以前のサービス設定へ戻します。通知元のUIDと実行ファイルを検査して準備完了を受け取ります。
復元はsh /var/lib/aurora/restore.sh。以前選んでいた文字盤等の設定も維持します。

導入時は追加ファイルとsystemd設定を書きます。ルートがROの場合は導入中だけRWへ変更し、
元へ戻します。boot/init_boot、パーティション、USBドライバーは変更しません。
表示・USB・歩数・省電力・サスペンドの実機確認は必要です。

## 再ビルド

```sh
python3 stage28/fetch_inputs.py stage28-work
python3 stage28/prepare_sdk.py stage28-work
bash stage30/build.sh
python3 stage30/prepare_runtime.py stage28-work
python3 stage30/tests/helper_peers.py stage28-work stage30-artifacts
python3 stage30/check_native.py stage28-work stage30-artifacts
```

全検査にはAF_UNIXと、専用一時パスを作成できるsudoを持つ使い捨てLinux環境が必要です。
元実行ファイルに対応するAsteroidOS/asteroid-launcherのc8c4d4bd46ソースとライセンスを
ソースZIPに含めます。コピーした表示基盤QMLの著作権表示は保持しています。
