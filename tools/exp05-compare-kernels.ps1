# EXP05: compares original slot-B kernel with pinned EXP01 Image, read-only.
param(
  [string]$BackupDir = 'C:\platform-tools\pipa_backup',
  [string]$Exp01Zip = '',
  [string]$Exp01ImagePath = '',
  [switch]$SyntheticTest
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$Expected = @{
  Zip='048c88f81c1909242eafbb1ff97e03dc1668a56b83bc8e02849bda4240a8897d'
  Exp01='bb20a6a936ff730d89dab8ca354ccb0ea7fe427594b8b60d2e1c424873970b11'
  Boot='31f57cded5fa4b37426b4387b58c1c7330703a1c1a8a5aa584b348fcbb78c2f4'
  OldKernel='a72fff8f285419f6f45c7e3d1c43fb1fe5958878b5ce53ab9291148ad9b7acdd'
}
if(([bool]$Exp01Zip) -eq ([bool]$Exp01ImagePath)){
  throw 'Specify exactly one of -Exp01Zip and -Exp01ImagePath.'
}
function FileHash([string]$Path){
  return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}
function ReadBuffer([System.IO.FileStream]$F,[long]$Offset,[int]$Length){
  if($Offset -lt 0 -or $Length -lt 0 -or $Offset -gt $F.Length -or $Length -gt ($F.Length-$Offset)){throw "Read outside file: $Offset/$Length"}
  [void]$F.Seek($Offset,[IO.SeekOrigin]::Begin)
  $out=New-Object byte[] $Length
  $pos=0
  while($pos -lt $Length){
    $got=$F.Read($out,$pos,$Length-$pos)
    if($got -le 0){throw 'Unexpected EOF'}
    $pos+=$got
  }
  return ,$out
}
function Read32([byte[]]$Bytes,[int]$Pos){return [long][BitConverter]::ToUInt32($Bytes,$Pos)}
function RangeHash([System.IO.FileStream]$F,[long]$Offset,[long]$Length){
  [void]$F.Seek($Offset,[IO.SeekOrigin]::Begin)
  $h=[Security.Cryptography.SHA256]::Create()
  try {
    [byte[]]$buffer=New-Object byte[] (1024*1024)
    while($Length -gt 0){
      $n=[int][Math]::Min($buffer.Length,$Length)
      $read=$F.Read($buffer,0,$n)
      if($read -le 0){throw 'Unexpected EOF while hashing'}
      [void]$h.TransformBlock($buffer,0,$read,$buffer,0)
      $Length-=$read
    }
    [void]$h.TransformFinalBlock([byte[]]@(),0,0)
    return ([BitConverter]::ToString($h.Hash)).Replace('-','').ToLowerInvariant()
  } finally {$h.Dispose()}
}
function VersionString([System.IO.FileStream]$F,[long]$Offset,[long]$Length){
  $grab=[int][Math]::Min($Length,40*1024*1024)
  $txt=[Text.Encoding]::ASCII.GetString((ReadBuffer $F $Offset $grab))
  $match=[regex]::Match($txt,'Linux version [0-9]+\.[0-9]+\.[0-9]+[^\x00\r\n]{0,210}')
  if($match.Success){return $match.Value}
  return 'NOT_FOUND'
}
$temporary=''
try {
  if($Exp01Zip){
    if(-not [IO.File]::Exists($Exp01Zip)){throw "Missing EXP01 GitHub artifact ZIP: $Exp01Zip"}
    $zHash=FileHash $Exp01Zip
    if($zHash -ne $Expected.Zip){throw "EXP01 ZIP SHA256 unexpected: $zHash"}
    $temporary=Join-Path ([IO.Path]::GetTempPath()) ('pipa-exp05-'+[guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Force -Path $temporary | Out-Null
    Expand-Archive -LiteralPath $Exp01Zip -DestinationPath $temporary -Force
    $Exp01ImagePath=Join-Path $temporary 'exp01-work\out\arch\arm64\boot\Image'
  }
  if(-not [IO.File]::Exists($Exp01ImagePath)){throw "Missing EXP01 Image: $Exp01ImagePath"}
  $imgHash=FileHash $Exp01ImagePath
  if($imgHash -ne $Expected.Exp01){throw "EXP01 Image SHA256 unexpected: $imgHash"}
  $bootPath=Join-Path $BackupDir 'boot_b.img'
  if(-not [IO.File]::Exists($bootPath)){throw "Missing boot backup: $bootPath"}
  $bootHash=FileHash $bootPath
  if(-not $SyntheticTest -and $bootHash -ne $Expected.Boot){throw "Original boot backup changed: $bootHash"}
  $A=[IO.File]::OpenRead($bootPath)
  $B=[IO.File]::OpenRead($Exp01ImagePath)
  try {
    $hdr=ReadBuffer $A 0 4096
    if([Text.Encoding]::ASCII.GetString($hdr,0,8) -ne 'ANDROID!' -or (Read32 $hdr 40) -ne 3 -or (Read32 $hdr 20) -ne 1580){throw 'Unexpected Android boot v3 header'}
    [long]$oldSize=Read32 $hdr 8
    [long]$newSize=$B.Length
    if($oldSize -lt 60 -or ($oldSize+4096) -gt $A.Length){throw 'Original kernel out of bounds'}
    if($newSize -lt 60){throw 'Compiled kernel is unexpectedly small'}
    $m1=ReadBuffer $A (4096+56) 4
    $m2=ReadBuffer $B 56 4
    if(([Text.Encoding]::ASCII.GetString($m1) -ne 'ARMd') -or ([Text.Encoding]::ASCII.GetString($m2) -ne 'ARMd')){throw 'ARM64 kernel magic mismatch'}
    $oldHash=RangeHash $A 4096 $oldSize
    if(-not $SyntheticTest -and $oldHash -ne $Expected.OldKernel){throw "Original kernel payload changed: $oldHash"}
    $oldBuild=VersionString $A 4096 $oldSize
    $newBuild=VersionString $B 0 $newSize
    $oldHead=ReadBuffer $A 4096 64
    $newHead=ReadBuffer $B 0 64
    Write-Output "SOURCE boot_sha256=$bootHash original_kernel_sha256=$oldHash"
    Write-Output "EXP01 image_sha256=$imgHash original_bytes=$oldSize exp01_bytes=$newSize difference_bytes=$($oldSize-$newSize)"
    Write-Output "ORIGINAL linux_build=$oldBuild"
    Write-Output "EXP01 linux_build=$newBuild"
    Write-Output "ARM64 original_header_hex=$(([BitConverter]::ToString($oldHead)).Replace('-','').ToLowerInvariant())"
    Write-Output "ARM64 exp01_header_hex=$(([BitConverter]::ToString($newHead)).Replace('-','').ToLowerInvariant())"
    [long]$length=[Math]::Min($oldSize,$newSize)
    [long]$position=0
    [int]$changed=0
    [int]$total=0
    [long]$first=-1
    while($position -lt $length){
      $block=[int][Math]::Min(1024*1024,$length-$position)
      $left=ReadBuffer $A (4096+$position) $block
      $right=ReadBuffer $B $position $block
      $h=[Security.Cryptography.SHA256]::Create()
      try {
        $x=[BitConverter]::ToString($h.ComputeHash($left))
        $y=[BitConverter]::ToString($h.ComputeHash($right))
      } finally {$h.Dispose()}
      if($x -ne $y){
        $changed++
        if($first -eq -1){
          for($i=0;$i -lt $block;$i++){
            if($left[$i] -ne $right[$i]){ $first=$position+$i; break }
          }
        }
      }
      $total++
      $position+=$block
    }
    $identical=($changed -eq 0 -and $oldSize -eq $newSize)
    Write-Output "COMPARE scanned_bytes=$length blocks=$total changed_blocks=$changed first_diff_offset=$first exactly_identical=$identical"
    Write-Output 'PASS: EXP05 compared kernels read-only; NO BOOT IMAGE CREATED.'
    Write-Output 'NOT PROVEN: ABI, kernel feature parity, filesystem drivers, root compatibility or startup.'
  } finally {$A.Dispose();$B.Dispose()}
} finally {
  if($temporary -and [IO.Directory]::Exists($temporary)){Remove-Item -LiteralPath $temporary -Recurse -Force}
}
