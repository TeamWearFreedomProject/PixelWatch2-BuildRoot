# Stage 24: GitLabのUbuntu TouchポートをGitHub Actionsでビルド

Pixel Watch 2向けのUBports `google-eos` ポートをGitLabから取得し、GitHub Actions上でビルドします。ホストのパッケージ管理はARM32版の`apt` / `dpkg`です。UIはこの段階では既存のLomiriです。

## 成果物

- `aurora-stage24-UT-ADAPTATION`: 今回ビルドした`boot.img`、`init_boot.img`、`device_eos.tar.xz`、kernel config、検査結果、入力一覧、SHA256。
- `aurora-stage24-UT-FOCAL-RW-ROOTFS`: `ubuntu.img.zst`、検査結果、入力一覧、SHA256。この圧縮ファイルを展開すると通常のraw ext4 `ubuntu.img`になります。
- `aurora-stage24-UT-*-LOGS`: 各工程のログ。ビルド失敗とrootfs組立失敗を区別できます。

`SHA256SUMS`には圧縮ファイルと展開後のイメージの両方を記録します。圧縮ファイルだけを取り出した状態では`ubuntu.img`の行の検証は展開後に行ってください。

## 入力とビルド方法

`stage24/pins.json`はポート、共通ビルドツール、カーネル、コンパイラ等のGitコミットを固定します。rootfsはUBportsのFocalジョブ394の**armhf**版、Android HALコンテナはHalium 13の**ARM32**ジョブ726です。バイナリ入力は取得後にサイズとSHA256を検証します。initramfsのARM64と、通常稼働するUbuntu userspaceのARM32を区別します。

共通ツールの現在の既定値が24.04系のため、`deviceinfo_ubuntu_touch_release="focal"`を明示して元のポートの20.04構成に合わせます。上流のヘルパーを使ってカーネルとdevice tarballをビルドし、rootfs・Haliumコンテナ・device tarballを同じ順序で組み合わせます。

rootfsの組立はループデバイスを使わず、数値UID/GIDを保持して展開したファイルツリーから`mke2fs -d`でext4を生成します。イメージ内のARMプログラムやinitスクリプトは実行しません。組立後にext4、ARM32版apt/dpkg、Haliumコンテナ、PW2用overlayを検査します。

ホストrootfsには`/.writable_image`を追加します。固定したHaliumの`mountroot`がこのマーカーを確認し、通常のread-onlyへの再マウントを省略する構成です。実機上での`apt update`・インストール成功は別途検証が必要です。

## この段階の実機対応状況

これは**UTのビルド・イメージ作成を移植したベースライン**です。Stage22のBuildrootイメージとは別のカーネル、initramfs、永続rootfsを使います。

- このStage24成果物での起動・USB列挙・画面・タッチ・Wi-Fiは未検証です。過去のUT動作報告とは分けて扱います。
- 90秒のFastboot復帰タイマーはありません。
- スピーカー無効化とAurora UIは後続の変更です。この段階では完了扱いにしません。
- `vendor_boot` / `vendor_kernel_boot` / `dtbo` / Googleのファームウェアは生成・配布しません。上流が前提にしているAndroid 13のFW・vendorモジュールとの組合せの確認が必要です。
- 上流READMEのパーティション変更手順は現在の実機向けの手順として転載しません。このPRはフラッシュやストレージ消去を行いません。

USB調査では、Stage22のCDC ACMが動いた事実、Asteroid V1のUSBゲート処理、UTの`usb-moded`・DWC3・configfsを比較します。V1のバイナリモジュールをUTカーネルへ流用する変更は含みません。

## Linuxホストでの再実行

Ubuntu 22.04のビルド依存関係はworkflowに記載しています。シェル構文とパッケージングの検証後、次の順で実行します。

```sh
python3 stage24/fetch.py --phase adaptation
bash stage24/build.sh
python3 stage24/fetch.py --phase assemble
sudo bash stage24/assemble.sh stage24-work stage24-artifacts/adaptation/device_eos.tar.xz stage24-artifacts/rootfs
```

再組立には新しい`stage24-work/rootfs`が必要です。既存ディレクトリがある場合は上書きせず停止します。OS全体の再ビルドをせずにrootfs側だけ改造する手順の土台にもなります。

## 出典

- [UBports google-eos](https://gitlab.com/ubports/porting/community-ports/android13/google-eos/google-eos) — ポートとoverlay（Apache-2.0）。
- [halium-generic-adaptation-build-tools](https://gitlab.com/ubports/porting/community-ports/halium-generic-adaptation-build-tools) — ビルド・パッケージング方式（Apache-2.0）。
- [Halium initramfs](https://github.com/Halium/initramfs-tools-halium) — init_bootのベース。各ソースとバイナリのライセンスは上流のものが適用されます。
