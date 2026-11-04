# PowerShell 5.1+ / Windows platform-tools + Android ADB / EXP76 uname namespace audit / read-only
$ErrorActionPreference = "Stop"
Set-Location "C:\platform-tools"

$adb = ".\adb.exe"
if (-not (Test-Path $adb)) { throw "ADB_NOT_FOUND" }

Write-Host "=== ADB ==="
& $adb devices

Write-Host "=== BASELINE EXP75 / BOOT ==="
& $adb shell getprop sys.boot_completed
& $adb shell getprop ro.boot.slot_suffix
& $adb shell cat /proc/version

Write-Host "=== UNPRIVILEGED CONTEXT ==="
& $adb shell "id; /system/bin/toybox uname -r; readlink /proc/self/ns/uts; readlink /proc/1/ns/uts; cat /proc/sys/kernel/osrelease 2>&1"

Write-Host "=== ROOT CONTEXT ==="
& $adb shell "su -c 'id; /system/bin/toybox uname -r; readlink /proc/self/ns/uts; readlink /proc/1/ns/uts; cat /proc/sys/kernel/osrelease; cat /proc/version'"

Write-Host "=== PROPERTY CHECK (READ-ONLY) ==="
& $adb shell getprop ro.kernel.version
& $adb shell getprop ro.build.version.release

Write-Host "EXP76_UNAME_AUDIT=COLLECTED"
Write-Host "KERNEL_CHANGED=false"
Write-Host "FLASH_READY=false"
