# Stage28: V1向けARM32独立プレビュー

実機からAsteroidOS 2.2-nightly、BUILD_ID 20261005064926、getconf LONG_BIT=32、
qtbase/qtdeclarative 6.11.3-r0、asteroid-launcher 1:2.1+152+git0+c8c4d4bd46-r1が
報告されました。公開V1の静的解析結果と一致します。全パーティションのバイト一致を
確認したという意味ではありません。

Stage27のColorOS for Watch/HarmonyOSに着想を得た独自QMLを、V1で動くARM32の
Qt6実行ファイルから開くための段階です。画面に出るStage27 Preview 1はUIデザインの版です。
標準ランチャーを残したまま試し、About画面に「デモを閉じる」を追加します。
カーネル、起動イメージ、パーティション、既存アプリ/サービスは置換しません。

## ビルドと実行前検査

- 公式ARM SDKのSHA512と公開V1 rootfsのSHA256/サイズを固定。
- SDKはQt 6.11.3を要求。ローカル配置で、不完全な一時ステージングファイル5件が
  ELFの再配置を止める問題を確認。クリーンなCIでは残らなかったため、それらの存在は
  必須にせず、既知の名前・サイズ・破損条件が全て一致する場合だけ除外する。
  未知の破損は拒否し、実行対象ELFの範囲と、除外対象の完全な本体があることを検査する。
  SDKの元データは変更せず、ターゲットQtライブラリも書き換えない。
- 同SDKのGCCがホストのasを選ばないよう、専用-BディレクトリからSDKのARM as/ldを選択。
- 最終バイナリーをstripした後で、ARM32/EABI5/hard-float、RPATH/RUNPATHなしを確認。
- V1のライブラリとフォントをdebugfsで読み取り、原本をmountせずQEMU用コピーを作成。
- ARM32実行ファイルをV1ライブラリで起動し、LD_BIND_NOW=1で32bit/Qt6.11.3を照合。
- GUIセッションの探索、誤った所有者や曖昧なセッションの拒否など7検査をARM32で実施。
- V1のQt6.11.3を使用して7画面をオフスクリーン描画し、戻るボタンの描画も検査。

V1ではStage27のQtQuick.Window 2.12の読み込みでエラーを確認したため、標準AsteroidOS
アプリと同様に、C++のQQuickViewにItem/RectangleのQMLを載せる方式へ変更しました。
デスクトップのQt6.2が通ることだけを根拠に、V1で動くとは扱いません。

## 実機のGUIセッション

`--runtime-check`はGUIを開かず、実際にリンクされたQt版とビット数を出します。
`--session-check`もGUIを開かず、起動中のbooster-asteroid-qt6サービスから必要な値だけを読みます。
UID/GID、所有者の一致するXDG_RUNTIME_DIR、Waylandソケットを検査し、複数の独立サービスが
あれば推測せず停止します。環境変数はホワイトリストだけを読み、認証トークン等は出力しません。

`--watch-session`はこの検査後、新しく起動するプロセスだけをGUIユーザーへ変更してから
QGuiApplicationを作ります。rootのGUIを起動せず、既存プロセスやサービスのUIDも変更しません。
アプリは検出したWaylandセッションのクライアントとして開き、直接ディスプレイを占有する
compositor用プラットフォームを継承しません。プレビューの重複起動はロックで拒否します。

配布物は自作バイナリー、QML、ビルド情報、全ソース、検査結果です。
SDKやV1の共有ライブラリ、boot/rootfsイメージは同梱しません。
Windowsでは同梱WINDOWS-STAGE28.mdのコードをPowerShellへ直接貼る方式を使います。
管理者権限、追加ドライバー、.ps1の実行、時計側への開発SDK導入は不要です。

## 残る実機確認

QEMUのオフスクリーン検査は、実機のWayland/EGL/入力/表示速度やサスペンドを保証しません。
ライブGUIセッションの自動検出とUID変更の実機確認もこれからです。
まずチェック出力と画面を記録し、失敗時は既存GUIを停止せず、その出力で原因を絞ります。
OS全体のランチャー置換、通知/表冠/既存アプリとの統合、スピーカー無効化は後の段階です。

公式参考: https://wiki.asteroidos.org/index.php/Installing_the_SDK

## Linux x86_64で再ビルドする場合

Python3、tar、xz、file、debugfs、readelfを用意して、リポジトリまたはソースZIPのルートで実行します。
SDKは作業フォルダーへ配置され、Windowsや時計へインストールするものではありません。

```sh
python3 stage28/fetch_inputs.py stage28-work
python3 stage28/prepare_sdk.py stage28-work
bash stage28/build.sh
python3 stage28/prepare_runtime.py stage28-work
python3 stage28/check_native.py stage28-work stage28-artifacts
python3 stage28/package.py stage28-artifacts
```

GUIセッションのソケット検査にはAF_UNIXの作成が許可されたLinux環境が必要です。
