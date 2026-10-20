param([Parameter(Mandatory=$true)][ValidatePattern('^COM[0-9]+$')][string]$Port)
$ErrorActionPreference = 'Stop'
$serial = New-Object System.IO.Ports.SerialPort $Port,115200,None,8,One
$serial.DtrEnable = $true
$serial.RtsEnable = $true
$serial.ReadTimeout = 200
$serial.WriteTimeout = 1000
$oldControlC = [Console]::TreatControlCAsInput
try {
    $serial.Open()
    [Console]::TreatControlCAsInput = $true
    Write-Host "Connected to $Port. Ctrl+] closes this terminal. The watch requests restart at its 90-second deadline."
    $serial.Write("`r")
    while ($serial.IsOpen) {
        if ($serial.BytesToRead -gt 0) { [Console]::Write($serial.ReadExisting()) }
        if ([Console]::KeyAvailable) {
            $key = [Console]::ReadKey($true)
            if ([int]$key.KeyChar -eq 29) { break }
            $serial.Write([string]$key.KeyChar)
        }
        Start-Sleep -Milliseconds 20
    }
} finally {
    if ($serial.IsOpen) { $serial.Close() }
    $serial.Dispose()
    [Console]::TreatControlCAsInput = $oldControlC
}
