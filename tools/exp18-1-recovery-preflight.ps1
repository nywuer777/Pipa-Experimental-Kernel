# EXP18.1 - Pipa recovery environment and original backup integrity audit.
# Read-only. No fastboot transport, reboot, flash, image modification or writes.
param(
  [string]$BackupDir='C:\platform-tools\pipa_backup',
  [string]$Exp06Zip="$env:USERPROFILE\Downloads\pipa-exp06-clang21-1.zip",
  [string]$AdbPath='C:\platform-tools\adb.exe',
  [string]$FastbootPath='C:\platform-tools\fastboot.exe',
  [switch]$SelfTest
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$expected=[ordered]@{
  'boot_b.img'='31f57cded5fa4b37426b4387b58c1c7330703a1c1a8a5aa584b348fcbb78c2f4'
  'vendor_boot_b.img'='a24ea921db6014a49f9895cc5c18efbb6c6674d697f25cde3b7a1670a643c28c'
  'dtbo_b.img'='f4168f76d092362ac438543d74938d83e3e567a37abb16e4d61fe7ba764588e2'
  'vbmeta_b.img'='86d703c2ea2f73a55aa86374329bd89ffd975c0e95e33645a156cfdc343889ff'
}
$expectedZip='e32af6b61163fba4724211986823fc4ffab759956d213ef15b7fcda042241402'
function Need([bool]$ok,[string]$reason){if(-not $ok){throw ('EXP18.1 REJECT: '+$reason)}}
function ShaValid([string]$h){return ($h -cmatch '^[0-9a-f]{64}$')}
function VerifyFile([string]$file,[string]$expectedSha) {
  Need (ShaValid $expectedSha) ('invalid pinned SHA-256: '+[IO.Path]::GetFileName($file))
  Need ([IO.File]::Exists($file)) ('missing original file: '+[IO.Path]::GetFileName($file))
  $actual=(Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash.ToLowerInvariant()
  Need ($actual -ceq $expectedSha) ('SHA-256 mismatch: '+[IO.Path]::GetFileName($file))
}
function ParsePipaDevices([string[]]$lines) {
  $found=@($lines | Where-Object {$_ -match '^\S+\s+device\s+.*\bproduct:pipa\b.*\bdevice:pipa\b'})
  return $found.Count
}
foreach($key in $expected.Keys){Need (ShaValid $expected[$key]) ('malformed reference: '+$key)}
Need (ShaValid $expectedZip) 'malformed EXP06 ZIP reference'
if($SelfTest){
  $valid=@('List of devices attached','example123 device product:pipa model:23043RP34G device:pipa transport_id:1')
  $invalid=@('List of devices attached','example123 unauthorized product:pipa model:23043RP34G device:pipa transport_id:1')
  Need ((ParsePipaDevices $valid) -eq 1) 'ADB parser rejected synthetic authorized pipa'
  Need ((ParsePipaDevices $invalid) -eq 0) 'ADB parser accepted unauthorized pipa'
  Need (-not (ShaValid ('a'*65))) 'accepted 65-character SHA-256'
  Write-Output 'EXP18.1 SYNTHETIC RECOVERY PREFLIGHT: PASS'
  Write-Output 'NO PRIVATE FILES READ. NO DEVICE COMMANDS. FLASH_READY=false'
  return
}
Need ([IO.File]::Exists($AdbPath)) 'adb.exe missing'
Need ([IO.File]::Exists($FastbootPath)) 'fastboot.exe missing'
$fastbootOutput=(& $FastbootPath --version 2>&1 | Out-String).Trim()
Need ($LASTEXITCODE -eq 0 -and $fastbootOutput -match 'fastboot version\s+[0-9]') 'fastboot.exe version unavailable'
$devices=@(& $AdbPath devices -l 2>&1)
Need ($LASTEXITCODE -eq 0) 'adb devices failed'
Need ((ParsePipaDevices $devices) -eq 1) 'expected exactly one authorized pipa on ADB'
$slot=((& $AdbPath shell getprop ro.boot.slot_suffix 2>&1) | Out-String).Trim()
Need ($LASTEXITCODE -eq 0 -and $slot -ceq '_b') 'live slot not _b or inaccessible'
$device=((& $AdbPath shell getprop ro.product.device 2>&1) | Out-String).Trim()
Need ($LASTEXITCODE -eq 0 -and $device -ceq 'pipa') 'Android product not pipa'
foreach($name in $expected.Keys){VerifyFile (Join-Path $BackupDir $name) $expected[$name]}
VerifyFile $Exp06Zip $expectedZip
Write-Output 'EXP18.1 REAL WINDOWS RECOVERY INVENTORY: PASS'
Write-Output 'DEVICE connected_adb=True product=pipa slot=_b authorized_count=1'
Write-Output 'TOOLS adb_present=True fastboot_version_available=True'
Write-Output 'BACKUPS sha256_verified=4 count=4 source_slot=_b'
Write-Output 'EXP06 original_zip_sha256_verified=True'
Write-Output 'RECOVERY_INFO fastboot_mode_transport=NOT_TESTED rollback_restore=NOT_TESTED'
Write-Output 'LIMITS: valid backups and tools do not prove bootloader access or operational recovery.'
Write-Output 'NO REBOOT. NO IMAGE CREATED. NO PARTITION MODIFIED. FLASH_READY=false'
