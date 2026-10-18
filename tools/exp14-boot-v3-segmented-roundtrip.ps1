# EXP14: Byte-preserving segmentation audit for original pipa boot_b.img.
# READ ONLY: no images, files or modified binaries are emitted.
param(
    [string]$BootPath='C:\platform-tools\pipa_backup\boot_b.img',
    [switch]$SelfTest
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$PIN_BOOT='31f57cded5fa4b37426b4387b58c1c7330703a1c1a8a5aa584b348fcbb78c2f4'
$PIN_KERNEL='a72fff8f285419f6f45c7e3d1c43fb1fe5958878b5ce53ab9291148ad9b7acdd'
function Need([bool]$Yes,[string]$Why){if(-not $Yes){throw "EXP14 REJECT: $Why"}}
function ReadAt([IO.Stream]$F,[long]$Off,[int]$Len) {
    Need ($Len -gt 0 -and $Off -ge 0 -and $Off -le $F.Length -and $Len -le $F.Length-$Off) 'read outside file'
    $F.Position=$Off
    [byte[]]$out=New-Object byte[] $Len
    $done=0
    while($done -lt $Len){
        $n=$F.Read($out,$done,$Len-$done)
        Need ($n -gt 0) 'unexpected EOF'
        $done+=$n
    }
    return ,$out
}
function Layout([IO.Stream]$F) {
    $h=ReadAt $F 0 4096
    Need ([Text.Encoding]::ASCII.GetString($h,0,8) -ceq 'ANDROID!') 'boot magic'
    $kernel=[long][BitConverter]::ToUInt32($h,8)
    $ramdisk=[long][BitConverter]::ToUInt32($h,12)
    $headerSize=[long][BitConverter]::ToUInt32($h,20)
    $version=[long][BitConverter]::ToUInt32($h,40)
    Need ($version -eq 3 -and $headerSize -eq 1580) 'not supported boot v3 header'
    Need ($kernel -ge 64 -and $ramdisk -ge 8) 'kernel/ramdisk length'
    [long]$kStart=4096
    [long]$kEnd=$kStart+$kernel
    [long]$rStart=$kStart+[long]([Math]::Floor(($kernel+4095)/4096)*4096)
    [long]$rEnd=$rStart+$ramdisk
    Need ($kEnd -le $rStart -and $rEnd -le $F.Length) 'section boundaries'
    Need ([Text.Encoding]::ASCII.GetString((ReadAt $F ($kStart+56) 4)) -ceq 'ARMd') 'ARM64 kernel magic'
    $gzip=ReadAt $F $rStart 2
    Need ($gzip[0] -eq 31 -and $gzip[1] -eq 139) 'generic ramdisk compression'
    return [pscustomobject]@{
      header_page_start=0L; header_page_bytes=4096L
      kernel_start=$kStart; kernel_bytes=$kernel
      padding_start=$kEnd; padding_bytes=$rStart-$kEnd
      ramdisk_start=$rStart; ramdisk_bytes=$ramdisk
      tail_start=$rEnd; tail_bytes=$F.Length-$rEnd
      total=$F.Length
    }
}
function Feed([Security.Cryptography.HashAlgorithm]$H,[IO.Stream]$F,[long]$Off,[long]$Len) {
    Need ($Off -ge 0 -and $Len -ge 0 -and $Off -le $F.Length -and $Len -le $F.Length-$Off) 'segment beyond EOF'
    $F.Position=$Off
    [byte[]]$buf=New-Object byte[] (1024*1024)
    [long]$remain=$Len
    while($remain -gt 0){
        $n=$F.Read($buf,0,[int][Math]::Min($remain,$buf.Length))
        Need ($n -gt 0) 'short segment read'
        [void]$H.TransformBlock($buf,0,$n,$buf,0)
        $remain-=$n
    }
}
function FinishHash([Security.Cryptography.HashAlgorithm]$H) {
    [void]$H.TransformFinalBlock([byte[]]@(),0,0)
    return ([BitConverter]::ToString($H.Hash)).Replace('-','').ToLowerInvariant()
}
function RegionHash([IO.Stream]$F,[long]$Off,[long]$Len) {
    $h=[Security.Cryptography.SHA256]::Create()
    try{Feed $h $F $Off $Len;return (FinishHash $h)}
    finally{$h.Dispose()}
}
function SegmentedHash([IO.Stream]$F,[object]$L) {
    $h=[Security.Cryptography.SHA256]::Create()
    try {
        Need ($L.header_page_start -eq 0) 'unexpected first segment'
        Need (($L.header_page_start + $L.header_page_bytes) -eq $L.kernel_start) 'header/kernel gap'
        Need (($L.kernel_start + $L.kernel_bytes) -eq $L.padding_start) 'kernel/padding gap'
        Need (($L.padding_start + $L.padding_bytes) -eq $L.ramdisk_start) 'padding/ramdisk gap'
        Need (($L.ramdisk_start + $L.ramdisk_bytes) -eq $L.tail_start) 'ramdisk/tail gap'
        Need (($L.tail_start + $L.tail_bytes) -eq $L.total) 'tail does not cover rest of partition'
        Feed $h $F $L.header_page_start $L.header_page_bytes
        Feed $h $F $L.kernel_start $L.kernel_bytes
        Feed $h $F $L.padding_start $L.padding_bytes
        Feed $h $F $L.ramdisk_start $L.ramdisk_bytes
        Feed $h $F $L.tail_start $L.tail_bytes
        return (FinishHash $h)
    } finally {$h.Dispose()}
}
function Synthetic {
    [byte[]]$image=New-Object byte[] 12299
    [Text.Encoding]::ASCII.GetBytes('ANDROID!').CopyTo($image,0)
    [BitConverter]::GetBytes([uint32]128).CopyTo($image,8)
    [BitConverter]::GetBytes([uint32]16).CopyTo($image,12)
    [BitConverter]::GetBytes([uint32]1580).CopyTo($image,20)
    [BitConverter]::GetBytes([uint32]3).CopyTo($image,40)
    [Text.Encoding]::ASCII.GetBytes('test cmdline').CopyTo($image,44)
    for($i=4096;$i -lt $image.Length;$i++){$image[$i]=[byte]($i%251)}
    [Text.Encoding]::ASCII.GetBytes('ARMd').CopyTo($image,4096+56)
    $image[8192]=31;$image[8193]=139
    $f=New-Object IO.MemoryStream(,$image)
    try {
        $layout=Layout $f
        Need ($layout.kernel_bytes -eq 128 -and $layout.padding_bytes -eq 3968 -and $layout.tail_bytes -eq 4091) 'synthetic layout'
        $whole=RegionHash $f 0 $f.Length
        $rebuild=SegmentedHash $f $layout
        Need ($whole -ceq $rebuild) 'byte-for-byte synthetic roundtrip mismatch'
        $image[0]=0
        $rejected=$false
        try{$null=Layout $f}catch{$rejected=$true}
        Need $rejected 'damaged synthetic header accepted'
        Write-Output 'EXP14 SYNTHETIC SEGMENTED ROUNDTRIP: PASS'
        Write-Output 'No files created. FLASH_READY=false'
    } finally{$f.Dispose()}
}
if($SelfTest){Synthetic;return}
Need ([IO.File]::Exists($BootPath)) 'missing boot_b.img'
$full=(Get-FileHash -LiteralPath $BootPath -Algorithm SHA256).Hash.ToLowerInvariant()
Need ($full -ceq $PIN_BOOT) 'original backup integrity mismatch'
$f=[IO.File]::OpenRead($BootPath)
try {
    Need ($f.Length -eq 201326592) 'backup partition length changed'
    $l=Layout $f
    Need ($l.kernel_bytes -eq 30349336 -and $l.ramdisk_bytes -eq 1849345 -and $l.ramdisk_start -eq 30355456) 'layout differs from EXP12'
    $kernelDigest=RegionHash $f $l.kernel_start $l.kernel_bytes
    Need ($kernelDigest -ceq $PIN_KERNEL) 'original E404 kernel hash mismatch'
    $seg=SegmentedHash $f $l
    Need ($seg -ceq $full) 'segmented roundtrip not identical'
    $cmd=RegionHash $f 44 1536
    $head=RegionHash $f 0 1580
    Write-Output 'EXP14 REAL BOOT-V3 SEGMENTED ROUNDTRIP: PASS'
    Write-Output "BACKUP full_sha256=$full bytes=$($l.total)"
    Write-Output "HEADER offset=0 bytes=1580 header_sha256=$head cmdline_sha256=$cmd cmdline_text=REDACTED"
    Write-Output "KERNEL offset=$($l.kernel_start) bytes=$($l.kernel_bytes) sha256=$kernelDigest"
    Write-Output "PADDING offset=$($l.padding_start) bytes=$($l.padding_bytes)"
    Write-Output "RAMDISK offset=$($l.ramdisk_start) bytes=$($l.ramdisk_bytes)"
    Write-Output "TAIL offset=$($l.tail_start) bytes=$($l.tail_bytes)"
    Write-Output "ROUNDTRIP segmented_sha256=$seg exactly_identical=True"
    Write-Output 'LIMITS: virtual segmentation audit only; not a mkbootimg repack, not a candidate boot image, not an AVB or boot test.'
    Write-Output 'NO IMAGE CREATED. NO FILE MODIFIED. FLASH_READY=false'
} finally {$f.Dispose()}
