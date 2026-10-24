# Stage29: Aurora Home

Stage28はユーザーから実機で表示・動作したとの報告を得ました。Stage29はその後継で、
Pixel Watch 2 / 公開V1 (BUILD_ID 20261005064926、32bit、Qt 6.11.3、
asteroid-launcher c8c4d4bd46) を対象にします。

## 画面と操作

- 中心から広がる六角格子を円内へ連続的に投影し、外側ほどアイコンを縮小。
  2方向へドラッグして移動。小さな外周アイコンは1回目で中央へ移し、再タップで起動。
- Wi-Fi、Bluetooth、ライト、設定、明るさのコントロールセンター。
- スクロールする設定メニュー。自動の明るさ、常時表示、色、アニメーション、About。
- Nemo.Mce、Connman、org.asteroid.utilsの既存OS機能に接続。見た目のチェックだけを
  保存する偽のトグルは使わず、ネットワーク変更後の実値を確認する。
- 色と動きはNemo.Configurationの/org/aurora-ui/配下に保存。

## デフォルトのホーム

V1のコンポジターを稼働させたまま、AsteroidOSの文字盤・アプリ一覧を選ぶ設定を使う。
`/desktop/asteroid/watchface` と `/desktop/asteroid/applauncher` の2つのURLだけを
GUIユーザーとして変更する。元の値は同ユーザーのホームに原子的に保存する。
systemd、パーティション、起動イメージ、USBや音声サービスは変更しない。

NativeHome.qmlはV1のPanelsGrid公開関数(cellAt/movePanel/addPanel/removePanel)を確認し、
元のクイックパネルを破棄せず退避してAuroraパネルを挿入する。文字盤が外れると元へ戻す。
新しい文字盤とアプリ一覧が12秒以内にロード完了を返さなければ、CLIが元の設定へ戻す。
NativeApps.qmlはV1のLauncherModelに載るインストール済みアプリも追加し、各アプリの
launchApplicationへ渡す。アプリ一覧の戻るボタンで時計へ戻る。

`--activate-home` で設定、`--home-status` で確認、`--restore-home` で復元する。
バックアップがない場合や、設定後に利用者が別の文字盤へ変更した場合は推測で上書きしない。
元へ戻すまで、配置した時計側フォルダーを移動・削除しない。

## 検証の範囲

Stage28のSHA512固定SDK、SHA256固定V1ライブラリ、ARM32/EABI5/hard-floatを継承する。
最終strip済みバイナリーで、9画面と実際のQt Quick入力イベントを検査する。
ホーム・アプリ一覧・クイックパネルの組み込み用4画面は、V1の公開グリッドAPIを模した
コンテキストで実モジュールとともに描画し、元パネルの復元とネイティブ起動の転送を検査する。
設定の初回保存、アップグレード、復元、利用者の変更との競合、途中失敗時の復元も検査する。

CIは実機コンポジターそのものの稼働、タッチ精度、消費電力、サスペンド、OS設定変更の
実機動作を保証しない。まず独立プレビュー、その後デフォルト化を実機で確認する段階。
スピーカーのOS全体での無効化、既存通知のデザイン変更は未実装。

## 再ビルド

Linux x86_64でPython3、tar、xz、file、debugfs、readelfが必要。

```sh
python3 stage28/fetch_inputs.py stage28-work
python3 stage28/prepare_sdk.py stage28-work
bash stage29/build.sh
python3 stage28/prepare_runtime.py stage28-work
python3 stage29/check_native.py stage28-work stage29-artifacts
python3 stage29/package.py stage29-artifacts
```

SDK、V1共有ライブラリ、rootfsは配布物へ同梱しない。

## 照合した一次ソース

- [V1 MainScreen.qml](https://github.com/AsteroidOS/asteroid-launcher/blob/c8c4d4bd46/src/qml/MainScreen.qml)
- [V1 PanelsGrid.qml](https://github.com/AsteroidOS/asteroid-launcher/blob/c8c4d4bd46/src/qml/misc/PanelsGrid.qml)
- [V1 LauncherModel](https://github.com/AsteroidOS/asteroid-launcher/blob/c8c4d4bd46/lipstick/src/components/launchermodel.h)
- [AsteroidOS Display settings](https://github.com/AsteroidOS/asteroid-settings/blob/master/src/qml/DisplayPage.qml)
- [AsteroidOS Wi-Fi settings](https://github.com/AsteroidOS/asteroid-settings/blob/master/src/qml/WiFiPage.qml)
- [AsteroidOS quick panel](https://github.com/AsteroidOS/asteroid-launcher/blob/c8c4d4bd46/src/qml/quickpanel/QuickPanel.qml)
