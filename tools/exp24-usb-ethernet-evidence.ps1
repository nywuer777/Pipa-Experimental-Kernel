# EXP24 - E404 / EXP24 USB Ethernet A/B evidence (read-only, Windows PowerShell 5.1+)
# Run once with -Stage E404 and once with -Stage EXP24, only after authorized temporary boot.
# If a USB-C Ethernet adapter occupies the tablet's only port, use already-configured wireless ADB.
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
New-Item -ItemType Directory -Path $OutDir -Force | Out-Null
$adbArgs = @()
if ($Serial -ne '') { $adbArgs += @('-s', $Serial) }
& $Adb @adbArgs get-state | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'ADB target unavailable; connect to the tablet before capture.' }

$commands = @(
    @{Title='kernel'; Cmd='uname -a; cat /proc/version; (cat /proc/sys/kernel/osrelease 2>/dev/null || echo "osrelease unavailable (permission denied or absent)")'},
    @{Title='USB VID PID and driver binding'; Cmd='for d in /sys/bus/usb/devices/*; do [ -r "$d/idVendor" ] || continue; echo "USB_DEVICE=$d"; printf "VID="; cat "$d/idVendor"; printf "PID="; cat "$d/idProduct"; echo "DRIVER_SYMLINK:"; ls -l "$d/driver" 2>/dev/null || true; done'},
    @{Title='USB interface-level driver binding'; Cmd='for d in /sys/bus/usb/devices/*:*; do [ -e "$d" ] || continue; echo "USB_INTERFACE=$d"; echo "INTERFACE_DRIVER:"; ls -l "$d/driver" 2>/dev/null || true; done'},
    @{Title='all network interfaces'; Cmd='ip -o link show; ip -4 address show'},
    @{Title='USB network interfaces sysfs'; Cmd='for d in /sys/class/net/*; do [ -e "$d" ] || continue; echo "NET_IF=$d"; echo "DEVICE_SYMLINK:"; ls -l "$d/device" 2>/dev/null || true; echo "CARRIER:"; cat "$d/carrier" 2>/dev/null || true; done'},
    @{Title='IPv4 routes'; Cmd='ip -4 route show'},
    @{Title='runtime Ethernet services'; Cmd='getprop | grep -i ethernet'},
    @{Title='kernel config if available'; Cmd='if [ -r /proc/config.gz ]; then zcat /proc/config.gz | grep -E "^(CONFIG_USB_(USBNET|RTL8152|NET_AX88179_178A|NET_CDCETHER|NET_CDC_NCM)|CONFIG_PIPA_EXP_SUGOV_RATE_LIMIT_US)="; else echo "/proc/config.gz unavailable"; fi'}
)
$lines = New-Object 'System.Collections.Generic.List[string]'
$lines.Add("# EXP24 Ethernet A/B read-only evidence")
$lines.Add("# Stage=$Stage")
$lines.Add("# Captured=$(Get-Date -Format o)")
foreach ($entry in $commands) {
    $lines.Add("")
    $lines.Add("======== $($entry.Title) ========")
    # PowerShell 5.1 may convert native ADB stderr into a terminating NativeCommandError
    # when ErrorActionPreference=Stop. Keep the strict policy for setup, but capture
    # per-section output under Continue, including optional Android permission failures.
    $previousPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        $captured = @(& $Adb @adbArgs shell $entry.Cmd 2>&1 | ForEach-Object { $_.ToString() })
        $exitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previousPreference
    }
    if ($captured.Count -eq 0) {
        $lines.Add('(empty or not accessible)')
    } else {
        foreach ($line in $captured) { $lines.Add([string]$line) }
    }
    $lines.Add("exit_code=$exitCode")
    if ($exitCode -ne 0) {
        $lines.Add('NOTE: Optional section failed or permission denied. Capture continues.')
    }
}
$out = Join-Path $OutDir ("exp24-usb-{0}-{1}.txt" -f $Stage, (Get-Date -Format 'yyyyMMdd-HHmmss'))
[IO.File]::WriteAllLines((Join-Path (Resolve-Path $OutDir) (Split-Path $out -Leaf)), $lines, [Text.UTF8Encoding]::new($false))
Write-Host "Read-only device evidence saved: $out"
Write-Host 'Do not infer driver success from Internet access alone: compare VID/PID, driver symlink, network interface, DHCP/route and loaded EXP24 identity.'
