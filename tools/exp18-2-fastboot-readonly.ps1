# EXP18.2 — Query pipa's Fastboot transport and selected bootloader variables.
# Read-only. NO reboot, flash, change-slot, image creation, or getvar all.
param(
  [string]$FastbootPath='C:\platform-tools\fastboot.exe',
  [switch]$SelfTest
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
function Need([bool]$OK,[string]$Why) {
  if(-not $OK){throw ('EXP18.2 REJECT: '+$Why)}
}
function FindFastbootDevices([string]$Lines) {
  $found=New-Object System.Collections.Generic.List[string]
  foreach($line in ($Lines -split "\r?\n")) {
    if($line -match '^([A-Za-z0-9._:-]+)\s+fastboot(?:\s|$)') {
      $found.Add($Matches[1])
    }
  }
  return ,$found.ToArray()
}
function FindVariable([string]$Output,[string]$Name) {
  Need ($Name -cmatch '^(product|current-slot|is-userspace|unlocked|slot-count)$') 'unexpected getvar key'
  $pattern='(?m)^\s*(?:\(bootloader\)\s*)?'+[regex]::Escape($Name)+':\s*([A-Za-z0-9_.-]+)\s*$'
  if($Output -match $pattern){return $Matches[1].ToLowerInvariant()}
  return 'UNKNOWN'
}
function RunFastboot([string]$Arguments) {
  $start=New-Object System.Diagnostics.ProcessStartInfo
  $start.FileName=$FastbootPath
  $start.Arguments=$Arguments
  $start.UseShellExecute=$false
  $start.CreateNoWindow=$true
  $start.RedirectStandardOutput=$true
  $start.RedirectStandardError=$true
  $process=New-Object System.Diagnostics.Process
  $process.StartInfo=$start
  try {
    Need ($process.Start()) 'fastboot process failed to start'
    if(-not $process.WaitForExit(15000)) {
      try {$process.Kill()}catch{}
      throw 'EXP18.2 REJECT: fastboot command timeout (15 seconds)'
    }
    $stdout=$process.StandardOutput.ReadToEnd()
    $stderr=$process.StandardError.ReadToEnd()
    $process.WaitForExit()
    return [pscustomobject]@{
      exit_code=$process.ExitCode
      output=($stdout+[Environment]::NewLine+$stderr)
    }
  } finally {$process.Dispose()}
}
if($SelfTest) {
  $nl=[Environment]::NewLine
  $d=FindFastbootDevices ('List of devices attached'+$nl+'123_abc fastboot usb:1-2'+$nl)
  Need ($d.Length -eq 1 -and $d[0] -ceq '123_abc') 'normal device parser'
  $none=FindFastbootDevices ('List of devices attached'+$nl)
  Need ($none.Length -eq 0) 'empty device parser'
  $other=FindFastbootDevices ('abc unauthorized usb:1-2'+$nl)
  Need ($other.Length -eq 0) 'accepted non-fastboot device'
  Need ((FindVariable '(bootloader) product: pipa' 'product') -ceq 'pipa') 'bootloader getvar parser'
  Need ((FindVariable 'current-slot: b' 'current-slot') -ceq 'b') 'standard getvar parser'
  Need ((FindVariable 'FAILED (remote: unknown variable)' 'unlocked') -ceq 'UNKNOWN') 'unknown getvar parser'
  Write-Output 'EXP18.2 SYNTHETIC FASTBOOT PARSER SELFTEST: PASS'
  Write-Output 'NO DEVICE COMMANDS. NO FILE MODIFIED. FLASH_READY=false'
  return
}
Need ([IO.File]::Exists($FastbootPath)) 'fastboot.exe not found'
$version=RunFastboot '--version'
Need ($version.exit_code -eq 0 -and $version.output -match 'fastboot version\s+[0-9]') 'fastboot version unavailable'
$devices=RunFastboot 'devices -l'
Need ($devices.exit_code -eq 0) 'fastboot devices failed'
$found=FindFastbootDevices $devices.output
if($found.Length -eq 0) {
  Write-Output 'EXP18.2 FASTBOOT TRANSPORT: NOT_CONNECTED'
  Write-Output 'Device is in Android mode or Fastboot transport is not recognized.'
  Write-Output 'RESULT=NOT_TESTED'
  Write-Output 'NO DEVICE MODE CHANGE. NO FILE MODIFIED. FLASH_READY=false'
  return
}
Need ($found.Length -eq 1) 'multiple fastboot devices: refusing unsafe target'
$serial=$found[0]
Need ($serial -cmatch '^[A-Za-z0-9._:-]{1,96}$') 'unsafe/oversized device serial'
$results=@{}
foreach($v in @('product','current-slot','is-userspace','unlocked','slot-count')) {
  $q=RunFastboot ('-s '+$serial+' getvar '+$v)
  $value=FindVariable $q.output $v
  if($q.exit_code -ne 0) {$value='UNKNOWN'}
  $results[$v]=$value
}
Write-Output 'EXP18.2 REAL FASTBOOT READ-ONLY PROBE'
Write-Output 'USB device_count=1 fastboot_transport=True serial=REDACTED'
Write-Output ('GETVAR product='+$results['product']+
              ' current_slot='+$results['current-slot']+
              ' is_userspace='+$results['is-userspace']+
              ' unlocked='+$results['unlocked']+
              ' slot_count='+$results['slot-count'])
if($results['product'] -cne 'pipa') {
  Write-Output 'RESULT=REJECT_PRODUCT_MISMATCH'
} elseif($results['current-slot'] -cnotin @('b','_b')) {
  Write-Output 'RESULT=INCONCLUSIVE_SLOT'
} elseif($results['is-userspace'] -ceq 'yes') {
  Write-Output 'RESULT=FASTBOOTD_NOT_BOOTLOADER'
} elseif($results['unlocked'] -ceq 'no') {
  Write-Output 'RESULT=LOCK_STATE_CONFLICT_WITH_USER_REPORT'
} elseif($results['is-userspace'] -ceq 'UNKNOWN') {
  Write-Output 'RESULT=TRANSPORT_PASS_BOOTLOADER_MODE_UNCONFIRMED'
} else {
  Write-Output 'RESULT=FASTBOOT_BOOTLOADER_TRANSPORT_PASS'
}
Write-Output 'LIMITS: read-only getvar is not proof of emergency recovery, AVB or rollback.'
Write-Output 'NO REBOOT. NO FLASH. NO SLOT CHANGE. NO FILE MODIFIED. FLASH_READY=false'
