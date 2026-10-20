# Stage 23: Windowsから画面・タッチの状態を取得

使うイメージは、実機確認済みの **boot-stage22.img**。
Stage 23では新しいboot.imgを作らず、表示設定も変更しません。
管理者権限・追加ソフト・.ps1実行・実行ポリシー変更は不要です。

platform-toolsのPowerShellを2つ開き、最初の画面へ次のブロック全体を貼ってください。
COM5を待機し、シェルのバナーとプロンプトを検出してから診断コマンドを順に送ります。
ポート番号が変わった場合はPortNameを修正してください。
結果はPCの **stage23-display.log** へ保存します。
各コマンドは1024バイト以下、500ms間隔で送信します。

```powershell
$commands = @'
[
  "R=${AURORA_STAGE23_TEST_ROOT:-}; if [ -n \"$R\" ] && [ ! -f \"$R/.aurora-stage23-fixture\" ]; then printf 'Unmarked fixture rejected\\n' >&2; exit 64; fi; printf '\\nAURORA_STAGE23_BEGIN\\n'; uname -a; cat \"$R/proc/uptime\"; printf '\\nPACKAGE_MANAGERS\\n'; for c in pkg opkg apk apt apt-get dpkg rpm dnf pacman; do p=$(command -v \"$c\" 2>/dev/null); [ -z \"$p\" ] || printf '%s=%s\\n' \"$c\" \"$p\"; done",
  "printf '\\nFRAMEBUFFERS\\n'; if [ -r \"$R/proc/fb\" ]; then cat \"$R/proc/fb\"; else printf 'proc/fb unavailable\\n'; fi; for d in \"$R\"/sys/class/graphics/fb*; do [ -d \"$d\" ] || continue; printf 'FB %s\\n' \"$d\"; for a in name virtual_size bits_per_pixel stride modes; do [ ! -r \"$d/$a\" ] || { printf '%s=' \"$a\"; head -c 1024 \"$d/$a\"; printf '\\n'; }; done; done; for p in \"$R\"/dev/fb* \"$R\"/dev/dri/*; do [ ! -e \"$p\" ] || ls -l \"$p\"; done",
  "printf '\\nDRM_AND_BACKLIGHT\\n'; for d in \"$R\"/sys/class/drm/card* \"$R\"/sys/class/backlight/*; do [ -d \"$d\" ] || continue; printf 'DEVICE %s driver=' \"$d\"; readlink \"$d/device/driver\" 2>/dev/null; for a in status enabled modes brightness max_brightness actual_brightness; do [ ! -r \"$d/$a\" ] || { printf '%s=' \"$a\"; head -c 1024 \"$d/$a\"; printf '\\n'; }; done; done",
  "printf '\\nINPUT\\n'; if [ -r \"$R/proc/bus/input/devices\" ]; then cat \"$R/proc/bus/input/devices\"; else printf 'input list unavailable\\n'; fi; for d in \"$R\"/sys/class/input/event*; do [ -d \"$d\" ] || continue; printf 'EVENT %s\\n' \"$d\"; for a in name capabilities/abs; do [ ! -r \"$d/device/$a\" ] || { printf '%s=' \"$a\"; cat \"$d/device/$a\"; }; done; done",
  "printf '\\nLIVE_DISPLAY_TOUCH_DT\\n'; D=\"$R/sys/firmware/devicetree/base\"; if [ -d \"$D\" ]; then n=0; find \"$D\" -type f -name compatible | while IFS= read -r f; do v=$(tr '\\000' ' ' < \"$f\"); printf '%s\\n' \"$v\" | grep -Eiq 'mdss|dsi|sde|simple-framebuffer|touch|synaptics|focaltech|novatek|raydium|goodix|st,fts' || continue; n=$((n+1)); if [ \"$n\" -gt 80 ]; then printf 'DT_NODE_LIMIT_REACHED\\n'; break; fi; d=${f%/compatible}; printf 'DT %s\\ncompatible=%s\\n' \"${d#\"$D\"}\" \"$v\"; for a in status qcom,mdss-dsi-panel-name label; do [ ! -r \"$d/$a\" ] || { printf '%s=' \"$a\"; tr '\\000' ' ' < \"$d/$a\"; printf '\\n'; }; done; for a in reg phandle memory-region qcom,dsi-panel qcom,dsi-pref-prim-pan qcom,mdss-dsi-panel-controller qcom,mdss-dsi-panel-width qcom,mdss-dsi-panel-height qcom,mdss-dsi-bpp; do [ ! -r \"$d/$a\" ] || { printf '%s(hex)=' \"$a\"; head -c 128 \"$d/$a\" | od -An -v -tx1; }; done; done; else printf 'live DT unavailable\\n'; fi",
  "printf '\\nLIVE_PANEL_DESCRIPTIONS\\n'; if [ -d \"$D\" ]; then n=0; find \"$D\" -type f -name qcom,mdss-dsi-panel-name | while IFS= read -r f; do n=$((n+1)); if [ \"$n\" -gt 80 ]; then printf 'DT_NODE_LIMIT_REACHED\\n'; break; fi; d=${f%/*}; printf 'PANEL %s name=' \"${d#\"$D\"}\"; tr '\\000' ' ' < \"$f\"; printf '\\n'; for a in phandle qcom,mdss-dsi-bpp; do [ ! -r \"$d/$a\" ] || { printf '%s(hex)=' \"$a\"; od -An -v -tx1 \"$d/$a\"; }; done; find \"$d\" -type f \\( -name qcom,mdss-dsi-panel-width -o -name qcom,mdss-dsi-panel-height \\) | while IFS= read -r p; do printf '%s(hex)=' \"${p#\"$D\"}\"; od -An -v -tx1 \"$p\"; done; done; fi",
  "printf '\\nRESERVED_SPLASH_DT\\n'; for d in \"$R\"/sys/firmware/devicetree/base/reserved-memory/*splash* \"$R\"/sys/firmware/devicetree/base/reserved-memory/*framebuffer*; do [ -d \"$d\" ] || continue; printf 'REGION %s\\n' \"$d\"; [ ! -r \"$d/reg\" ] || od -An -v -tx1 \"$d/reg\"; done; printf '\\nDMA_HEAPS_AND_MODULES\\n'; for p in \"$R\"/dev/dma_heap/*; do [ ! -e \"$p\" ] || ls -l \"$p\"; done; [ ! -r \"$R/proc/modules\" ] || cat \"$R/proc/modules\"; if [ -r \"$R/sys/kernel/debug/devices_deferred\" ]; then cat \"$R/sys/kernel/debug/devices_deferred\"; else printf 'deferred list unavailable (debugfs not mounted by this diagnostic)\\n'; fi",
  "printf '\\nPLATFORM_BINDINGS\\n'; for d in \"$R\"/sys/bus/platform/devices/*; do f=\"$d/of_node/compatible\"; [ -r \"$f\" ] || continue; v=$(tr '\\000' ' ' < \"$f\"); printf '%s\\n' \"$v\" | grep -Eiq 'mdss|dsi|sde|simple-framebuffer|touch' || continue; printf 'PLATFORM %s compatible=%s driver=' \"${d##*/}\" \"$v\"; readlink \"$d/driver\" 2>/dev/null || printf 'UNBOUND\\n'; done",
  "printf '\\nAURORA_STAGE23_DMESG_BEGIN\\n'; if [ -n \"$R\" ]; then cat \"$R/fixture-dmesg\"; else dmesg; fi; printf '\\nAURORA_STAGE23_DMESG_END\\nAURORA_STAGE23_END\\n'"
]
'@ | ConvertFrom-Json
$serial = New-Object System.IO.Ports.SerialPort
$serial.PortName = 'COM5'
$serial.BaudRate = 115200
$serial.DtrEnable = $true
$serial.RtsEnable = $true
$serial.ReadBufferSize = 262144
$serial.WriteTimeout = 2000
$writer = [System.IO.StreamWriter]::new((Join-Path $PWD 'stage23-display.log'), $false, [System.Text.UTF8Encoding]::new($false))
$writer.AutoFlush = $true
$complete = $false
try {
    Write-Host 'Waiting for COM5; boot Stage 22 from the other window.'
    $deadline = (Get-Date).AddSeconds(180)
    while (-not $serial.IsOpen) {
        if ((Get-Date) -gt $deadline) { throw 'COM connection timed out' }
        try { $serial.Open() } catch { Start-Sleep -Milliseconds 100 }
    }
    $writer.WriteLine('HOST_CONNECTED_UTC=' + (Get-Date).ToUniversalTime().ToString('o'))
    $deadline = (Get-Date).AddSeconds(85)
    $recent = ''
    $nextCommand = 0
    $nextSend = $null
    $ready = $false
    $sawBanner = $false
    $sawPrompt = $false
    while ((Get-Date) -lt $deadline) {
        if ($serial.BytesToRead -gt 0) {
            $chunk = $serial.ReadExisting()
            $writer.Write($chunk)
            [Console]::Write($chunk)
            $recent += $chunk
            if ($recent.Contains('AURORA_STAGE20_USB_SHELL')) { $sawBanner = $true }
            if ($recent.Contains('aurora-stage20#')) { $sawPrompt = $true }
            if (-not $ready -and $sawBanner -and $sawPrompt) {
                $ready = $true
                $nextSend = (Get-Date).AddMilliseconds(500)
            }
            if ($recent -match '(?m)^AURORA_STAGE23_END\r?$') { $complete = $true; break }
            if ($recent.Length -gt 32768) { $recent = $recent.Substring($recent.Length - 32768) }
        }
        if ($ready -and $nextCommand -lt $commands.Count -and (Get-Date) -ge $nextSend) {
            $serial.Write([string]$commands[$nextCommand] + "`r")
            $nextCommand++
            $nextSend = (Get-Date).AddMilliseconds(500)
        }
        Start-Sleep -Milliseconds 20
    }
    if (-not $complete) { $writer.WriteLine('HOST_INCOMPLETE_CAPTURE'); Write-Host 'Capture incomplete; keep the log for diagnosis.' }
} catch {
    $writer.WriteLine('HOST_CAPTURE_ERROR=' + $_.Exception.Message)
    Write-Host $_.Exception.Message
} finally {
    try { if ($serial.IsOpen) { $serial.Close() } }
    finally { $serial.Dispose(); $writer.Dispose() }
}
Write-Host 'Saved stage23-display.log. The watch keeps its existing 90-second return timer.'
```

待機開始後、WatchがFastbootにいる状態で、2つ目のPowerShellへ以下を貼ります。
ハッシュが一致した場合だけ一時起動します。

```powershell
if ((Get-FileHash .\boot-stage22.img -Algorithm SHA256 -ErrorAction Stop).Hash -eq 'b843667c765bad061410118c47a5956314331ae263397ab4f655782df1f00a2a') {
    .\fastboot.exe boot .\boot-stage22.img
} else {
    throw 'SHA256 mismatch'
}
```

**stage23-display.log** を返してください。画面に何が出ていたかと、Fastbootへ戻ったかも記録してください。
収集終了でPCの接続は閉じますが、Watchの90秒タイマーはそのまま動きます。
ファイルには表示/入力ノード、DTの限定したプロパティ、dmesgが含まれます。
表示デバイスの存在だけでは点灯やタッチ動作の成功とは判定しません。
