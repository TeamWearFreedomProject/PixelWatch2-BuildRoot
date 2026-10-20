#!/usr/bin/env python3
"""Generate a Windows paste-only capture using short, complete shell commands."""
import argparse
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def commands():
    result = [s for s in (HERE / 'inventory.sh').read_text().splitlines()
              if s.strip() and not s.startswith('#')]
    if not result or any(len(s.encode()) > 1024 for s in result):
        raise ValueError('Guest commands must be complete lines of at most 1024 bytes')
    return result


def render():
    payload = json.dumps(commands(), indent=2)
    prefix = '''# Stage 23: Windowsから画面・タッチの状態を取得

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
'''
    suffix = '''
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
            if ($recent -match '(?m)^AURORA_STAGE23_END\\r?$') { $complete = $true; break }
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
if ((Get-FileHash .\\boot-stage22.img -Algorithm SHA256 -ErrorAction Stop).Hash -eq 'b843667c765bad061410118c47a5956314331ae263397ab4f655782df1f00a2a') {
    .\\fastboot.exe boot .\\boot-stage22.img
} else {
    throw 'SHA256 mismatch'
}
```

**stage23-display.log** を返してください。画面に何が出ていたかと、Fastbootへ戻ったかも記録してください。
収集終了でPCの接続は閉じますが、Watchの90秒タイマーはそのまま動きます。
ファイルには表示/入力ノード、DTの限定したプロパティ、dmesgが含まれます。
表示デバイスの存在だけでは点灯やタッチ動作の成功とは判定しません。
'''
    return prefix + payload + suffix


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    path = HERE / 'WINDOWS-CAPTURE.md'
    output = render()
    if args.check:
        if path.read_text() != output:
            raise SystemExit('WINDOWS-CAPTURE.md differs; regenerate it')
    else:
        path.write_text(output)


if __name__ == '__main__':
    main()
