# EXP13: inspect the original slot-B vbmeta AVB descriptor layout OFFLINE.
# No modification, ADB, network calls, images or flash/boot commands.
# Supported on Windows PowerShell 5.1 and PowerShell 7.
param(
    [string]$VbmetaPath='C:\platform-tools\pipa_backup\vbmeta_b.img',
    [switch]$SelfTest
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$KnownHash='86d703c2ea2f73a55aa86374329bd89ffd975c0e95e33645a156cfdc343889ff'
function Require([bool]$Condition,[string]$Message){
    if(-not $Condition){throw ('EXP13 REJECT: '+$Message)}
}
function U32([byte[]]$B,[int]$I){
    Require ($I -ge 0 -and ($I+4) -le $B.Length) 'uint32 outside data'
    return (([long]$B[$I] -shl 24) -bor ([long]$B[$I+1] -shl 16) -bor ([long]$B[$I+2] -shl 8) -bor ([long]$B[$I+3]))
}
function U64([byte[]]$B,[int]$I){
    Require ($I -ge 0 -and ($I+8) -le $B.Length) 'uint64 outside data'
    return ([decimal](U32 $B $I)*[decimal]4294967296)+[decimal](U32 $B ($I+4))
}
function CheckSpan([decimal]$Offset,[decimal]$Count,[decimal]$Size,[string]$What){
    Require ($Offset -ge 0 -and $Count -ge 0 -and $Offset -le $Size -and $Count -le ($Size-$Offset)) ($What+' outside range')
}
function Inspect([byte[]]$Bytes) {
    Require ($Bytes.Length -ge 256) 'vbmeta shorter than 256-byte header'
    Require ([Text.Encoding]::ASCII.GetString($Bytes,0,4) -ceq 'AVB0') 'missing AVB0 magic'
    $major=U32 $Bytes 4; $minor=U32 $Bytes 8
    Require ($major -eq 1) 'unexpected required libavb major version'
    $auth=U64 $Bytes 12; $aux=U64 $Bytes 20
    Require (($auth%64) -eq 0 -and ($aux%64) -eq 0) 'AVB authentication/auxiliary alignment'
    $algorithm=U32 $Bytes 28
    $hashOff=U64 $Bytes 32; $hashSize=U64 $Bytes 40
    $sigOff=U64 $Bytes 48; $sigSize=U64 $Bytes 56
    $keyOff=U64 $Bytes 64; $keySize=U64 $Bytes 72
    $keyMetaOff=U64 $Bytes 80; $keyMetaSize=U64 $Bytes 88
    $descOff=U64 $Bytes 96; $descSize=U64 $Bytes 104
    $rollback=U64 $Bytes 112
    $flags=U32 $Bytes 120
    $rollbackLoc=U32 $Bytes 124
    $rawString=[Text.Encoding]::ASCII.GetString($Bytes,128,48)
    $release=$rawString.Split([char]0)[0]
    $imageBytes=[decimal]256+$auth+$aux
    Require ($imageBytes -le $Bytes.Length) 'AVB header blocks extend beyond vbmeta partition'
    CheckSpan $hashOff $hashSize $auth 'hash'
    CheckSpan $sigOff $sigSize $auth 'signature'
    CheckSpan $keyOff $keySize $aux 'public key'
    CheckSpan $keyMetaOff $keyMetaSize $aux 'public key metadata'
    CheckSpan $descOff $descSize $aux 'descriptors'
    Require ($descSize -le 16*1024*1024) 'descriptor size too large'
    Require (($descSize % 8) -eq 0) 'descriptor block misalignment'
    $descList=New-Object System.Collections.Generic.List[object]
    [decimal]$cursor=[decimal]256+$auth+$descOff
    [decimal]$end=$cursor+$descSize
    $named=@{'0'='property';'1'='hashtree';'2'='hash';'3'='kernel_cmdline';'4'='chain_partition'}
    while($cursor -lt $end) {
        Require ($descList.Count -lt 2048) 'too many descriptors'
        Require (($end-$cursor) -ge 16) 'truncated descriptor header'
        $p=[int]$cursor
        $tag=U64 $Bytes $p
        $body=U64 $Bytes ($p+8)
        Require (($body%8) -eq 0) 'descriptor body alignment invalid'
        Require ($body -le ($end-$cursor-16)) 'descriptor body beyond descriptors span'
        $label=if($named.ContainsKey([string]$tag)){$named[[string]$tag]}else{'unknown'}
        $descList.Add([pscustomobject]@{tag=[string]$tag;kind=$label;body_bytes=[int]$body})
        $cursor+=16+$body
    }
    Require ($cursor -eq $end) 'descriptor traversal did not consume exact span'
    $disabledTree=(($flags -band 1) -ne 0)
    $disabledVerify=(($flags -band 2) -ne 0)
    return [pscustomobject]@{
        required_avb_version=("$major.$minor")
        image_bytes=[int]$imageBytes
        authentication_bytes=[int]$auth
        auxiliary_bytes=[int]$aux
        algorithm_type=$algorithm
        hash_bytes=[int]$hashSize
        signature_bytes=[int]$sigSize
        public_key_bytes=[int]$keySize
        descriptors_bytes=[int]$descSize
        descriptor_count=$descList.Count
        descriptors=@($descList.ToArray())
        rollback_index=[string]$rollback
        rollback_index_location=$rollbackLoc
        flags=$flags
        hashtree_disabled=$disabledTree
        verification_disabled=$disabledVerify
        release_string=$release
        signature_cryptographically_verified=$false
        known_trusted_public_key_checked=$false
        hardware_rollback_storage_compared=$false
        flash_ready=$false
    }
}
function MakeSynthetic([bool]$Damage){
    # Header(256) + auth(0) + aux(64) with one 16-byte property descriptor.
    [byte[]]$b=New-Object byte[] 320
    [Text.Encoding]::ASCII.GetBytes('AVB0').CopyTo($b,0)
    $b[7]=1
    $b[27]=64
    $b[111]=16
    $b[123]=3
    $b[124]=0
    if($Damage){
        # Declares impossible 0x10000000 descriptor body; structural parser must reject.
        $b[256+15]=1
    }
    return ,$b
}
if($SelfTest){
    $v=Inspect (MakeSynthetic $false)
    Require ($v.descriptor_count -eq 1 -and $v.flags -eq 3) 'synthetic valid header'
    Require ($v.verification_disabled -and $v.hashtree_disabled) 'AVB flags interpretation'
    $rejected=$false
    try{$null=Inspect (MakeSynthetic $true)}catch{$rejected=$true}
    Require $rejected 'bad descriptor body was accepted'
    Write-Output 'EXP13 SYNTHETIC AVB HEADER AND DESCRIPTOR TEST: PASS'
    Write-Output 'NO REAL BACKUP USED. FLASH_READY=false'
    return
}
Require ([IO.File]::Exists($VbmetaPath)) 'vbmeta_b.img backup not found'
$hash=(Get-FileHash -LiteralPath $VbmetaPath -Algorithm SHA256).Hash.ToLowerInvariant()
Require ($hash -ceq $KnownHash) ('backup hash changed: '+$hash)
$stream=[IO.File]::OpenRead($VbmetaPath)
try {
    Require ($stream.Length -eq 131072) 'unexpected vbmeta partition size'
    [byte[]]$b=New-Object byte[] $stream.Length
    $offset=0
    while($offset -lt $b.Length){
        $n=$stream.Read($b,$offset,$b.Length-$offset)
        Require ($n -gt 0) 'unexpected end of vbmeta partition'
        $offset+=$n
    }
} finally {$stream.Dispose()}
$r=Inspect $b
Write-Output 'EXP13 REAL SLOT-B VBMETA STRUCTURAL AUDIT: PASS'
Write-Output "SOURCE=vbmeta_b.img sha256=$hash partition_bytes=$($b.Length)"
Write-Output "AVB required_version=$($r.required_avb_version) algorithm_type=$($r.algorithm_type) release=$($r.release_string)"
Write-Output "BLOCKS total_bytes=$($r.image_bytes) auth_bytes=$($r.authentication_bytes) aux_bytes=$($r.auxiliary_bytes)"
Write-Output "CRYPTO_FIELDS hash_bytes=$($r.hash_bytes) signature_bytes=$($r.signature_bytes) key_bytes=$($r.public_key_bytes) signature_verified=False"
Write-Output "POLICY flags=$($r.flags) hashtree_disabled=$($r.hashtree_disabled) verification_disabled=$($r.verification_disabled)"
Write-Output "ROLLBACK index=$($r.rollback_index) location=$($r.rollback_index_location) hardware_storage_checked=False"
Write-Output "DESCRIPTORS count=$($r.descriptor_count) bytes=$($r.descriptors_bytes)"
foreach($d in $r.descriptors){
    Write-Output "  descriptor_tag=$($d.tag) kind=$($d.kind) body_bytes=$($d.body_bytes)"
}
Write-Output 'LIMITS: flags are header metadata; no AVB signature verification, no bootloader policy, no rollback storage read.'
Write-Output 'NO FILE MODIFIED. NO BOOT IMAGE CREATED. FLASH_READY=false'
