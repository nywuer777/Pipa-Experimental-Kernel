# EXP13.3: Compare the 1st vbmeta blob from the pinned local backup with a reported boot vbmeta digest.
# Offline, read only, no keys, no salt, no flash, no reboot. Supports PowerShell 5.1 and 7.
param(
  [string]$VbmetaPath='C:\platform-tools\pipa_backup\vbmeta_b.img',
  [string]$BootReportedDigest='',
  [switch]$SelfTest
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$ExpectedHash='86d703c2ea2f73a55aa86374329bd89ffd975c0e95e33645a156cfdc343889ff'
function Check([bool]$Ok,[string]$Reason) {
  if(-not $Ok){throw ('EXP13.3 REJECT: '+$Reason)}
}
function ReadBe32([byte[]]$Data,[int]$Offset) {
  Check ($Offset -ge 0 -and ($Offset+4) -le $Data.Length) '32-bit header field outside bytes'
  return (([long]$Data[$Offset] -shl 24) -bor ([long]$Data[$Offset+1] -shl 16) -bor ([long]$Data[$Offset+2] -shl 8) -bor [long]$Data[$Offset+3])
}
function ReadBe64([byte[]]$Data,[int]$Offset) {
  Check ($Offset -ge 0 -and ($Offset+8) -le $Data.Length) '64-bit header field outside bytes'
  return ([decimal](ReadBe32 $Data $Offset)*[decimal]4294967296) + [decimal](ReadBe32 $Data ($Offset+4))
}
function GetBlobDigest([byte[]]$Data) {
  Check ($Data.Length -ge 256) 'vbmeta too short'
  Check ([Text.Encoding]::ASCII.GetString($Data,0,4) -ceq 'AVB0') 'missing AVB magic'
  Check ((ReadBe32 $Data 4) -eq 1) 'unsupported AVB major version'
  $auth=ReadBe64 $Data 12
  $aux=ReadBe64 $Data 20
  Check ($auth -ge 0 -and $aux -ge 0 -and ($auth % 64) -eq 0 -and ($aux % 64) -eq 0) 'unexpected block alignment'
  [decimal]$blob=256+$auth+$aux
  Check ($blob -le $Data.Length -and $blob -le 65536 -and $blob -ge 256) 'vbmeta blob size invalid'
  $sha=[Security.Cryptography.SHA256]::Create()
  try {
    $h=([BitConverter]::ToString($sha.ComputeHash($Data,0,[int]$blob))).Replace('-','').ToLowerInvariant()
    return [pscustomobject]@{blob_bytes=[long]$blob;digest=$h;flags=(ReadBe32 $Data 120)}
  } finally {$sha.Dispose()}
}
if($SelfTest) {
  [byte[]]$sample=New-Object byte[] 384
  [Text.Encoding]::ASCII.GetBytes('AVB0').CopyTo($sample,0)
  $sample[7]=1
  $sample[27]=64 # aux size
  $sample[19]=64 # auth size
  $sample[123]=3 # flags
  $r=GetBlobDigest $sample
  Check ($r.blob_bytes -eq 384 -and $r.flags -eq 3) 'synthetic AVB parse or length failed'
  $plain=[Security.Cryptography.SHA256]::Create()
  try {
    $compare=([BitConverter]::ToString($plain.ComputeHash($sample))).Replace('-','').ToLowerInvariant()
    Check ($r.digest -ceq $compare) 'SHA-256 of complete vbmeta blob mismatch'
  } finally {$plain.Dispose()}
  $sample[0]=0
  $rejected=$false
  try {$null=GetBlobDigest $sample} catch {$rejected=$true}
  Check $rejected 'corrupted AVB magic accepted'
  Write-Output 'EXP13.3 SYNTHETIC VBMETA DIGEST TEST: PASS'
  Write-Output 'NO PRIVATE IMAGES USED. FLASH_READY=false'
  return
}
Check ([IO.File]::Exists($VbmetaPath)) 'missing pinned vbmeta_b.img'
$fullHash=(Get-FileHash -LiteralPath $VbmetaPath -Algorithm SHA256).Hash.ToLowerInvariant()
Check ($fullHash -ceq $ExpectedHash) 'vbmeta backup SHA-256 changed'
$b=[IO.File]::ReadAllBytes($VbmetaPath)
Check ($b.Length -eq 131072) 'unexpected backup partition length'
$r=GetBlobDigest $b
Check ($r.blob_bytes -eq 5184 -and $r.flags -eq 3) 'unexpected vbmeta header compared with validated EXP13'
Write-Output 'EXP13.3 REAL SLOT-B VBMETA BLOB DIGEST AUDIT: PASS'
Write-Output 'SOURCE=vbmeta_b.img sha256_full_backup=verified slot=_b'
Write-Output "VBMETA_BLOB bytes=$($r.blob_bytes) sha256=$($r.digest) flags=$($r.flags)"
if([string]::IsNullOrWhiteSpace($BootReportedDigest)) {
  Write-Output 'BOOT_REPORTED_DIGEST=NOT_PROVIDED'
  Write-Output 'RESULT=LOCAL_DIGEST_ONLY'
} else {
  $reported=$BootReportedDigest.Trim().ToLowerInvariant()
  Check ($reported -cmatch '^[0-9a-f]{64}$') 'reported digest is not a 64-character SHA-256'
  if($r.digest -ceq $reported) {
    Write-Output 'RESULT=MATCH_STANDALONE_VBMETA_BLOB'
  } else {
    Write-Output 'RESULT=DOES_NOT_MATCH_STANDALONE_VBMETA_BLOB'
  }
}
Write-Output 'LIMITS: boot-reported digest may include multiple chained vbmeta images, not just the local top-level image.'
Write-Output 'LIMITS: Android getprop may be empty, filtered or inconsistent; a match is correlation, NOT a trusted-key or rollback attestation.'
Write-Output 'NO FILE MODIFIED. NO IMAGE CREATED. FLASH_READY=false'
