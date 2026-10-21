# PixelWatch2-BuildRoot

> スマートウォッチのスマートさを生かそう

Pixel Watch 2 Wi-Fi (`aurora`) 向けの**独立した組み込み Linux**を研究するプロジェクトです。Buildroot で最小 userspace/rootfs（ARM32とARM64の2案）を生成し、将来的に時計・タッチ操作・低消費電力・独自の丸型 UI を実装することを目指します。

**Status: Stage26 / USB復旧を最優先。** [Stage26](docs/STAGE26.md) は専用PID1・シェル・90秒ソフトウェア復帰タイマーをカーネル内蔵initramfsに組み込みます。Stage25は実機でCOMなし・自動復帰なし、強制再起動でFastbootへ復帰。原因は未確定です。

[Stage 24](docs/STAGE24.md) のGitHubビルドは成功し、ARM32のUbuntuホストrootfs（apt/dpkg）とARM64カーネルを生成済みです。

Stage 23までのBuildroot調査も保持しています。Stage 22は実機でLinux・USBシェル・Fastboot復帰を確認済みですが、Stage 24のUT成果物の実機動作は未確認です。

**Architecture:** 実機確認済みの候補は ARM64 Linux 5.15.137 + ARM32 musl/BusyBox userspaceです。64bit userspaceの代替設定も保持しますが、その実機動作は未確認です。

- 対象: Google Pixel Watch 2 Wi-Fi / `aurora`
- 直近の実機Fastboot情報: `aurora`、slot `b`、unlocked `yes`、bootloader `eos-0.4-11366482`。全パーティションのFW版は未確定です。
- Ubuntu Touchの参考FW: **TWD9.240405.001**（Android 13系）。これは**他のOSの動作保証ではありません**。
- 現在の候補は [Stage 22](docs/STAGE22.md) の `boot-stage22.img`。USBシェルと90秒後の復帰要求を備えた診断用イメージです。画面・タッチ・時計UIは未確認です。
- [Stage 23の手順](stage23/WINDOWS-CAPTURE.md) は、この候補を一時起動して表示・入力情報を取得します。rootfs単体をフラッシュするものではありません。
- パッケージ管理コマンドは未導入です。ソフトはBuildrootで選択してrootfsへ組み込みます。

## Stage plan

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
