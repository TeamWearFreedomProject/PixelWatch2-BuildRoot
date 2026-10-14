# PixelWatch2-BuildRoot

> スマートウォッチのスマートさを生かそう

Pixel Watch 2 Wi-Fi (`aurora`) 向けの**独立した組み込み Linux**を研究するプロジェクトです。Buildroot で最小 userspace/rootfs（ARM32とARM64の2案）を生成し、将来的に時計・タッチ操作・低消費電力・独自の丸型 UI を実装することを目指します。

**Status: Stage 1 / rootfs build experiment. NOT BOOTABLE. DO NOT FLASH.**

**Architecture:** Wear OS/LineageOS の device tree は ARM32 (`armeabi-v7a`) userspaceを指定する一方、argosphil のLinuxカーネルは `CONFIG_ARM64=y`, `CONFIG_COMPAT=y`, `CONFIG_COMPAT_BINFMT_ELF=y`。そのため **32bit rootfsを優先的にCI検証**し、64bit rootfsも別設定として維持します。32bitの実機動作も、64bitが実機では動かないことも、まだ証明されていません。

- 対象: Google Pixel Watch 2 Wi-Fi / `aurora`
- 現在手元で使用中と申告されているFW: **TWD9系**（末尾の正確なビルド番号は未確認）
- Ubuntu Touchの参考FW: **TWD9.240405.001**（Android 13系）。これは**他のOSの動作保証ではありません**。
- 現段階の成果物は汎用的な **ARM64 rootfs** のみ。カーネル・DTB/DTBO・起動イメージは同梱しません。
- GitHub Actionsでの生成物は研究・検証用であり、実機にフラッシュしないでください。

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
