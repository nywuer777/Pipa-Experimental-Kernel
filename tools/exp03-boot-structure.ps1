# EXP03 — read-only structural audit of four pipa slot-B backups.
param([string]$BackupDir = 'C:\platform-tools\pipa_backup')
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function ReadAt {
  param([System.IO.FileStream]$F,[long]$Offset,[int]$Count)
  if($Offset -lt 0 -or $Count -lt 0 -or $Offset -gt $F.Length -or $Count -gt ($F.Length-$Offset)) { throw "Invalid read offset=$Offset size=$Count" }
  $F.Position=$Offset
  [byte[]]$B=New-Object byte[] $Count
  $N=0
  while($N -lt $Count){ $K=$F.Read($B,$N,$Count-$N); if($K -le 0){throw 'Unexpected EOF'}; $N+=$K }
  return ,$B
}
function LE32 {param([byte[]]$B,[int]$O)
  if($O -lt 0 -or $O+4 -gt $B.Length){throw 'LE32 out of range'}
  return [uint64]$B[$O] -bor ([uint64]$B[$O+1] -shl 8) -bor ([uint64]$B[$O+2] -shl 16) -bor ([uint64]$B[$O+3] -shl 24)
}
function BE32 {param([byte[]]$B,[int]$O)
  if($O -lt 0 -or $O+4 -gt $B.Length){throw 'BE32 out of range'}
  return ([uint64]$B[$O] -shl 24) -bor ([uint64]$B[$O+1] -shl 16) -bor ([uint64]$B[$O+2] -shl 8) -bor [uint64]$B[$O+3]
}
function BE64 {param([byte[]]$B,[int]$O)
  return ([uint64](BE32 $B $O)*[uint64]4294967296)+[uint64](BE32 $B ($O+4))
}
function Aligned {param([long]$N,[long]$P)
  if($P -le 0 -or $N -lt 0){throw 'Invalid alignment'}
  return [long]([math]::Ceiling([double]$N/[double]$P)*[double]$P)
}
function CheckSection {param([System.IO.FileStream]$F,[long]$Offset,[long]$Count,[string]$Name)
  if($Count -le 0 -or $Offset -lt 0 -or $Offset -gt $F.Length -or $Count -gt ($F.Length-$Offset)){throw "Invalid $Name section: offset=$Offset size=$Count"}
}
function PrefixKind {param([byte[]]$B)
  $hex=([BitConverter]::ToString($B)).Replace('-','').ToLowerInvariant()
  if($hex.StartsWith('1f8b')){return 'gzip'}
  if($hex.StartsWith('04224d18')){return 'lz4-frame'}
  if($hex.StartsWith('28b52ffd')){return 'zstd'}
  if($hex.StartsWith('fd377a58')){return 'xz'}
  if($B.Length -ge 6 -and ([Text.Encoding]::ASCII.GetString($B,0,6) -in @('070701','070702'))){return 'cpio-newc'}
  return 'unknown-'+$hex
}

if(-not [IO.Directory]::Exists($BackupDir)){throw "Missing directory: $BackupDir"}
Write-Output 'Pipa Experimental EXP03 — read-only structural audit'
Write-Output 'No partition is modified; no private image is uploaded.'

$F=[IO.File]::OpenRead((Join-Path $BackupDir 'boot_b.img'))
try {
  $H=ReadAt $F 0 4096
  if([Text.Encoding]::ASCII.GetString($H,0,8) -ne 'ANDROID!'){throw 'boot magic mismatch'}
  $Ver=LE32 $H 40; $HdrSize=LE32 $H 20
  if($Ver -ne 3 -or $HdrSize -ne 1580){throw "Unexpected boot version or header size: $Ver/$HdrSize"}
  $KSize=[long](LE32 $H 8); $RSize=[long](LE32 $H 12)
  $KOff=4096L; $ROff=$KOff+(Aligned $KSize 4096)
  CheckSection $F $KOff $KSize 'kernel'; CheckSection $F $ROff $RSize 'generic ramdisk'
  $ArmBytes=ReadAt $F ($KOff+56) 4
  $IsArm=([Text.Encoding]::ASCII.GetString($ArmBytes) -eq 'ARMd')
  $RKind=PrefixKind (ReadAt $F $ROff 8)
  Write-Output "BOOT version=$Ver header_size=$HdrSize kernel_size=$KSize kernel_offset=$KOff arm64_magic=$IsArm ramdisk_size=$RSize ramdisk_offset=$ROff ramdisk_kind=$RKind"
} finally { $F.Dispose() }

$F=[IO.File]::OpenRead((Join-Path $BackupDir 'vendor_boot_b.img'))
try {
  $H=ReadAt $F 0 4096
  if([Text.Encoding]::ASCII.GetString($H,0,8) -ne 'VNDRBOOT'){throw 'vendor boot magic mismatch'}
  $Ver=LE32 $H 8; $Page=[long](LE32 $H 12)
  $RSize=[long](LE32 $H 24); $HdrSize=LE32 $H 2096; $DTBSize=[long](LE32 $H 2100)
  if($Ver -ne 3 -or $HdrSize -ne 2112 -or $Page -lt 2048 -or $Page -gt 65536 -or (($Page -band ($Page-1)) -ne 0)){throw "Unexpected vendor header: version=$Ver size=$HdrSize page=$Page"}
  $ROff=Aligned $HdrSize $Page; $DTBOff=$ROff+(Aligned $RSize $Page)
  CheckSection $F $ROff $RSize 'vendor ramdisk'; CheckSection $F $DTBOff $DTBSize 'DTB'
  $RKind=PrefixKind (ReadAt $F $ROff 8)
  $DTBHeader=ReadAt $F $DTBOff 8
  if((BE32 $DTBHeader 0) -eq 3490578157){$DTBKind='FDT size='+(BE32 $DTBHeader 4)}else{$DTBKind='INVALID_MAGIC'}
  Write-Output "VENDOR_BOOT version=$Ver header_size=$HdrSize page_size=$Page ramdisk_size=$RSize ramdisk_offset=$ROff ramdisk_kind=$RKind dtb_size=$DTBSize dtb_offset=$DTBOff dtb_magic=$DTBKind"
} finally { $F.Dispose() }

$F=[IO.File]::OpenRead((Join-Path $BackupDir 'dtbo_b.img'))
try {
  $H=ReadAt $F 0 32
  if((BE32 $H 0) -ne 3619138334){throw 'DTBO magic mismatch'}
  $Total=[long](BE32 $H 4); $HdrSize=[long](BE32 $H 8)
  $EntrySize=[long](BE32 $H 12); $Count=[long](BE32 $H 16)
  $EntriesOffset=[long](BE32 $H 20); $Page=BE32 $H 24; $Ver=BE32 $H 28
  if($Total -lt 32 -or $Total -gt $F.Length -or $HdrSize -lt 32 -or $EntrySize -lt 32 -or $Count -gt 256 -or $EntriesOffset -lt $HdrSize -or $EntriesOffset -gt $Total -or ($Count*$EntrySize) -gt ($Total-$EntriesOffset)){throw 'DTBO table dimensions invalid'}
  $Bad=0
  for($I=0;$I -lt $Count;$I++){
    $E=ReadAt $F ($EntriesOffset+$I*$EntrySize) 16
    $Size=[long](BE32 $E 0); $Offset=[long](BE32 $E 4)
    if($Size -le 0 -or $Offset -gt $Total -or $Size -gt ($Total-$Offset)){throw "DTBO entry $I outside image"}
    $D=ReadAt $F $Offset 4
    if((BE32 $D 0) -ne 3490578157){$Bad++}
  }
  Write-Output "DTBO version=$Ver table_size=$Total header_size=$HdrSize entry_size=$EntrySize entries=$Count page_size=$Page non_fdt_entries=$Bad"
} finally {$F.Dispose()}

$F=[IO.File]::OpenRead((Join-Path $BackupDir 'vbmeta_b.img'))
try {
  $H=ReadAt $F 0 256
  if([Text.Encoding]::ASCII.GetString($H,0,4) -ne 'AVB0'){throw 'AVB magic mismatch'}
  $Major=BE32 $H 4; $Minor=BE32 $H 8
  $Auth=BE64 $H 12; $Aux=BE64 $H 20
  $Algorithm=BE32 $H 28; $Flags=BE32 $H 120
  if(($Auth+$Aux+256) -gt $F.Length){throw 'AVB blocks exceed partition size'}
  Write-Output "VBMETA version=$Major.$Minor auth_size=$Auth aux_size=$Aux algorithm=$Algorithm flags=$Flags (signature NOT verified)"
} finally {$F.Dispose()}

Write-Output 'PASS: header and section boundaries structurally valid; images UNMODIFIED.'
Write-Output 'NOT VERIFIED: boot compatibility, module ABI, AVB signatures, root and recovery.'
