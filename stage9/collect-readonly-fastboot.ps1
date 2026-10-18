# Stage 9 / Pixel Watch 2: READ-ONLY fastboot evidence collector.
# Does not flash, boot, erase, unlock, write partitions, or upload results.
# Never queries or stores serialno, IMEI, product identifiers or accounts.
param(
    [string]$FastbootExe = ".\fastboot.exe",
    [string]$OutputFile = "$env:USERPROFILE\aurora-fastboot-evidence.json"
)

if (-not (Test-Path -LiteralPath $FastbootExe -PathType Leaf)) {
    throw "fastboot.exe not found. Use -FastbootExe C:\path\fastboot.exe"
}

$keys = @(
    "product",
    "current-slot",
    "unlocked",
    "is-userspace",
    "version-bootloader",
    "version-baseband",
    "partition-size:boot",
    "partition-size:boot_a",
    "partition-size:boot_b",
    "partition-size:vendor_boot_a",
    "partition-size:vendor_boot_b",
    "partition-size:dtbo_a",
    "partition-size:dtbo_b"
)
$values = [ordered]@{}
foreach ($key in $keys) {
    # Some versions of fastboot print getvar replies to stderr.
    $lines = & $FastbootExe getvar $key 2>&1 |
        ForEach-Object { $_.ToString() }
    $pattern = '^\s*(?:\(bootloader\)\s*)?' +
        [Regex]::Escape($key) + ':\s*(.*?)\s*$'
    foreach ($line in $lines) {
        if ($line -match $pattern) {
            $values[$key] = $Matches[1].Trim()
            break
        }
    }
}
if ($values["product"] -ne "aurora") {
    throw "Expected aurora. Got '$($values['product'])'. No evidence written."
}
$dir = Split-Path -Parent $OutputFile
if ($dir -and -not (Test-Path -LiteralPath $dir)) {
    throw "Output directory does not exist: $dir"
}
$values | ConvertTo-Json -Depth 3 | Set-Content -LiteralPath $OutputFile -Encoding UTF8
Write-Host "Read-only fastboot evidence saved to: $OutputFile"
Write-Host "No serial number was queried, and no device partition was changed."
Write-Host "This report is NOT permission to try fastboot boot."
