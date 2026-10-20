param(
    [string]$Fastboot = '.\fastboot.exe',
    [string]$Image = '.\boot-stage20.img',
    [string]$Output = '.\stage21-preflight.json'
)
$ErrorActionPreference = 'Stop'
$exe = (Resolve-Path $Fastboot).Path
function Read-Variable([string]$Name) {
    $info = New-Object System.Diagnostics.ProcessStartInfo
    $info.FileName = $exe
    $info.Arguments = "getvar $Name"
    $info.UseShellExecute = $false
    $info.RedirectStandardOutput = $true
    $info.RedirectStandardError = $true
    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $info
    [void]$process.Start()
    $stdout = $process.StandardOutput.ReadToEndAsync()
    $stderr = $process.StandardError.ReadToEndAsync()
    if (-not $process.WaitForExit(8000)) {
        $process.Kill()
        throw "No fastboot response for $Name. Check the cable and bootloader mode."
    }
    $text = $stdout.Result + "`n" + $stderr.Result
    $pattern = '(?m)^\s*(?:\(bootloader\)\s*)?' + [regex]::Escape($Name) + ':\s*([^\r\n]*)'
    if ($process.ExitCode -eq 0 -and $text -match $pattern) { return $Matches[1].Trim() }
    return $null
}
$device = [ordered]@{}
foreach ($key in @('product','current-slot','unlocked','is-userspace','version-bootloader','version-baseband','partition-size:boot','partition-size:boot_a','partition-size:boot_b','max-download-size')) {
    $device[$key] = Read-Variable $key
}
$file = Get-Item $Image
$capacity = $null
$sizeText = $device['partition-size:boot']
if ($device['current-slot'] -in @('a','b')) {
    $slotSize = $device['partition-size:boot_' + $device['current-slot']]
    if ($slotSize) { $sizeText = $slotSize }
}
if ($sizeText -match '^0x[0-9a-fA-F]+$') {
    $capacity = [Convert]::ToInt64($sizeText.Substring(2),16)
}
$checks = [ordered]@{
    product_aurora = ($device['product'] -eq 'aurora')
    unlocked = ($device['unlocked'] -eq 'yes')
    bootloader_mode = ($device['is-userspace'] -eq 'no')
    slot_known = ($device['current-slot'] -in @('a','b'))
    historical_twd9_bootloader = ($device['version-bootloader'] -eq 'eos-0.4-11366482')
    size_fits = ($null -ne $capacity -and $file.Length -le $capacity)
}
$report = [ordered]@{
    stage = 21
    captured_utc = (Get-Date).ToUniversalTime().ToString('o')
    device = $device
    image_bytes = $file.Length
    image_sha256 = (Get-FileHash $Image -Algorithm SHA256).Hash.ToLowerInvariant()
    checks = $checks
    device_commands = 'getvar only; no boot, flash, erase or slot change'
    physical_recovery_rehearsed = 'NOT_RECORDED'
    runtime_safety = 'NOT_TESTED'
}
$report | ConvertTo-Json -Depth 6 | Set-Content -Encoding UTF8 $Output
$checks | Format-Table -AutoSize
Write-Host "Saved $Output. Review these current values before any temporary boot."
Write-Host 'Unknown or different firmware means review; do not downgrade firmware to make this report pass.'
