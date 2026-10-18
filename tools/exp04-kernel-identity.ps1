# Pipa EXP04 read-only binary identity gate — no external tools, no writes.
param([string]$BackupDir = 'C:\platform-tools\pipa_backup')
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$Exp01ImageBytes = [long]30349328
$Exp01ImageSHA256 = 'bb20a6a936ff730d89dab8ca354ccb0ea7fe427594b8b60d2e1c424873970b11'

function ReadAt {
    param([System.IO.FileStream]$Stream,[long]$Offset,[int]$Count)
    if ($Offset -lt 0 -or $Count -lt 0 -or $Offset -gt $Stream.Length -or $Count -gt ($Stream.Length - $Offset)) {
        throw "Invalid bounds: $Offset + $Count"
    }
    [void]$Stream.Seek($Offset, [System.IO.SeekOrigin]::Begin)
    $data = New-Object byte[] $Count
    $n = 0
    while ($n -lt $Count) {
        $got = $Stream.Read($data, $n, $Count-$n)
        if ($got -le 0) { throw 'Unexpected end of image' }
        $n += $got
    }
    return ,$data
}
function LE32 { param([byte[]]$Data,[int]$At)
    return ([long][BitConverter]::ToUInt32($Data,$At))
}
function BE32 {param([byte[]]$Data,[int]$At)
    return (([long]$Data[$At] -shl 24) -bor ([long]$Data[$At+1] -shl 16) -bor ([long]$Data[$At+2] -shl 8) -bor [long]$Data[$At+3])
}
function RangeSHA256 {
    param([System.IO.FileStream]$Stream,[long]$Start,[long]$Count)
    if($Start -lt 0 -or $Count -le 0 -or $Start -gt $Stream.Length -or $Count -gt ($Stream.Length-$Start)) {
        throw "Hash range exceeds source: $Start + $Count"
    }
    [void]$Stream.Seek($Start,[System.IO.SeekOrigin]::Begin)
    $hash=[System.Security.Cryptography.SHA256]::Create()
    try {
        [byte[]]$buf=New-Object byte[] (1024*1024)
        [long]$remaining=$Count
        while($remaining -gt 0) {
            $take=[int][Math]::Min([long]$buf.Length,$remaining)
            $read=$Stream.Read($buf,0,$take)
            if($read -le 0){throw 'Unexpected EOF hashing range'}
            [void]$hash.TransformBlock($buf,0,$read,$buf,0)
            $remaining -= $read
        }
        [void]$hash.TransformFinalBlock([byte[]]@(),0,0)
        return ([BitConverter]::ToString($hash.Hash)).Replace('-','').ToLowerInvariant()
    } finally { $hash.Dispose() }
}
function Align {param([long]$X,[long]$By)
    return ([long]([Math]::Ceiling($X/[double]$By)*$By))
}

if(-not [IO.Directory]::Exists($BackupDir)){throw "Backup directory missing: $BackupDir"}

$boot=[IO.File]::OpenRead((Join-Path $BackupDir 'boot_b.img'))
try{
    $header=ReadAt $boot 0 4096
    if([Text.Encoding]::ASCII.GetString($header,0,8) -ne 'ANDROID!' -or (LE32 $header 40) -ne 3 -or (LE32 $header 20) -ne 1580){
        throw 'Expected boot v3 header was not found'
    }
    $kernelBytes=LE32 $header 8
    $ramdiskBytes=LE32 $header 12
    $kStart=[long]4096
    $rStart=$kStart+(Align $kernelBytes 4096)
    if($kernelBytes -lt 60 -or $rStart -gt $boot.Length -or $ramdiskBytes -gt ($boot.Length-$rStart)){throw 'Boot v3 payload bounds invalid'}
    $magic=ReadAt $boot ($kStart+56) 4
    if([Text.Encoding]::ASCII.GetString($magic,0,4) -ne 'ARMd'){throw 'Boot kernel is not ARM64 Image'}
    $oldHash=RangeSHA256 $boot $kStart $kernelBytes
    $ramdiskHash=RangeSHA256 $boot $rStart $ramdiskBytes
    $prefixResult='NOT_COMPARABLE'
    $prefixHash='n/a'
    if($kernelBytes -ge $Exp01ImageBytes){
        $prefixHash=RangeSHA256 $boot $kStart $Exp01ImageBytes
        if($prefixHash -eq $Exp01ImageSHA256){$prefixResult='IDENTICAL_PREFIX'}
        else{$prefixResult='DIFFERENT_PREFIX'}
    }
    $tail=ReadAt $boot ($kStart+$kernelBytes-8) 8
    $tailHex=([BitConverter]::ToString($tail)).Replace('-','').ToLowerInvariant()
    Write-Output "BOOT kernel_bytes=$kernelBytes kernel_sha256=$oldHash"
    Write-Output "BOOT ramdisk_bytes=$ramdiskBytes ramdisk_sha256=$ramdiskHash"
    Write-Output "EXP01 compiled_bytes=$Exp01ImageBytes compiled_sha256=$Exp01ImageSHA256"
    Write-Output "COMPARE source_kernel_prefix_sha256=$prefixHash exp01_match=$prefixResult size_delta=$($kernelBytes-$Exp01ImageBytes)"
    Write-Output "BOOT kernel_last_8_bytes_hex=$tailHex"
} finally {$boot.Dispose()}

$vendor=[IO.File]::OpenRead((Join-Path $BackupDir 'vendor_boot_b.img'))
try{
    $h=ReadAt $vendor 0 4096
    if([Text.Encoding]::ASCII.GetString($h,0,8) -ne 'VNDRBOOT' -or (LE32 $h 8) -ne 3){throw 'Expected vendor_boot v3 missing'}
    $page=LE32 $h 12; $rSize=LE32 $h 24; $hdr=LE32 $h 2096; $dtbSize=LE32 $h 2100
    if($page -lt 2048 -or $page -gt 65536 -or ($page -band ($page-1)) -ne 0 -or $hdr -ne 2112){throw 'Unexpected vendor_boot layout'}
    $rStart=Align $hdr $page; $dtbStart=$rStart+(Align $rSize $page)
    $vRamdiskSha=RangeSHA256 $vendor $rStart $rSize
    $dtbMagic=ReadAt $vendor $dtbStart 4
    if((BE32 $dtbMagic 0) -ne 3490578157){throw 'Invalid vendor DTB magic'}
    $dtbHash=RangeSHA256 $vendor $dtbStart $dtbSize
    Write-Output "VENDOR ramdisk_bytes=$rSize ramdisk_sha256=$vRamdiskSha dtb_bytes=$dtbSize dtb_sha256=$dtbHash"
} finally {$vendor.Dispose()}

$dtbo=[IO.File]::OpenRead((Join-Path $BackupDir 'dtbo_b.img'))
try{
    $h=ReadAt $dtbo 0 32
    if((BE32 $h 0) -ne 3619138334){throw 'Invalid DTBO header magic'}
    $total=BE32 $h 4
    $dtboHash=RangeSHA256 $dtbo 0 $total
    Write-Output "DTBO table_bytes=$total table_sha256=$dtboHash"
} finally{$dtbo.Dispose()}

$avb=[IO.File]::OpenRead((Join-Path $BackupDir 'vbmeta_b.img'))
try{
    $h=ReadAt $avb 0 256
    if([Text.Encoding]::ASCII.GetString($h,0,4) -ne 'AVB0'){throw 'Invalid vbmeta header'}
    $flags=BE32 $h 120
    $hashtreeDisabled=(($flags -band 1) -ne 0)
    $verificationDisabled=(($flags -band 2) -ne 0)
    Write-Output "AVB flags=$flags hashtree_disabled=$hashtreeDisabled verification_disabled=$verificationDisabled signature_checked=False"
} finally{$avb.Dispose()}
Write-Output 'PASS: read-only kernel and payload SHA-256 collection completed. NO BOOT.IMG GENERATED.'
Write-Output 'NOT PROVEN: matching kernel ABI, installed root, AVB signature chain, or boot success.'
