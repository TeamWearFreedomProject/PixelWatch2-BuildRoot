#!/usr/bin/env python3
"""Generate a hash-specific paste-only Windows capture guide after packaging."""
import json
from pathlib import Path
import sys


def render(sha):
    if len(sha) != 64 or any(c not in '0123456789abcdef' for c in sha):
        raise ValueError('Invalid image SHA256')
    return '''# Stage25 USB診断・Windows受信手順

ZIPを展開したフォルダーにplatform-toolsのfastboot.exeを用意し、PowerShellを2つ開く。
WatchがFastbootにいる間に、最初の画面へ次のブロックを直接貼る。
既存のCOMポート一覧を記録し、一時起動後に増えたCOMポートが1個の場合だけ接続する。
受信待機中は、他のシリアル機器を新しく接続しない。
管理者権限・追加ドライバー・.ps1実行は不要。

```powershell
$before = @([System.IO.Ports.SerialPort]::GetPortNames())
$serial = New-Object System.IO.Ports.SerialPort
$serial.BaudRate = 115200
$serial.DtrEnable = $true
$serial.RtsEnable = $true
$serial.ReadBufferSize = 262144
$serial.WriteTimeout = 2000
$writer = [System.IO.StreamWriter]::new((Join-Path $PWD 'stage25-usb.log'), $false, [System.Text.UTF8Encoding]::new($false))
$writer.AutoFlush = $true
$complete = $false
try {
    Write-Host 'Waiting for a new COM port; run the temporary-boot block in the other window.'
    $deadline = (Get-Date).AddSeconds(180)
    while (-not $serial.IsOpen) {
        if ((Get-Date) -ge $deadline) { throw 'No new COM port connected before deadline' }
        $added = @([System.IO.Ports.SerialPort]::GetPortNames() | Where-Object { $_ -notin $before })
        if ($added.Count -gt 1) { throw 'Multiple new COM ports; refusing to guess' }
        if ($added.Count -eq 1) {
            $serial.PortName = $added[0]
            try { $serial.Open() } catch { Start-Sleep -Milliseconds 100 }
        } else { Start-Sleep -Milliseconds 100 }
    }
    $writer.WriteLine('HOST_CONNECTED_UTC=' + (Get-Date).ToUniversalTime().ToString('o'))
    $writer.WriteLine('HOST_PORT=' + $serial.PortName)
    $serial.Write("`r")
    $deadline = (Get-Date).AddSeconds(85)
    $recent = ''
    $sent = $false
    while ((Get-Date) -lt $deadline) {
        if ($serial.BytesToRead -gt 0) {
            $chunk = $serial.ReadExisting()
            $writer.Write($chunk)
            [Console]::Write($chunk)
            $recent += $chunk
            if (-not $sent -and $recent.Contains('AURORA_STAGE25_USB_SHELL') -and $recent.Contains('aurora-stage25#')) {
                $serial.Write("sleep 5; aurora-info25`r")
                $sent = $true
            }
            if ($recent -match '(?m)^AURORA_STAGE25_END\\r?$') { $complete = $true; break }
            if ($recent.Length -gt 32768) { $recent = $recent.Substring($recent.Length - 32768) }
        }
        Start-Sleep -Milliseconds 20
    }
    if (-not $complete) { $writer.WriteLine('HOST_INCOMPLETE_CAPTURE') }
} catch {
    $writer.WriteLine('HOST_CAPTURE_ERROR=' + $_.Exception.Message)
    Write-Host $_.Exception.Message
} finally {
    try { if ($serial.IsOpen) { $serial.Close() } }
    finally { $serial.Dispose(); $writer.Dispose() }
}
Write-Host 'Saved stage25-usb.log. Record whether the watch returns to Fastboot around 90s after PID1 starts.'
```

受信待機を開始した後、2つ目の画面へ以下を貼って一時起動する。
ハッシュが違う場合やfastbootが拒否した場合は止め、その出力を記録する。

```powershell
if ((Get-FileHash .\\boot-stage25-usb.img -Algorithm SHA256 -ErrorAction Stop).Hash -eq 'IMAGE_SHA') {
    .\\fastboot.exe boot .\\boot-stage25-usb.img
} else {
    throw 'SHA256 mismatch'
}
```

`stage25-usb.log`と「COMが出たか」「Fastbootに戻ったか」を返す。
画面は診断に使わない。flash・erase・set_activeは行わない。
90秒タイマーはソフトウェアによるもので、PID1に到達しない場合やカーネル停止時には効かない。
この機種では一時起動のramdisk受け渡しに既知の問題があり、専用rdinitを指定した今回の方式も実機未検証。
通常のStage24 UTイメージには、このタイマーは入っていない。
'''.replace('IMAGE_SHA', sha)


if __name__ == '__main__':
    out = Path(sys.argv[1])
    report = json.loads((out/'audit.json').read_text())
    (out/'WINDOWS-CAPTURE.md').write_text(render(report['boot_sha256']))
