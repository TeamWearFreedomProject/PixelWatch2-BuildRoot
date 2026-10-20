# Stage 22 Windows capture, using interactive commands

Extract the successful Stage 22 artifact next to fastboot.exe. In the
platform-tools PowerShell window, compare the image hash with boot-report.json
and SHA256SUMS. This prints every hash digit, without a table truncation:

```powershell
(Get-FileHash .\boot-stage22.img -Algorithm SHA256).Hash
```

Keep two PowerShell windows open in that directory. Paste the entire next
block into the first window. It writes stage22-serial.log, waits up to 180
seconds for COM5, opens it, and sends read-only Linux diagnostics after one
second of reading. It stops on disconnect or after 85 seconds connected.
It never changes Windows execution policy. The Stage 20 userspace banner
is expected; the new kernel must identify itself as build #22.

If COM5 has changed, replace only the PortName value with the observed port.
The normal Stage 20 USB serial device used COM5 on the tested PC.

```powershell
$serial = New-Object System.IO.Ports.SerialPort
$serial.PortName = 'COM5'
$serial.BaudRate = 115200
$serial.DtrEnable = $true
$serial.RtsEnable = $true
$serial.WriteTimeout = 1000
$writer = [System.IO.StreamWriter]::new((Join-Path $PWD 'stage22-serial.log'), $false, [System.Text.UTF8Encoding]::new($false))
$writer.AutoFlush = $true
try {
    Write-Host 'Waiting for COM5; boot the watch from the other window.'
    $deadline = (Get-Date).AddSeconds(180)
    while (-not $serial.IsOpen) {
        if ((Get-Date) -gt $deadline) { throw 'COM connection timed out' }
        try { $serial.Open() }
        catch { Start-Sleep -Milliseconds 100 }
    }
    Write-Host 'Connected; recording stage22-serial.log'
    $writer.WriteLine('HOST_CONNECTED_UTC=' + (Get-Date).ToUniversalTime().ToString('o'))
    $connected = Get-Date
    $sent = $false
    while ((Get-Date) -lt $connected.AddSeconds(85)) {
        try {
            if ($serial.BytesToRead -gt 0) {
                $chunk = $serial.ReadExisting()
                [Console]::Write($chunk)
                $writer.Write($chunk)
            }
            if (-not $sent -and (Get-Date) -gt $connected.AddSeconds(1)) {
                $serial.Write("`runame -a; cat /proc/uptime; printf '\nAURORA_STAGE22_DMESG_BEGIN\n'; dmesg; printf '\nAURORA_STAGE22_DMESG_END\n'`r")
                $sent = $true
            }
        } catch {
            $writer.WriteLine("`nHOST_SERIAL_ERROR=" + $_.Exception.Message)
            Write-Host ('Serial disconnected or failed: ' + $_.Exception.Message)
            break
        }
        Start-Sleep -Milliseconds 20
    }
} finally {
    try { if ($serial.IsOpen) { $serial.Close() } }
    finally { $serial.Dispose(); $writer.Dispose() }
}
```

After the image hash matches, with the watch in Fastboot and the physical
restart/Fastboot route available, use the second window for one temporary
boot. The device preflight established aurora, unlocked, slot b and a 64-MiB
boot capacity in Stage 21; recheck if the device state has changed.

```powershell
.\fastboot.exe boot .\boot-stage22.img
```

Save the Fastboot output and the capture file. Report whether the watch
returned to Fastboot at about the existing 90-second PID 1 deadline.
The host's 85-second capture limit does not control the watch's timer.
If automatic return fails, use the already rehearsed physical restart route.
The complete dmesg markers and any KASAN stack matter more than a console
with no visible error. This procedure does not validate charging or thermals.
