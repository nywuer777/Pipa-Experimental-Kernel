# EXP24 / E404 - USB Ethernet A/B evidence v3 (read-only)
# Windows PowerShell 5.1+; requires a working ADB connection (wireless if USB-C is occupied).
# Avoid Android shell loops, parentheses and regex: adb.exe can strip nested quotes on Windows.
[CmdletBinding()]
param(
    [string]$Adb = 'C:\platform-tools\adb.exe',
    [string]$Serial = '',
    [ValidateSet('E404','EXP24')][string]$Stage = 'E404',
    [string]$OutDir = '.\exp24-usb-ethernet-evidence'
)

$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $Adb -PathType Leaf)) {
    throw "ADB executable not found: $Adb"
}

$adbArgs = @()
if ($Serial -ne '') { $adbArgs += @('-s', $Serial) }
try {
    $state = (& $Adb @adbArgs get-state 2>&1 | Out-String).Trim()
} catch {
    throw "ADB connection failed: $($_.Exception.Message)"
}
if ($LASTEXITCODE -ne 0 -or $state -ne 'device') {
    throw "ADB target unavailable ($state). Run 'adb devices -l' and use -Serial if needed."
}

New-Item -ItemType Directory -Path $OutDir -Force | Out-Null
$lines = New-Object 'System.Collections.Generic.List[string]'
[void]$lines.Add('# EXP24 Ethernet A/B read-only evidence v3')
[void]$lines.Add("# Stage=$Stage")
[void]$lines.Add("# Captured=$(Get-Date -Format o)")
[void]$lines.Add("# ADB device=$state")

function Invoke-Probe {
    param(
        [Parameter(Mandatory=$true)][string]$Title,
        [Parameter(Mandatory=$true)][string[]]$ShellArgs
    )
    [void]$lines.Add('')
    [void]$lines.Add("======== $Title ========")
    # Each ADB invocation has plain shell words, not nested quotes/loops/pipes.
    # Android can refuse optional sysfs or /proc reads; record and continue.
    $previousPreference = $ErrorActionPreference
    $captured = @()
    $exitCode = -1
    try {
        $ErrorActionPreference = 'Continue'
        $captured = @(& $Adb @adbArgs shell @ShellArgs 2>&1 | ForEach-Object { $_.ToString() })
        $exitCode = $LASTEXITCODE
    } catch {
        $captured += "PowerShell/ADB exception: $($_.Exception.Message)"
    } finally {
        $ErrorActionPreference = $previousPreference
    }
    if ($captured.Count -eq 0) {
        [void]$lines.Add('(empty or not accessible)')
    } else {
        foreach ($line in $captured) { [void]$lines.Add([string]$line) }
    }
    [void]$lines.Add("exit_code=$exitCode")
    if ($exitCode -ne 0) {
        [void]$lines.Add('NOTE: optional read failed; continuing without root.')
    }
    return $captured
}

# Kernel identity: do not group commands using remote shell parentheses.
Invoke-Probe -Title 'kernel / uname -a' -ShellArgs @('uname', '-a') | Out-Null
Invoke-Probe -Title 'kernel / uname -r' -ShellArgs @('uname', '-r') | Out-Null
Invoke-Probe -Title 'kernel / proc version' -ShellArgs @('cat', '/proc/version') | Out-Null
Invoke-Probe -Title 'kernel / device name' -ShellArgs @('getprop', 'ro.product.device') | Out-Null

# Enumerate actual USB sysfs entries locally in PowerShell; avoid -r filters in Android shell.
$usbEntries = @(Invoke-Probe -Title 'USB / sysfs entries' -ShellArgs @('ls', '-1', '/sys/bus/usb/devices'))
$usbDevices = @($usbEntries | ForEach-Object { $_.Trim() } |
    Where-Object { $_ -match '^\d+-\d+(?:\.\d+)*$' } | Select-Object -Unique)
$usbInterfaces = @($usbEntries | ForEach-Object { $_.Trim() } |
    Where-Object { $_ -match '^\d+-\d+(?:\.\d+)*:\d+\.\d+$' } | Select-Object -Unique)
[void]$lines.Add("USB device paths found=$($usbDevices.Count); interfaces found=$($usbInterfaces.Count)")

foreach ($device in $usbDevices) {
    $base = "/sys/bus/usb/devices/$device"
    foreach ($field in @('idVendor','idProduct','bDeviceClass','bDeviceSubClass',
                         'bDeviceProtocol','bConfigurationValue','manufacturer','product')) {
        Invoke-Probe -Title "USB $device / $field" -ShellArgs @('cat', "$base/$field") | Out-Null
    }
    Invoke-Probe -Title "USB $device / device driver" -ShellArgs @('ls', '-l', "$base/driver") | Out-Null
}

foreach ($iface in $usbInterfaces) {
    $base = "/sys/bus/usb/devices/$iface"
    foreach ($field in @('bInterfaceClass','bInterfaceSubClass','bInterfaceProtocol')) {
        Invoke-Probe -Title "USB interface $iface / $field" -ShellArgs @('cat', "$base/$field") | Out-Null
    }
    Invoke-Probe -Title "USB interface $iface / bound driver" -ShellArgs @('ls', '-l', "$base/driver") | Out-Null
}

# Network and Android service views. Failure of one diagnostic is not a kernel failure.
Invoke-Probe -Title 'network / interfaces in sysfs' -ShellArgs @('ls', '-l', '/sys/class/net') | Out-Null
Invoke-Probe -Title 'network / ip link' -ShellArgs @('ip', 'link', 'show') | Out-Null
Invoke-Probe -Title 'network / IPv4 addresses' -ShellArgs @('ip', '-4', 'address', 'show') | Out-Null
Invoke-Probe -Title 'network / IPv4 routes' -ShellArgs @('ip', '-4', 'route', 'show') | Out-Null
Invoke-Probe -Title 'Android / Ethernet service' -ShellArgs @('dumpsys', 'ethernet') | Out-Null
Invoke-Probe -Title 'kernel / proc config if allowed' -ShellArgs @('ls', '-l', '/proc/config.gz') | Out-Null

$filename = 'exp24-usb-{0}-{1}.txt' -f $Stage, (Get-Date -Format 'yyyyMMdd-HHmmss')
$out = Join-Path (Resolve-Path -LiteralPath $OutDir).Path $filename
[IO.File]::WriteAllLines($out, $lines, (New-Object System.Text.UTF8Encoding($false)))
Write-Host "Read-only USB Ethernet evidence saved: $out"
Write-Host 'Inspect VID:PID, interface class/driver, network interface, IP/route and running kernel.'
