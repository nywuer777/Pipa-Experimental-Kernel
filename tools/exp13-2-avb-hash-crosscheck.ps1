# EXP13.2: Offline read-only match of AVB hash descriptors against 3 original slot-B backups.
# No salt, digest, signature, public key or property values are printed.
# Supports Windows PowerShell 5.1 and PowerShell 7.
param(
    [string]$BackupDir='C:\platform-tools\pipa_backup',
    [switch]$SelfTest
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$Known=@{
    'vbmeta_b.img'='86d703c2ea2f73a55aa86374329bd89ffd975c0e95e33645a156cfdc343889ff'
    'boot_b.img'='31f57cded5fa4b37426b4387b58c1c7330703a1c1a8a5aa5844b348fcbb78c2f4'
    'dtbo_b.img'='f4168f76d092362ac438543d74938d83e3e567a37abb16e4d61fe7ba764588e2'
    'vendor_boot_b.img'='a24ea921db6014a49f9895cc5c18efbb6c6674d697f25cde3b7a1670a643c28c'
}
function Require([bool]$OK,[string]$Why) {if(-not $OK){throw ('EXP13.2 REJECT: '+$Why)}}
function BE32([byte[]]$B,[int]$O) {
    Require ($O -ge 0 -and $O+4 -le $B.Length) 'BE32 offset'
    return (([long]$B[$O] -shl 24) -bor ([long]$B[$O+1] -shl 16) -bor ([long]$B[$O+2] -shl 8) -bor [long]$B[$O+3])
}
function BE64([byte[]]$B,[int]$O) {
    Require ($O -ge 0 -and $O+8 -le $B.Length) 'BE64 offset'
    return [decimal](BE32 $B $O)*[decimal]4294967296+[decimal](BE32 $B ($O+4))
}
function Name([byte[]]$B,[int]$O,[int]$N) {
    Require ($N -gt 0 -and $N -lt 65 -and $O -ge 0 -and $O+$N -le $B.Length) 'partition name bounds'
    $s=[Text.Encoding]::UTF8.GetString($B,$O,$N)
    Require ($s -cmatch '^[a-z0-9_]+$') 'unsafe partition name'
    return $s
}
function ParseHashes([byte[]]$B) {
    Require ($B.Length -eq 131072) 'unexpected original vbmeta partition size'
    Require ([Text.Encoding]::ASCII.GetString($B,0,4) -ceq 'AVB0') 'AVB0 magic'
    Require ((BE32 $B 4) -eq 1) 'AVB version'
    [decimal]$auth=BE64 $B 12; [decimal]$aux=BE64 $B 20
    [decimal]$dOff=BE64 $B 96; [decimal]$dSize=BE64 $B 104
    Require ((($auth % 64) -eq 0) -and (($aux % 64) -eq 0)) 'AVB auth/aux alignment'
    Require (([decimal]256+$auth+$aux) -le $B.Length) 'AVB blocks out of range'
    Require ($dOff -ge 0 -and $dSize -gt 0 -and $dSize -le $aux-$dOff -and $dSize%8 -eq 0 -and $dSize -le 16384) 'AVB descriptor range'
    $p=[int]([decimal]256+$auth+$dOff)
    $end=$p+[int]$dSize
    $out=New-Object System.Collections.Generic.List[object]
    $total=0
    while($p -lt $end) {
        Require ($total -lt 64 -and ($end-$p) -ge 16) 'too many descriptor headers'
        [decimal]$tag=BE64 $B $p; [decimal]$body=BE64 $B ($p+8)
        Require ($body%8 -eq 0 -and $body -le ($end-$p-16)) 'descriptor length'
        $next=$p+16+[int]$body
        if ($tag -eq 2) {
            # AvbHashDescriptor: 132 byte total fixed header (including 16 parent).
            Require ($next-$p -ge 132) 'hash descriptor truncated'
            $sz=BE64 $B ($p+16)
            $alg=[Text.Encoding]::ASCII.GetString($B,$p+24,32).Split([char]0)[0]
            $nameLen=BE32 $B ($p+56)
            $saltLen=BE32 $B ($p+60)
            $digLen=BE32 $B ($p+64)
            $flags=BE32 $B ($p+68)
            Require ($alg -ceq 'sha256') 'unexpected hash algorithm'
            Require ($digLen -eq 32) 'persistent or unexpected digest length unsupported'
            Require ($nameLen -gt 0 -and $nameLen -le 64 -and $saltLen -le 4096 -and $nameLen+$saltLen+$digLen -le $next-$p-132) 'hash fields outside descriptor'
            $name=Name $B ($p+132) ([int]$nameLen)
            $salt=New-Object byte[] ([int]$saltLen)
            if($saltLen -gt 0){[Array]::Copy($B,$p+132+[int]$nameLen,$salt,0,[int]$saltLen)}
            $digest=New-Object byte[] 32
            [Array]::Copy($B,$p+132+[int]$nameLen+[int]$saltLen,$digest,0,32)
            $out.Add([pscustomobject]@{partition=$name;image_bytes=[long]$sz;flags=$flags;salt=$salt;digest=$digest})
        }
        $p=$next
        $total++
    }
    Require ($p -eq $end -and $total -eq 15 -and $out.Count -eq 3) 'unexpected descriptor count'
    foreach($n in @('boot','dtbo','vendor_boot')) {
        Require ((@($out.ToArray() | Where-Object {$_.partition -ceq $n}).Count) -eq 1) "missing/duplicate AVB $n"
    }
    return @($out.ToArray())
}
function HashPrefix([IO.Stream]$S,[long]$Count,[byte[]]$Salt) {
    Require ($Count -gt 0 -and $Count -le $S.Length) 'hash descriptor image size exceeds actual partition data'
    $S.Position=0
    $h=[Security.Cryptography.SHA256]::Create()
    try {
        if($Salt.Length -gt 0){[void]$h.TransformBlock($Salt,0,$Salt.Length,$Salt,0)}
        [byte[]]$buf=New-Object byte[] (1024*1024)
        [long]$remaining=$Count
        while($remaining -gt 0){
            $count=[int][Math]::Min($remaining,$buf.Length)
            $read=$S.Read($buf,0,$count)
            Require ($read -gt 0) 'unexpected EOF while hashing'
            [void]$h.TransformBlock($buf,0,$read,$buf,0)
            $remaining-=$read
        }
        [void]$h.TransformFinalBlock([byte[]]@(),0,0)
        return ,([byte[]]$h.Hash.Clone())
    } finally {$h.Dispose()}
}
function EqualDigest([byte[]]$A,[byte[]]$B) {
    if($A.Length -ne $B.Length){return $false}
    $v=0
    for($i=0;$i -lt $A.Length;$i++){$v=$v -bor ($A[$i] -bxor $B[$i])}
    return $v -eq 0
}
function TestOnly {
    $data=[Text.Encoding]::ASCII.GetBytes('safe fixture')
    $salt=[byte[]](1,2,3,4,5)
    $stream=New-Object IO.MemoryStream(,$data)
    try {
        $actual=HashPrefix $stream $data.Length $salt
        $joined=New-Object byte[] ($salt.Length+$data.Length)
        [Array]::Copy($salt,$joined,$salt.Length)
        [Array]::Copy($data,0,$joined,$salt.Length,$data.Length)
        $h=[Security.Cryptography.SHA256]::Create()
        try {$expected=$h.ComputeHash($joined)}finally{$h.Dispose()}
        Require (EqualDigest $actual $expected) 'salt+image prefix SHA mismatch'
        $actual[0]=$actual[0] -bxor 255
        Require (-not (EqualDigest $actual $expected)) 'tampered digest accepted'
        $rejected=$false
        try{$null=HashPrefix $stream ($data.Length+1) $salt}catch{$rejected=$true}
        Require $rejected 'out-of-bounds hash request accepted'
        Write-Output 'EXP13.2 SYNTHETIC SALTED HASH TEST: PASS'
        Write-Output 'NO PRIVATE FILES USED. NO DIGEST PRINTED. FLASH_READY=false'
    } finally {$stream.Dispose()}
}
if($SelfTest){TestOnly;return}
foreach($name in $Known.Keys) {
    $file=Join-Path $BackupDir $name
    Require ([IO.File]::Exists($file)) "missing backup: $name"
    $got=(Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash.ToLowerInvariant()
    Require ($got -ceq $Known[$name]) "backup integrity mismatch: $name"
}
$vb=([IO.File]::ReadAllBytes((Join-Path $BackupDir 'vbmeta_b.img')))
$descs=ParseHashes $vb
$ends=@{boot=32204801;vendor_boot=20878874;dtbo=688455}
$allMatched=$true
Write-Output 'EXP13.2 REAL SLOT-B AVB DESCRIPTOR DIGEST CROSS-CHECK'
Write-Output 'BACKUPS: all four input files SHA256 verified; no contents disclosed'
foreach($d in $descs) {
    $input=Join-Path $BackupDir ($d.partition+'_b.img')
    $file=[IO.File]::OpenRead($input)
    try {
        $calc=HashPrefix $file $d.image_bytes $d.salt
        $matched=EqualDigest $calc $d.digest
        $covers=$d.image_bytes -ge $ends[$d.partition]
        if(-not $matched){$allMatched=$false}
        $state=if($matched){'MATCH'}else{'MISMATCH'}
        $coverage=if($covers){'YES'}else{'NO'}
        Write-Output "PARTITION name=$($d.partition) descriptor_hash=$state hashed_bytes=$($d.image_bytes) known_used_end=$($ends[$d.partition]) covers_known_payload=$coverage flags=$($d.flags)"
    } finally {$file.Dispose()}
}
$status=if($allMatched){'ALL_THREE_MATCH'}else{'ONE_OR_MORE_MISMATCH'}
Write-Output "RESULT=$status"
Write-Output 'INTERPRETATION: compares salted SHA256 descriptor hash to same-length backup prefix; no signature/trust/active policy/rollback verification.'
Write-Output 'A mismatch does not by itself prove corruption: descriptors may describe other image builds or ignored metadata.'
Write-Output 'NO PARTITIONS MODIFIED. NO IMAGE CREATED. FLASH_READY=false'
