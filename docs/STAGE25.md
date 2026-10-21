# Stage 25: USB → Aurora UI → スピーカー無効化

最優先はUSBのシェルを取り戻すこと。Windowsの標準CDC ACMで接続でき、
GUIやUbuntu rootfsが起動できなくても診断できる入口を先に検証する。

この成果物は **Stage24と同じLinux 5.15.144カーネルを使うRAM上のUSB診断**。
Ubuntu Touch全体を起動するイメージではなく、USB復旧を切り分ける最初の候補。
画面が空白でも判定材料にはしない。USBのPC側認識・シェル・ログ・Fastbootへの復帰を確認する。

## 構成

- Stage24のboot/init_bootを公開artifactの固定SHA256で検証する。
- カーネルはバイト単位で同じものを再利用する。別のカーネルへ変更しない。
- Haliumのベースinitramfsを保ち、診断用PID1を追加する。
- `/init`と専用の`/aurora-stage25-init`を診断用にし、rdinitも明示する。
- boot v4のカーネル＋ramdiskを1個の一時起動イメージにまとめる。
  この端末には一時起動でramdiskが正しく渡らないという先行調査がある。
  専用rdinitで`/init`の上書きを避けるが、ramdisk自体が渡るかは未検証。
  拒否・起動しない場合は出力を記録して止め、次はカーネル内蔵initramfs方式を検討する。
- 機種専用モジュールはブートローダーが供給する現在のスロットのものを使う。
  Asteroidの`.ko`を混ぜたり、バージョン・署名検査を強制回避したりしない。
- upstreamと同じモジュール一覧を使い、読み込み成否をRAMに記録する。
- Google USB shimに明示的な`usb_force_disable_boot=0`を渡し、既知の`force_disable`
  属性がある場合に0を設定する。調べたソースではパラメーター既定値もfalseなので、
  これが従来のUSB不通の原因だったとは断定しない。
- UDCが1つ登録されたらCDC ACMを構成する。他のgadgetがUDCを所有している場合は奪わない。
- PID1開始から90秒の独立したソフトウェアタイマーでFastbootへの再起動を要求する。
  USBやモジュール読み込みが待ち状態でもタイマーの子プロセスは別に動く。
  **ハードウェアwatchdogではない。PID1が実行されない・カーネルが停止した場合は効かない。**

診断処理はuserdata・system・superをマウントせず、Haliumのfsck・resize・rootfs起動も呼ばない。
rootfsへ進まないためusb-modedやAndroid initとのconfigfs競合を避けて切り分けられる。
この診断シェルは開発用のrootシェルで認証なし。常用イメージにはそのまま採用しない。

## 実機で試す手順

artifact ZIPを展開し、`boot-stage25-usb.img`、`SHA256SUMS`、生成された
**`WINDOWS-CAPTURE.md`** を使う。手順はPowerShellへ直接貼る方式。
管理者権限・追加ドライバー・`.ps1`実行・実行ポリシー変更は不要。

1. WatchをFastbootにする。現在のスロットや既存のboot/init_boot/vendor_kernel_bootは変更しない。
2. `WINDOWS-CAPTURE.md`の受信ブロックを先に貼る。接続前後に増えたCOMポートを1つだけ選ぶ。
3. 別ウィンドウで同文書のSHA256照合付き`fastboot boot`ブロックを実行する。
4. `stage25-usb.log`、COMポートが現れたか、約90秒後にFastbootに戻ったかを記録する。
   一時起動の拒否・エラー・USBが出ない場合も、その出力と状態を記録する。

**flash・erase・set_active・パーティション変更は行わない。**
`fastboot boot`で受け入れられなかったときに、代わりにflashしない。
Stage24の通常UTイメージにはこの90秒タイマーは追加されない。

## 判定と次の作業

| 結果 | 意味と次の作業 |
|---|---|
| COMが出て`AURORA_STAGE25_END`まで取得 | このUTカーネルと現在のvendor modulesで早期USBシェル成立。次はUT通常起動後も維持する構成へ進む |
| COMが出たが収集が途中 | シェル・モジュール・転送のログで停止箇所を確認する |
| COMなし、Fastbootへ復帰 | PID1やタイマーが動いた可能性はあるがUSB原因は未確定。UDC/module/bootloader経路を追加調査する |
| 一時起動拒否、または復帰なし | boot v4のramdisk受け渡し・モジュール互換性・カーネル停止を含め未確定。書き込みに切り替えず結果を確認する |

USBの完成条件は、通常UT起動でもPCに認識されシェルへ接続でき、GUI停止時にも
診断できること。今回のRAM診断が成功しても、この完成条件を達成したとは扱わない。
Aurora UIとスピーカー無効化はその後に進める。

## 参照

- [Stage24 PR / 固定ビルド](https://github.com/TeamWearFreedomProject/PixelWatch2-BuildRoot/pull/24)
- [UT port](https://gitlab.com/ubports/porting/community-ports/android13/google-eos/google-eos/-/tree/d2b4512ed1758b5ad73118cd311e2fca32f39cf5)
- [Android vendor bootとramdiskの構成](https://source.android.com/docs/core/architecture/partitions/vendor-boot-partitions)
- [Linux ACM gadget](https://docs.kernel.org/usb/gadget-testing.html)

- [Pixel Watch 2の先行調査・bootloader issues](https://github.com/argosphil/aurora#bootloader-issues)
