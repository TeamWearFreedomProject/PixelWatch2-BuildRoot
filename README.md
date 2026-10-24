# PixelWatch2-BuildRoot

> スマートウォッチのスマートさを生かそう

Pixel Watch 2 Wi-Fi (`aurora`) 向けに、**AsteroidOSを土台にした独自の丸型Aurora UI**を作るプロジェクトです。HarmonyOSとColorOS for Watchの方向を参考に、時計・タッチ操作・低消費電力を考えたUIを目指します。以前のBuildrootとUbuntu Touchによる調査も履歴として保持しています。

**Status: Stage28 / V1向けARM32独立プレビュー。** 実機のBUILD_ID、32bit userspace、Qt 6.11.3、ランチャー版が公開V1と一致しました。[Stage28](docs/STAGE28.md)は公式SDKでARM32版を作り、V1ライブラリを使って実行・描画を検査します。実機のGUIセッションを検出して、そのユーザーで独立アプリを開く方式です。実機GUIの初試験はこれからです。

[Stage27](docs/STAGE27.md)のColorOS for Watch/HarmonyOSに着想を得た独自QMLを使用します。USB・Wi-Fi・Bluetoothの動作実績があるAsteroidOSのランチャーを残し、置換や自動起動設定は行いません。

Stage25/26はどちらも実機でCOMなし・自動Fastboot復帰なしでした。停止箇所は未確定で、これらの診断イメージの再試行は中止します。以前のBuildroot/UT調査は履歴として保持します。

[Stage 24](docs/STAGE24.md) のGitHubビルドは成功し、ARM32のUbuntuホストrootfs（apt/dpkg）とARM64カーネルを生成済みです。

Stage 23までのBuildroot調査も保持しています。Stage 22は実機でLinux・USBシェル・Fastboot復帰を確認済みですが、Stage 24のUT成果物の実機動作は未確認です。

**Architecture:** 現在のAsteroidOSではARM64 Linux 5.15.144が実機起動しています。実機のgetconfは32、qtbase/qtdeclarativeは6.11.3-r0で、公開V1のARM32パッケージ構成と一致しました。以前のStage22はARM64 Linux 5.15.137 + ARM32 musl/BusyBoxの診断環境でした。

- 対象: Google Pixel Watch 2 Wi-Fi / `aurora`
- 以前の実機Fastboot情報: `aurora`、slot `b`、unlocked `yes`、bootloader `eos-0.4-11366482`。現在のV1環境では再確認していません。全パーティションのFW版は未確定です。
- Ubuntu Touchの参考FW: **TWD9.240405.001**（Android 13系）。これは**他のOSの動作保証ではありません**。
- 現在の基準は[ユーザーのAsteroidOS V1](https://github.com/TeamWearFreedomProject/Pixel-Watch-2-Asteroid-OS-Beta/releases/tag/V1)。[Stage22](docs/STAGE22.md)のUSBシェルは以前の診断環境として保持します。
- [Stage 23の手順](stage23/WINDOWS-CAPTURE.md) は、この候補を一時起動して表示・入力情報を取得します。rootfs単体をフラッシュするものではありません。
- 現方針ではAsteroidOS標準のopkgを使用します。Ubuntuのaptを導入したものではありません。以前のBuildroot rootfsにはパッケージ管理コマンドを導入していません。

## Current plan

1. 実機で動作したAsteroidOS V1一式をSHA256で固定し、Qtと起動セッションを把握する。
2. 既存ランチャーを残して独立したAurora UIデモを試し、時計・ハニカム一覧・操作カードを調整する。
3. 既存アプリ、通知、表冠、消灯/復帰との統合を進め、その後スピーカーを無効化する。

## Historical Buildroot plan

1. **Buildroot rootfs**: ARM32（優先）とARM64の musl + BusyBox + init を選択してビルドし、`rootfs.cpio.gz` と `rootfs.tar`、BusyBoxのELF種別を検証する。
2. **Kernel + initramfs**: 既存のAurora Linux 5.15実験を調査し、互換性を確認。特に組み込みinitramfsと起動ヘッダーv4の制約。
3. **Boot diagnostics**: USBログ・pstore・画面により起動状態を検証。実機検証は情報を揃えてから、可能なら一時起動を優先。
4. **Display & touch**: DTB/DTBOのボードIDやパネル差異を解析し、対応ドライバーを検証。
5. **Watch UI**: HarmonyOSに着想を得た**オリジナル**の丸型UIを設計（公式コード・画像の複製はしない）。

## Build locally (Linux host)

Buildroot **2025.02.1** に固定して初期実験を行います。

```bash
git clone https://github.com/TeamWearFreedomProject/PixelWatch2-BuildRoot.git
cd PixelWatch2-BuildRoot
git clone --depth 1 --branch 2025.02.1 https://github.com/buildroot/buildroot.git
make -C buildroot BR2_EXTERNAL="$PWD" O="$PWD/output" aurora_arm32_defconfig
make -C buildroot O="$PWD/output" -j2
ls -lh output/images/rootfs.*
```

64bitの代替検証では `aurora_minimal_defconfig` を選んで、**別のoutputディレクトリ**にビルドしてください。GitHub ActionsはPRではARM32、手動実行ではアーキテクチャを選択できます。

`rootfs.cpio.gz` は将来の内蔵initramfs検証向け、`rootfs.tar` は内容検査向けです。**どちらもフラッシュ用のboot.imgではありません。**

CI: [.github/workflows/build-rootfs.yml](.github/workflows/build-rootfs.yml) （手動実行、およびPRでの検証）

## Reference notes / credits

See [docs/PORTING_NOTES.md](docs/PORTING_NOTES.md) for the evidence and compatibility warnings.

- AsteroidOS research: [argosphil/aurora](https://github.com/argosphil/aurora) — kernel config, bootloader/ramdisk behavior, framebuffer and USB findings.
- Ubuntu Touch community port: [UBports google-eos](https://gitlab.com/ubports/porting/community-ports/android13/google-eos/google-eos) — TWD9 base firmware and partition details.
- [Buildroot manual](https://buildroot.org/downloads/manual/manual.html) — BR2_EXTERNAL and rootfs construction.
- Pixel Watch 2 DTB/DTBO research: owner-provided firmware binary analysis (not redistributed here).

Original upstream code, if incorporated in the future, must retain its copyright and license notices. This project does not imply endorsement by any upstream author.

**Developer/project direction:** TeamWearFreedomProject. The research and scaffolding were prepared with ChatGPT assistance, with real-device testing controlled by the project owner.
