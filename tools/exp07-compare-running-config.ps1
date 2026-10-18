# EXP07 - compare the active kernel's proc config with the successful EXP06 build.
# Only reads two local files; no network, ADB, root, image writes or flashing.
param(
    [Parameter(Mandatory=$true)][string]$LiveConfigGz,
    [Parameter(Mandatory=$true)][string]$Exp06Zip
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$expectedZip='e32af6b61163fba4724211986823fc4ffab759956d213ef15b7fcda042241402'
$expectedImage='7b3c971a6bd92e8e609e4c56fb6e33df78a7668463e9bcfc342aa1cdee9a0033'
$zipEntryName='exp06-work/out/.config'
if(-not [IO.File]::Exists($LiveConfigGz)){throw "Active kernel config not found: $LiveConfigGz"}
if(-not [IO.File]::Exists($Exp06Zip)){throw "EXP06 artifact not found: $Exp06Zip"}
$sha=(Get-FileHash -LiteralPath $Exp06Zip -Algorithm SHA256).Hash.ToLowerInvariant()
if($sha -ne $expectedZip){throw "EXP06 artifact hash mismatch: $sha"}
Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem
$liveFile=[IO.File]::OpenRead($LiveConfigGz)
try {
    $gzip=New-Object IO.Compression.GZipStream($liveFile,[IO.Compression.CompressionMode]::Decompress)
    try {
        $reader=New-Object IO.StreamReader($gzip,[Text.Encoding]::UTF8)
        try{$liveText=$reader.ReadToEnd()}finally{$reader.Dispose()}
    }finally{$gzip.Dispose()}
}finally{$liveFile.Dispose()}
$archive=[IO.Compression.ZipFile]::OpenRead($Exp06Zip)
try {
    $entry=$archive.GetEntry($zipEntryName)
    if($null -eq $entry){throw "Missing .config in EXP06 ZIP: $zipEntryName"}
    $stream=$entry.Open()
    try {
        $reader=New-Object IO.StreamReader($stream,[Text.Encoding]::UTF8)
        try{$expText=$reader.ReadToEnd()}finally{$reader.Dispose()}
    }finally{$stream.Dispose()}
}finally{$archive.Dispose()}
function ParseConfig([string]$txt){
    $values=@{}
    foreach($line in ($txt -split "\r?\n")){
        if($line -match '^(CONFIG_[A-Za-z0-9_]+)=(.*)$'){
            $values[$Matches[1]]=$Matches[2]
        } elseif($line -match '^# (CONFIG_[A-Za-z0-9_]+) is not set$'){
            $values[$Matches[1]]='n'
        }
    }
    return ,$values
}
$live=ParseConfig $liveText
$exp=ParseConfig $expText
if($live.Count -lt 300 -or $exp.Count -lt 300){throw 'Config missing or too few Kconfig entries'}
$keys=@($live.Keys+$exp.Keys | Sort-Object -Unique)
$diff=@()
foreach($k in $keys){
    $a=if($live.ContainsKey($k)){$live[$k]}else{'<not listed>'}
    $b=if($exp.ContainsKey($k)){$exp[$k]}else{'<not listed>'}
    if($a -cne $b){$diff+= $k}
}
$critical=@(
'CONFIG_MODULES','CONFIG_MODVERSIONS','CONFIG_KSU','CONFIG_KSU_MANUAL_HOOK',
'CONFIG_KSU_FEATURE_ADBROOT','CONFIG_PIPA_EXP_SUGOV',
'CONFIG_PIPA_EXP_SUGOV_RATE_LIMIT_US','CONFIG_CPU_FREQ_GOV_SCHEDUTIL',
'CONFIG_CPU_FREQ_DEFAULT_GOV_PERFORMANCE','CONFIG_CPU_FREQ_DEFAULT_GOV_SCHEDUTIL',
'CONFIG_LOCALVERSION_AUTO','CONFIG_CC_IS_CLANG','CONFIG_LTO_CLANG_THIN',
'CONFIG_IKCONFIG','CONFIG_IKCONFIG_PROC','CONFIG_ARM64',
'CONFIG_SECURITY_SELINUX','CONFIG_BPF','CONFIG_KALLSYMS','CONFIG_THERMAL'
)
Write-Output 'PIPA EXP07 - ACTUAL CONFIG VS AOSP CLANG21 BUILD'
Write-Output "LIVE config.gz_sha256=$((Get-FileHash -LiteralPath $LiveConfigGz -Algorithm SHA256).Hash.ToLowerInvariant()) entries=$($live.Count)"
Write-Output "EXP06 zip_sha256=$sha image_sha256=$expectedImage entries=$($exp.Count)"
Write-Output "DIFF config_keys_total=$($keys.Count) changed_or_missing=$($diff.Count) identical=$($diff.Count -eq 0)"
Write-Output 'CRITICAL FLAGS (live | exp06):'
foreach($k in $critical){
    $a=if($live.ContainsKey($k)){$live[$k]}else{'<not listed>'}
    $b=if($exp.ContainsKey($k)){$exp[$k]}else{'<not listed>'}
    $mark=if($a -cne $b){'DIFF'}else{'SAME'}
    Write-Output "  $mark $k live=$a exp06=$b"
}
$other=@($diff | Where-Object {$_ -notin $critical})
Write-Output "OTHER_DIFFERENCES shown=$([Math]::Min($other.Count,60)) total=$($other.Count)"
foreach($k in ($other | Select-Object -First 60)){
    $a=if($live.ContainsKey($k)){$live[$k]}else{'<not listed>'}
    $b=if($exp.ContainsKey($k)){$exp[$k]}else{'<not listed>'}
    if($a.Length -gt 110){$a=$a.Substring(0,110)+'...'}
    if($b.Length -gt 110){$b=$b.Substring(0,110)+'...'}
    Write-Output "  DIFF $k live=$a exp06=$b"
}
Write-Output 'PASS: read-only EXP07 Kconfig comparison complete. No partition image changed.'
Write-Output 'NOT PROVEN: boot functionality, root operation, ABI or performance.'
