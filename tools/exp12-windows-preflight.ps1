# EXP12: only local read-only verification of Xiaomi Pad 6 slot-B backups.
# Tested on PowerShell 5.1 and 7; never unpacks or creates .img files.
param(
    [string]$BackupDir = 'C:\platform-tools\pipa_backup',
    [string]$Exp06Zip = '',
    [switch]$SelfTest
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$Expected=[ordered]@{
    'boot_b.img'='31f57cded5fa4b37426b4387b58c1c7330703a1c1a8a5aa584b348fcbb78c2f4'
    'vendor_boot_b.img'='a24ea921db6014a49f9895cc5c18efbb6c6674d697f25cde3b7a1670a643c28c'
    'dtbo_b.img'='f4168f76d092362ac438543d74938d83e3e567a37abb16e4d61fe7ba764588e2'
    'vbmeta_b.img'='86d703c2ea2f73a55aa86374329bd89ffd975c0e95e33645a156cfdc343889ff'
}
$Exp06ZipHash='e32af6b61163fba4724211986823fc4ffab759956d213ef15b7fcda042241402'
$Exp06ImageHash='7b3c971a6bd92e8e609e4c56fb6e33df78a7668463e9bcfc342aa1cdee9a0033'
$OldKernelHash='a72fff8f285419f6f45c7e3d1c43fb1fe5958878b5ce53ab9291148ad9b7acdd'
$GenericRamdiskHash='d2a62b4ca809b28ddd0ae25388af051c874fbacfecb6b965243b7d6b81465ee9'
$VendorRamdiskHash='8e0841f5271c164654b0a43561671a7a9e2364430ee1d650c114c8f55144c8e6'
$DTBHash='9b92c1aa019fffdfaf3bfe36dcd84c2858c804109c100b684e08f62228881117'
$DTBOHash='6a0e109590742ce67713d738aef1320e015e9abc6b509d5be7f6e9ed46dd4f9c'
function Assert([bool]$Ok,[string]$Reason) {if(-not $Ok){throw "EXP12 FAIL: $Reason"}}
function HashBytes([byte[]]$Data) {
    $sha=[Security.Cryptography.SHA256]::Create()
    try{return ([BitConverter]::ToString($sha.ComputeHash($Data))).Replace('-','').ToLowerInvariant()}
    finally {$sha.Dispose()}
}
function HashStream([IO.Stream]$Stream,[long]$Offset,[long]$Size) {
    Assert ($Offset -ge 0 -and $Size -gt 0 -and $Offset -le $Stream.Length -and $Size -le ($Stream.Length-$Offset)) 'hash range outside stream'
    $Stream.Position=$Offset
    $hash=[Security.Cryptography.SHA256]::Create()
    try {
        [byte[]]$buffer=New-Object byte[] (1024*1024)
        while ($Size -gt 0) {
            $read=$Stream.Read($buffer,0,[int][Math]::Min($buffer.Length,$Size))
            Assert ($read -gt 0) 'unexpected EOF'
            [void]$hash.TransformBlock($buffer,0,$read,$buffer,0)
            $Size-=$read
        }
        [void]$hash.TransformFinalBlock([byte[]]@(),0,0)
        return ([BitConverter]::ToString($hash.Hash)).Replace('-','').ToLowerInvariant()
    } finally {$hash.Dispose()}
}
function ReadAt([IO.Stream]$S,[long]$Offset,[int]$Count) {
    Assert ($Count -gt 0 -and $Offset -ge 0 -and $Offset -le $S.Length -and $Count -le ($S.Length-$Offset)) "read outside file at $Offset/$Count"
    $S.Position=$Offset
    [byte[]]$buf=New-Object byte[] $Count
    $i=0
    while($i -lt $Count) {
        $n=$S.Read($buf,$i,$Count-$i)
        Assert ($n -gt 0) 'short read'
        $i+=$n
    }
    return ,$buf
}
function U32LE([byte[]]$B,[int]$I) {
    Assert ($I -ge 0 -and $I+4 -le $B.Length) 'LE32 outside header'
    return [long]([BitConverter]::ToUInt32($B,$I))
}
function U32BE([byte[]]$B,[int]$I) {
    Assert ($I -ge 0 -and $I+4 -le $B.Length) 'BE32 outside header'
    return ([long]$B[$I] -shl 24) -bor ([long]$B[$I+1] -shl 16) -bor ([long]$B[$I+2] -shl 8) -bor [long]$B[$I+3]
}
function U64BE([byte[]]$B,[int]$I){
    return ([decimal](U32BE $B $I)*[decimal]4294967296 + [decimal](U32BE $B ($I+4)))
}
function Aligned([long]$N,[long]$Page) {
    Assert ($Page -ge 2048 -and $Page -le 65536 -and (($Page -band ($Page-1)) -eq 0)) 'unexpected page alignment'
    return [long](([Math]::Floor(($N+$Page-1)/$Page))*$Page)
}
function ParseBoot([IO.Stream]$F) {
    $h=ReadAt $F 0 4096
    Assert ([Text.Encoding]::ASCII.GetString($h,0,8) -ceq 'ANDROID!') 'boot_v3 magic'
    $ks=U32LE $h 8; $rs=U32LE $h 12; $hs=U32LE $h 20; $v=U32LE $h 40
    Assert ($v -eq 3 -and $hs -eq 1580) 'boot v3 version/header'
    Assert ($ks -ge 64 -and $rs -gt 8) 'boot kernel or ramdisk size'
    $ko=4096L; $ro=$ko+(Aligned $ks 4096)
    Assert ([Text.Encoding]::ASCII.GetString((ReadAt $F ($ko+56) 4)) -ceq 'ARMd') 'ARM64 magic missing in original'
    $rz=ReadAt $F $ro 2
    Assert ($rz[0] -eq 31 -and $rz[1] -eq 139) 'generic ramdisk not gzip'
    return @{
        kernel_offset=$ko; kernel_bytes=$ks; generic_offset=$ro; generic_bytes=$rs
        original_kernel_sha256=(HashStream $F $ko $ks)
        generic_ramdisk_sha256=(HashStream $F $ro $rs)
    }
}
function ParseVendor([IO.Stream]$F) {
    $h=ReadAt $F 0 4096
    Assert ([Text.Encoding]::ASCII.GetString($h,0,8) -ceq 'VNDRBOOT') 'vendor_boot magic'
    $v=U32LE $h 8; $page=U32LE $h 12; $r=U32LE $h 24
    $hs=U32LE $h 2096; $ds=U32LE $h 2100
    Assert ($v -eq 3 -and $hs -eq 2112 -and $r -gt 8 -and $ds -ge 40) 'vendor boot v3 metadata'
    $ro=Aligned $hs $page; $do=$ro+(Aligned $r $page)
    $g=ReadAt $F $ro 2
    Assert ($g[0] -eq 31 -and $g[1] -eq 139) 'vendor ramdisk not gzip'
    $fdt=ReadAt $F $do 8
    Assert ((U32BE $fdt 0) -eq 3490578157) 'vendor DTB FDT magic'
    Assert ((U32BE $fdt 4) -eq $ds) 'vendor DTB FDT length'
    return @{
        vendor_ramdisk_offset=$ro; vendor_ramdisk_bytes=$r; dtb_offset=$do; dtb_bytes=$ds
        vendor_ramdisk_sha256=(HashStream $F $ro $r); dtb_sha256=(HashStream $F $do $ds)
    }
}
function ParseDtbo([IO.Stream]$F) {
    $h=ReadAt $F 0 32
    $magic=U32BE $h 0; $total=U32BE $h 4; $hs=U32BE $h 8
    $es=U32BE $h 12; $count=U32BE $h 16; $eo=U32BE $h 20; $ver=U32BE $h 28
    Assert ($magic -eq 3619138334) 'DTBO table magic'
    Assert ($ver -eq 0 -and $total -ge 64 -and $hs -ge 32 -and $es -ge 32 -and $count -ge 1 -and $count -le 256) 'DTBO dimensions'
    Assert ($eo -ge $hs -and (($eo+$count*$es) -le $total) -and $total -le $F.Length) 'DTBO entries outside table'
    for($i=0;$i -lt $count;$i++){
        $e=ReadAt $F ($eo+$i*$es) 8
        $size=U32BE $e 0; $off=U32BE $e 4
        Assert ($size -ge 40 -and $off+$size -le $total) "DTBO entry $i outside table"
        $fdt=ReadAt $F $off 8
        Assert ((U32BE $fdt 0) -eq 3490578157 -and (U32BE $fdt 4) -eq $size) "DTBO FDT $i inconsistent"
    }
    return @{total_bytes=$total; entries=$count; table_sha256=(HashStream $F 0 $total)}
}
function ParseVbmeta([IO.Stream]$F){
    $h=ReadAt $F 0 256
    Assert ([Text.Encoding]::ASCII.GetString($h,0,4) -ceq 'AVB0') 'vbmeta magic'
    $major=U32BE $h 4; $minor=U32BE $h 8; $auth=U64BE $h 12; $aux=U64BE $h 20
    $algo=U32BE $h 28; $flags=U32BE $h 120
    Assert (($auth+$aux+256) -le $F.Length) 'vbmeta authentication/auxiliary ranges'
    return @{version="$major.$minor"; algorithm=$algo; flags=$flags; cryptographic_signature_verified=$false}
}
function FromFile([string]$File,[scriptblock]$Read) {
    $s=[IO.File]::OpenRead($File)
    try {return (& $Read $s)}
    finally {$s.Dispose()}
}
function CheckHash([string]$Val,[string]$ExpectedVal,[string]$Name) {
    Assert ($Val -ceq $ExpectedVal) "$Name SHA256 mismatch: got $Val"
}
function SHAFile([string]$Path) {return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()}
function TestParsers {
    # Unit-only small buffers; *never* claims real backup integrity.
    [byte[]]$k=New-Object byte[] 256; $k[56]=65; $k[57]=82; $k[58]=77; $k[59]=100
    [byte[]]$h=New-Object byte[] 4096; [Text.Encoding]::ASCII.GetBytes('ANDROID!').CopyTo($h,0)
    [BitConverter]::GetBytes([uint32]256).CopyTo($h,8)
    [BitConverter]::GetBytes([uint32]128).CopyTo($h,12)
    [BitConverter]::GetBytes([uint32]1580).CopyTo($h,20)
    [BitConverter]::GetBytes([uint32]3).CopyTo($h,40)
    [byte[]]$buf=New-Object byte[] (8192+128)
    [Array]::Copy($h,0,$buf,0,$h.Length); [Array]::Copy($k,0,$buf,4096,$k.Length)
    $buf[8192]=31; $buf[8193]=139
    $s=New-Object IO.MemoryStream(,$buf)
    try{
        $b=ParseBoot $s
        Assert ($b.kernel_bytes -eq 256 -and $b.generic_offset -eq 8192) 'synthetic boot layout mismatch'
        $buf[4096+56]=0
        $bad=New-Object IO.MemoryStream(,$buf)
        try {
            $rejected=$false
            try {$null=ParseBoot $bad} catch {$rejected=$true}
            Assert $rejected 'invalid synthetic arm magic accepted'
        } finally {$bad.Dispose()}
        Write-Output 'PASS SYNTHETIC: boot v3 layout and corruption rejection'
        Write-Output 'FIXTURE ONLY - no real backups audited. FLASH_READY=false'
    } finally {$s.Dispose()}
}
if($SelfTest){TestParsers; return}
Assert (-not [string]::IsNullOrWhiteSpace($Exp06Zip)) 'Provide -Exp06Zip'
Assert ([IO.Directory]::Exists($BackupDir)) 'Backup directory missing'
Assert ([IO.File]::Exists($Exp06Zip)) 'EXP06 GitHub artifact ZIP missing'
CheckHash (SHAFile $Exp06Zip) $Exp06ZipHash 'EXP06 pinned ZIP'
foreach($name in $Expected.Keys) {
    $path=Join-Path $BackupDir $name
    Assert ([IO.File]::Exists($path)) "Missing private backup: $name"
    CheckHash (SHAFile $path) $Expected[$name] $name
}
$boot=FromFile (Join-Path $BackupDir 'boot_b.img') {param($s) ParseBoot $s}
$vendor=FromFile (Join-Path $BackupDir 'vendor_boot_b.img') {param($s) ParseVendor $s}
$dtbo=FromFile (Join-Path $BackupDir 'dtbo_b.img') {param($s) ParseDtbo $s}
$vbmeta=FromFile (Join-Path $BackupDir 'vbmeta_b.img') {param($s) ParseVbmeta $s}
CheckHash $boot.original_kernel_sha256 $OldKernelHash 'original kernel'
CheckHash $boot.generic_ramdisk_sha256 $GenericRamdiskHash 'original generic ramdisk'
CheckHash $vendor.vendor_ramdisk_sha256 $VendorRamdiskHash 'original vendor ramdisk'
CheckHash $vendor.dtb_sha256 $DTBHash 'original vendor DTB'
CheckHash $dtbo.table_sha256 $DTBOHash 'original DTBO table'
Assert ($boot.kernel_bytes -eq 30349336 -and $boot.generic_bytes -eq 1849345) 'original boot sizes unexpectedly differ'
Assert ($vendor.dtb_bytes -eq 460314 -and $vendor.vendor_ramdisk_bytes -eq 20412235) 'original vendor sizes unexpectedly differ'
Assert ($dtbo.total_bytes -eq 688455 -and $dtbo.entries -eq 1) 'original DTBO table sizes unexpectedly differ'
Assert ($vbmeta.version -ceq '1.0' -and $vbmeta.algorithm -eq 2 -and $vbmeta.flags -eq 3) 'unexpected AVB metadata'
Add-Type -AssemblyName System.IO.Compression
$z=[IO.Compression.ZipFile]::OpenRead($Exp06Zip)
try {
    $entries=@{
        image='exp06-work/out/arch/arm64/boot/Image'
        dtb='exp06-work/out/arch/arm64/boot/dtb'
        dtbo='exp06-work/out/arch/arm64/boot/dtbo.img'
    }
    foreach($n in @('image','dtb','dtbo')){
        $e=$z.GetEntry($entries[$n]); Assert ($null -ne $e) "EXP06 entry missing: $n"
        $stream=$e.Open()
        try {
            $sha=[Security.Cryptography.SHA256]::Create()
            try {$hash=([BitConverter]::ToString($sha.ComputeHash($stream))).Replace('-','').ToLowerInvariant()}
            finally {$sha.Dispose()}
            switch($n) {
                'image' {
                    CheckHash $hash $Exp06ImageHash $n
                    Assert ($e.Length -eq $boot.kernel_bytes) 'EXP06 ARM64 Image size would change boot v3 offsets'
                }
                'dtb' {CheckHash $hash $DTBHash $n}
                'dtbo' {CheckHash $hash $DTBOHash $n}
            }
        } finally {$stream.Dispose()}
    }
} finally {$z.Dispose()}
Write-Output 'EXP12 REAL SLOT-B OFFLINE PREFLIGHT: PASS'
Write-Output "BACKUPS sha256=verified count=4 device=pipa slot=_b"
Write-Output "BOOT version=3 original_kernel_bytes=$($boot.kernel_bytes) offset=$($boot.kernel_offset) generic_ramdisk_bytes=$($boot.generic_bytes) offset=$($boot.generic_offset)"
Write-Output "VENDOR_BOOT version=3 vendor_ramdisk_bytes=$($vendor.vendor_ramdisk_bytes) dtb_bytes=$($vendor.dtb_bytes) dtb_sha256=$($vendor.dtb_sha256)"
Write-Output "DTBO table_bytes=$($dtbo.total_bytes) entries=$($dtbo.entries) table_sha256=$($dtbo.table_sha256)"
Write-Output "VBMETA version=$($vbmeta.version) algorithm=$($vbmeta.algorithm) flags=$($vbmeta.flags) signature_verified=False"
Write-Output "EXP06 image_sha256=$Exp06ImageHash kernel_size_preserves_offsets=True dtb_dtbo_same_as_backup=True"
Write-Output 'IMPORTANT: Structural integrity only. NO AVB CRYPTO VERIFICATION, NO ROOT/RECOVERY/BOOT COMPATIBILITY TEST.'
Write-Output 'NO IMAGE CREATED. NO FILE MODIFIED. FLASH_READY=false'
