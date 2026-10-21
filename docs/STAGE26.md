# Stage26: カーネル内蔵initramfsでUSB診断の入口を作る

優先順位は **USB復旧 → Aurora UI → スピーカー無効化**。

Stage25の実機結果は、**COM認識なし、90秒後もFastbootへ自動移行せず、
強制再起動でFastbootへ復帰**。診断PID1・タイマーの実行は確認できていない。
USB設定だけの問題とは断定しない。外付けramdiskの受け渡し不具合または、
それ以前のカーネル起動停止などが候補であり、原因確定ではない。

## Stage25から変える点

- Stage24と同じ固定カーネルソース・Clangを使い、カーネルを再ビルドする。
  バイナリーはStage24/25と同一ではない。
- `CONFIG_INITRAMFS_SOURCE`へ専用CPIOを指定し、実際の最終vmlinuxとARM64 Imageに
  CPIOが入っていることをバイト比較で検証する。
- 専用のstatic ARM64 Cプログラム `/aurora26/pid1` を直接起動する。
  **シェルやUSB設定より先に、別プロセスで90秒タイマーを開始する。**
- static BusyBoxとすべてのスクリプト・コマンドへのリンクを `/aurora26` 内に置く。
  Android側の `/init` や `/bin/sh`、動的ライブラリーに依存しない。
- カーネル組み込みcmdlineとbootヘッダーの両方で専用rdinitを指定する。
- boot v4は**カーネルのみ、外付けramdisk 0 bytes**。
  `init_boot`など既存のパーティションは書き換えない。
- 機種専用モジュールはブートローダーが供給する現在のスロットのものを使う。
  別リリースの`.ko`は同梱せず、互換性検査の強制回避もしない。
  その実機でのモジュール互換性はまだ未確認。

カーネルの生成済み`.config`だけを変更し、固定したカーネルソース自体は編集しない。
Stage24設定との差分はinitramfsと専用cmdlineに限定して、コンパイル前と配布前の両方で検査し、kernel releaseも照合する。
staticヘルパーは別ジョブで生成し、ARM64 libc開発用sysrootがカーネルの自動判定へ影響しないよう分離する。
汎用ビルドツールへ挿入する設定フックは`stage26/hook.py`で明示する。

## 配布前の実行検証

最終boot.imgから取り出したカーネルを、ディスクを接続しないARM64 QEMUで起動する。
外付けの`/init`と`/bin/sh`には意図的に競合するファイルを与え、専用PID1とシェルの起動、
実際の90秒タイマー、再起動要求、仮想マシンの再起動による終了を確認する。
この検証に失敗した場合、実機用artifactの公開ステップへ進まない。
`CI-INPUT` / `UNTESTED`と付いたartifactはビルド・デバッグ用であり、実機手順の対象は
`aurora-stage26-EMBEDDED-USB-DIAGNOSTIC`だけ。

**QEMUで検証できるのは起動処理・タイマーまで。WatchのUSB、vendor modules、
Fastboot復帰の実機動作を証明するものではない。** ハードウェアwatchdogではないため、
PID1に到達しない場合やカーネル停止時には90秒タイマーも効かない。

## 実機での手順

artifact ZIPを展開し、同梱の`WINDOWS-CAPTURE.md`に従う。
管理者権限や`.ps1`実行を必要としない、PowerShellへの直接貼り付け方式。
前のStage25とはイメージ名・ハッシュ・ログ名が違う。

1. WatchがFastbootにいる状態で、`fastboot.exe`のあるフォルダーへZIPの中身を置く。
2. PowerShellを2つ開く。最初の画面で受信コードを先に実行する。
3. もう一方で同文書のハッシュ照合付き`fastboot boot`を実行する。
4. `stage26-usb.log`と、COMが出たか・自動でFastbootへ戻ったかを記録する。
   起動拒否やエラーもそのまま記録する。

**flash・erase・set_active・パーティション操作は行わない。**
診断処理はuserdata/system/superをマウントせず、fsck・resize・UT rootfs起動を呼ばない。
画面表示は判定対象にしない。

COMが出れば、PID1からUSBまでのログで通常UT起動へのUSB接続を設計する。
COMがなくても自動復帰できれば、前回とは異なり診断起動処理が進んだ可能性を評価できる。
両方ない場合も、カーネル停止や起動経路の問題を含めて確認し、同じ試行を繰り返さない。

この診断シェルは開発用の認証なしrootシェル。通常UT起動後のUSB復旧、Aurora UI、
スピーカー無効化は今回の成果物ではまだ完了しない。Stage24通常イメージにもタイマーは付かない。

## 参照

- [Stage25の実機結果](../stage26/stage25-hardware-result.json)
- [Pixel Watch 2のramdisk問題](https://github.com/argosphil/aurora#bootloader-issues)
- [Linux early userspace / CONFIG_INITRAMFS_SOURCE](https://docs.kernel.org/driver-api/early-userspace/early_userspace_support.html)
