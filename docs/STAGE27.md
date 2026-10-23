# Stage 27: AsteroidOS V1を土台にしたAurora UI初版

Stage25/26は実機でCOM接続も自動Fastboot復帰も確認できませんでした。
一方、ユーザーが自分でビルドしたAsteroidOS V1はUSB・Wi-Fi・Bluetoothが動作し、
今回もGUIの言語選択画面、ADB接続、以下のunameが報告されています。

```
Linux aurora 5.15.144 #1 SMP PREEMPT Sun Mar 30 15:32:43 UTC 2025 aarch64 GNU/Linux
```

ここからはV1を動作実績のある基準にします。実行中パーティションのハッシュは
読み戻していないため、公開V1の4イメージ全てとのバイト一致は未証明です。
CIは公開V1のrootfs/boot/init_boot/vendor_kernel_bootをサイズとSHA256で照合し、
rootfsをdebugfsで読み取ってQt・ランチャー・opkg・サービス構成を記録します。
画像をmountしたり、イメージ内のプログラムを実行したりはしません。

## デザイン

ユーザーの希望により、HarmonyOS風に加えてColorOS for Watchの方向も反映します。
OPPO公式の製品紹介を参考に、Aurora UIとして独自に描くデザインです。

- 黒い背景、大きな数字、明るいアクセントカラー。
- 円形のアプリアイコンを7個のハニカム配置にする。
- 設定や操作部は余白のある角丸カードとカプセル型ボタン。
- 押したときの縮小と短いフェード/拡大遷移。重い常時ぼかしは使わない。
- 丸い384px画面の内側に主要な操作を配置。拡大縮小にも追従する。
- 純正OPPO/Huaweiのコード、ロゴ、アイコンや画像は複製しない。

参考: https://www.oppo.com/cn/accessories/oppo-watch-4-pro/

## 初版の範囲

`stage27/qml/Main.qml`は独立したQt Quickウィンドウです。QtQuick 2.12と
QtQuick.Window 2.12だけを使用し、独自のCanvasアイコンを描きます。
既存のasteroid-launcherを停止・上書きせず、systemdや起動イメージも変更しません。

時計、ハニカム一覧、ストップウォッチ、タイマー、電卓、白いライト画面、
アクセント/アニメーション設定を試せます。設定はプロセス内だけに保持します。
ストップウォッチ/タイマーはデモのプロセスが生きている間だけ動きます。
サスペンドをまたぐ精度、バックグラウンド通知、実機の消費電力は未検証です。
終了通知は画面表示だけで、音声APIは呼びません。
これはOS全体のスピーカー無効化を実現したものではありません。

Wi-Fi/Bluetooth/健康データの架空の状態表示や通信トグルは用意しません。
既存AsteroidOSのアプリ起動、通知、表冠、画面消灯や復帰との統合は次の段階です。
Qt Quick Testで画面遷移・計時・電卓・設定変更を検査し、デスクトップの
ソフトウェア描画でPNGを生成します。実機上の表示・速度は別途確認が必要です。

## 最初に実機から読み取る情報

ADBで時計のシェルに入った状態で、以下を実行して出力を記録します。
状態を読むだけで、設定・起動サービスを変更しません。

```sh
cat /etc/os-release
getconf LONG_BIT
id
command -v qmlscene
command -v qml
opkg list-installed | grep -E 'asteroid-launcher|qml-asteroid|qtbase|qtdeclarative|qtwayland'
ps -eo user,pid,args | grep -E 'asteroid-launcher|lipstick|qmlscene'
```

`uname -m`のaarch64はカーネルの情報です。userspaceの32/64bitはそれだけでは
判定しません。V1のQt版、QML実行ファイル、GUIセッションの実ユーザーと環境を
確かめてから、独立デモの実機起動コマンドを決めます。rootシェルに
`WAYLAND_DISPLAY`や`XDG_RUNTIME_DIR`を推測で設定しません。
公開rootfsの静的解析結果と、現在動いている実機の出力は区別します。

## ローカルでデスクトップ試験

Qt 5.12以降とQt Quick Test、QtQuick/WindowのQMLモジュールを用意します。

```sh
mkdir -p stage27-artifacts
QT_QUICK_BACKEND=software qmltestrunner -input stage27/tests
qmlscene stage27/qml/Main.qml
```

配布ZIPはQMLと説明書・照合情報だけです。boot/rootfsイメージは含みません。
フラッシュ、パーティション変更、Stage26の再試行は必要ありません。
GitHubでのOS全体の再ビルドもこの段階では行いません。

優先順位: V1の通信環境を確保 → Aurora UI → スピーカー無効化。
AsteroidOS標準のopkgを使います。Ubuntuのネイティブaptを追加したものではありません。
