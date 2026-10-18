# EXP08 — read-only runtime identity cross-check. Does not write files or flash partitions.
param(
    [string]$AdbPath = 'C:\platform-tools\adb.exe',
    [string]$Serial = '',
    [string]$FixtureJson = ''
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Read-Adb([string[]]$Commands) {
    $argList = @()
    if ($Serial) { $argList += @('-s', $Serial) }
    $argList += @('shell')
    $argList += $Commands
    $result = & $AdbPath @argList 2>&1 | Out-String
    if ($LASTEXITCODE -ne 0) {
        throw ('ADB command failed: ' + ($Commands -join ' ') + ' => ' + $result.Trim())
    }
    return $result.Trim()
}

$values = [ordered]@{}
if ($FixtureJson) {
    if (-not [IO.File]::Exists($FixtureJson)) { throw "Missing fixture file: $FixtureJson" }
    $fixture = Get-Content -LiteralPath $FixtureJson -Raw | ConvertFrom-Json
    foreach ($key in @('uname_release','toybox_release','proc_osrelease','proc_version','uname_full','kernel_version','slot','device')) {
        $v = $fixture.$key
        if ($null -eq $v) { throw "Missing fixture field: $key" }
        $values[$key] = [string]$v
    }
} else {
    if (-not [IO.File]::Exists($AdbPath)) { throw "ADB not found: $AdbPath" }
    $queries = [ordered]@{
        uname_release  = @('uname', '-r')
        toybox_release = @('/system/bin/toybox', 'uname', '-r')
        proc_osrelease = @('cat', '/proc/sys/kernel/osrelease')
        proc_version   = @('cat', '/proc/version')
        uname_full     = @('uname', '-a')
        kernel_version = @('cat', '/proc/sys/kernel/version')
        slot           = @('getprop', 'ro.boot.slot_suffix')
        device         = @('getprop', 'ro.product.device')
    }
    foreach ($key in $queries.Keys) {
        $values[$key] = Read-Adb $queries[$key]
    }
}

$procMatch = [regex]::Match($values['proc_version'], '^Linux version ([^\s]+)')
$unameMatch = [regex]::Match($values['uname_full'], '^Linux\s+\S+\s+([^\s]+)')
if (-not $procMatch.Success -or -not $unameMatch.Success) {
    throw 'Unable to parse standard Linux kernel version formats.'
}
$fromProcVersion = $procMatch.Groups[1].Value
$fromUnameFull = $unameMatch.Groups[1].Value

Write-Output 'EXP08 PIPA RUNTIME IDENTITY (READ ONLY)'
Write-Output ("DEVICE code_name={0} active_slot={1}" -f $values['device'], $values['slot'])
Write-Output ("UNAME release={0}" -f $values['uname_release'])
Write-Output ("TOYBOX release={0}" -f $values['toybox_release'])
Write-Output ("PROC_SYS release={0}" -f $values['proc_osrelease'])
Write-Output ("PROC_VERSION release={0}" -f $fromProcVersion)
Write-Output ("UNAME_FULL release={0}" -f $fromUnameFull)
Write-Output ("KERNEL_BUILD version={0}" -f $values['kernel_version'])
Write-Output ("PROC_VERSION_RAW {0}" -f $values['proc_version'])
if ($values['device'] -ne 'pipa') {
    Write-Output 'WARNING: device codename does not equal pipa'
}
if ($values['slot'] -notin @('_a','_b')) {
    Write-Output 'WARNING: device did not report a standard active slot'
}

if ($values['uname_release'] -cne $values['toybox_release']) {
    $status='USERSPACE_UNAME_MISMATCH'
} elseif ($values['uname_release'] -cne $values['proc_osrelease']) {
    $status='UNAME_VS_PROC_OSRELEASE_MISMATCH'
} elseif ($values['uname_release'] -cne $fromUnameFull) {
    $status='UNAME_COMMAND_MISMATCH'
} elseif ($values['uname_release'] -cne $fromProcVersion) {
    $status='PROC_VERSION_MISMATCH'
} else {
    $status='RELEASE_SOURCES_AGREE'
}
Write-Output "RESULT $status"
Write-Output 'SAFETY: this result does not prove kernel source/config ABI compatibility.'
Write-Output 'SAFETY: no partition images or files were modified.'
