# EXP13.1: Offline, SHA-pinned, redacted AVB partition descriptor report.
# Reads the user's original vbmeta_b.img; prints partition names and flags only.
# Never prints public keys, salts, hashes, digests, property values or signatures.
param(
  [string]$VbmetaPath='C:\platform-tools\pipa_backup\vbmeta_b.img',
  [switch]$SelfTest
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$ExpectedHash='86d703c2ea2f73a55aa86374329bd89ffd975c0e95e33645a156cfdc343889ff'
function Check([bool]$Ok,[string]$Why){
  if(-not $Ok){throw ('EXP13.1 REJECT: '+$Why)}
}
function Be32([byte[]]$B,[int]$O){
  Check ($O -ge 0 -and ($O+4) -le $B.Length) 'be32 out of bounds'
  return (([long]$B[$O] -shl 24) -bor ([long]$B[$O+1] -shl 16) -bor ([long]$B[$O+2] -shl 8) -bor ([long]$B[$O+3]))
}
function Be64([byte[]]$B,[int]$O){
  Check ($O -ge 0 -and ($O+8) -le $B.Length) 'be64 out of bounds'
  return [decimal](Be32 $B $O)*[decimal]4294967296+[decimal](Be32 $B ($O+4))
}
function TextAt([byte[]]$B,[int]$O,[int]$N){
  Check ($N -gt 0 -and $N -le 128 -and $O -ge 0 -and $O+$N -le $B.Length) 'invalid name bytes'
  $raw=[Text.Encoding]::UTF8.GetString($B,$O,$N)
  Check ($raw -cmatch '^[A-Za-z0-9_.-]+$') 'partition name not printable/safe'
  return $raw
}
function ReadDescriptorNames([byte[]]$B){
  Check ($B.Length -ge 320 -and ([Text.Encoding]::ASCII.GetString($B,0,4) -ceq 'AVB0')) 'invalid vbmeta'
  $auth=Be64 $B 12
  $aux=Be64 $B 20
  $descOff=Be64 $B 96
  $descSize=Be64 $B 104
  $flags=Be32 $B 120
  Check ((Be32 $B 4) -eq 1) 'unsupported AVB major'
  Check (($auth%64) -eq 0 -and ($aux%64) -eq 0) 'unaligned auth/aux'
  Check (($descSize%8) -eq 0 -and $descSize -ge 16 -and $descSize -le 16384) 'invalid descriptors size'
  Check ($descOff -ge 0 -and $descOff -le $aux -and $descSize -le $aux-$descOff) 'descriptors outside auxiliary'
  Check (([decimal]256+$auth+$aux) -le $B.Length) 'AVB auxiliary beyond partition'
  $pos=[int]([decimal]256+$auth+$descOff)
  $end=$pos+[int]$descSize
  $output=New-Object System.Collections.Generic.List[object]
  $counts=@{chain=0;hash=0;hashtree=0;other=0}
  while($pos -lt $end){
    Check ($output.Count -lt 128 -and ($end-$pos) -ge 16) 'descriptor count/header'
    $tag=Be64 $B $pos
    $body=Be64 $B ($pos+8)
    Check (($body%8) -eq 0 -and $body -le ($end-$pos-16)) 'descriptor size out of bounds'
    $next=$pos+16+[int]$body
    switch ([string]$tag){
      '4' {
        # AvbChainPartitionDescriptor: fixed 92-byte struct (including 16-byte parent)
        Check (($next-$pos) -ge 92) 'truncated chain descriptor'
        $rollback=Be32 $B ($pos+16)
        $namelen=Be32 $B ($pos+20)
        $keylen=Be32 $B ($pos+24)
        $localflags=Be32 $B ($pos+28)
        Check ($namelen -gt 0 -and $namelen -le 128 -and ($namelen+$keylen) -le ($next-$pos-92)) 'chain name/key bounds'
        $name=TextAt $B ($pos+92) ([int]$namelen)
        $output.Add([pscustomobject]@{kind='chain';name=$name;flags=$localflags;rollback_location=$rollback;size_bytes=$null;hash_algorithm=$null})
        $counts.chain++
      }
      '2' {
        # AvbHashDescriptor: fixed 132-byte struct (including parent)
        Check (($next-$pos) -ge 132) 'truncated hash descriptor'
        $size=Be64 $B ($pos+16)
        $alg=[Text.Encoding]::ASCII.GetString($B,$pos+24,32).Split([char]0)[0]
        $namelen=Be32 $B ($pos+56)
        $saltlen=Be32 $B ($pos+60)
        $digestlen=Be32 $B ($pos+64)
        $localflags=Be32 $B ($pos+68)
        Check ($namelen -gt 0 -and $namelen -le 128 -and ([decimal]$namelen+$saltlen+$digestlen) -le ($next-$pos-132)) 'hash name/salt/digest bounds'
        Check ($alg -cmatch '^(sha256|sha512)$') 'unknown hash algorithm'
        $name=TextAt $B ($pos+132) ([int]$namelen)
        $output.Add([pscustomobject]@{kind='hash';name=$name;flags=$localflags;rollback_location=$null;size_bytes=[string]$size;hash_algorithm=$alg})
        $counts.hash++
      }
      '1' {
        # AvbHashtreeDescriptor: fixed 180-byte struct (including parent)
        Check (($next-$pos) -ge 180) 'truncated hashtree descriptor'
        $size=Be64 $B ($pos+20)
        $alg=[Text.Encoding]::ASCII.GetString($B,$pos+72,32).Split([char]0)[0]
        $namelen=Be32 $B ($pos+104)
        $saltlen=Be32 $B ($pos+108)
        $digestlen=Be32 $B ($pos+112)
        $localflags=Be32 $B ($pos+116)
        Check ($namelen -gt 0 -and $namelen -le 128 -and ([decimal]$namelen+$saltlen+$digestlen) -le ($next-$pos-180)) 'hashtree name/salt/root digest bounds'
        Check ($alg -cmatch '^(sha256|sha512)$') 'unknown hashtree algorithm'
        $name=TextAt $B ($pos+180) ([int]$namelen)
        $output.Add([pscustomobject]@{kind='hashtree';name=$name;flags=$localflags;rollback_location=$null;size_bytes=[string]$size;hash_algorithm=$alg})
        $counts.hashtree++
      }
      default {
        # Skip other descriptor values, properties and data. Never print raw bytes.
        $counts.other++
      }
    }
    $pos=$next
  }
  Check ($pos -eq $end) 'descriptor traversal mismatch'
  return @{
    flags=$flags;count=$output.Count+$counts.other
    summaries=@($output.ToArray())
    kinds=$counts
  }
}
function WriteBe32([byte[]]$B,[int]$O,[long]$V){
  $B[$O]=[byte](($V -shr 24) -band 255)
  $B[$O+1]=[byte](($V -shr 16) -band 255)
  $B[$O+2]=[byte](($V -shr 8) -band 255)
  $B[$O+3]=[byte]($V -band 255)
}
function WriteBe64([byte[]]$B,[int]$O,[long]$V){
  WriteBe32 $B $O ([long]($V -shr 32))
  WriteBe32 $B ($O+4) ([long]($V -band 4294967295))
}
function TestFixture {
  # Three realistic synthetic descriptors: chain "vbmt", hash "boot", hashtree "syst".
  [byte[]]$b=New-Object byte[] 768
  [Text.Encoding]::ASCII.GetBytes('AVB0').CopyTo($b,0)
  WriteBe32 $b 4 1
  WriteBe64 $b 20 512
  WriteBe64 $b 104 440
  WriteBe32 $b 120 3
  $p=256
  WriteBe64 $b $p 4; WriteBe64 $b ($p+8) 88
  WriteBe32 $b ($p+16) 2; WriteBe32 $b ($p+20) 4; WriteBe32 $b ($p+24) 8
  [Text.Encoding]::ASCII.GetBytes('vbmt').CopyTo($b,$p+92)
  $p+=104
  WriteBe64 $b $p 2; WriteBe64 $b ($p+8) 128
  WriteBe64 $b ($p+16) 1024
  [Text.Encoding]::ASCII.GetBytes('sha256').CopyTo($b,$p+24)
  WriteBe32 $b ($p+56) 4; WriteBe32 $b ($p+60) 4; WriteBe32 $b ($p+64) 4
  [Text.Encoding]::ASCII.GetBytes('boot').CopyTo($b,$p+132)
  $p+=144
  WriteBe64 $b $p 1; WriteBe64 $b ($p+8) 176
  WriteBe64 $b ($p+20) 2048
  [Text.Encoding]::ASCII.GetBytes('sha256').CopyTo($b,$p+72)
  WriteBe32 $b ($p+104) 4; WriteBe32 $b ($p+108) 4; WriteBe32 $b ($p+112) 4
  [Text.Encoding]::ASCII.GetBytes('syst').CopyTo($b,$p+180)
  $v=ReadDescriptorNames $b
  Check ($v.count -eq 3 -and $v.kinds.chain -eq 1 -and $v.kinds.hash -eq 1 -and $v.kinds.hashtree -eq 1) 'synthetic summary count'
  Check ($v.summaries[0].name -ceq 'vbmt' -and $v.summaries[1].name -ceq 'boot' -and $v.summaries[2].name -ceq 'syst') 'synthetic partition names'
  $p=256
  WriteBe32 $b ($p+20) 200
  $failed=$false
  try{$null=ReadDescriptorNames $b}catch{$failed=$true}
  Check $failed 'malformed chain partition name was accepted'
  Write-Output 'EXP13.1 SYNTHETIC 3-DESCRIPTOR NAMES TEST: PASS'
  Write-Output 'NO REAL BACKUP USED. NO KEYS OR DIGESTS OUTPUT. FLASH_READY=false'
}
if($SelfTest){TestFixture;return}
Check ([IO.File]::Exists($VbmetaPath)) 'vbmeta_b.img not found'
$sha=(Get-FileHash -LiteralPath $VbmetaPath -Algorithm SHA256).Hash.ToLowerInvariant()
Check ($sha -ceq $ExpectedHash) 'vbmeta_b.img hash does not match pinned backup'
$b=[IO.File]::ReadAllBytes($VbmetaPath)
Check ($b.Length -eq 131072) 'unexpected vbmeta partition length'
$r=ReadDescriptorNames $b
Check ($r.count -eq 15 -and $r.kinds.chain -eq 1 -and $r.kinds.hash -eq 3 -and $r.kinds.hashtree -eq 2) 'unexpected count/kind of AVB descriptors'
Write-Output 'EXP13.1 REAL AVB PARTITION NAME AUDIT: PASS'
Write-Output "SOURCE=vbmeta_b.img verified_sha256=$sha"
Write-Output "DESCRIPTORS total=$($r.count) chain=$($r.kinds.chain) hash=$($r.kinds.hash) hashtree=$($r.kinds.hashtree) other=$($r.kinds.other)"
Write-Output "VBMETA flags=$($r.flags) signature_verified=False trusted_key_verified=False hardware_rollback_checked=False"
foreach($d in $r.summaries){
  $line="PARTITION kind=$($d.kind) name=$($d.name) flags=$($d.flags)"
  if($null -ne $d.rollback_location){$line+=" rollback_location=$($d.rollback_location)"}
  if($null -ne $d.size_bytes){$line+=" image_bytes=$($d.size_bytes) algorithm=$($d.hash_algorithm)"}
  Write-Output $line
}
Write-Output 'SECURITY: names are descriptor CLAIMS, not evidence of currently enforced boot verification.'
Write-Output 'NO PRIVATE KEYS, PUBLIC KEYS, SALTS, DIGESTS, SIGNATURES OR PROPERTY VALUES DISPLAYED.'
Write-Output 'NO FILE MODIFIED. NO BOOT IMAGE CREATED. FLASH_READY=false'
