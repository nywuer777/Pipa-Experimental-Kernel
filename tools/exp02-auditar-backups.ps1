# EXP02 — somente leitura dos backups locais do Xiaomi Pad 6.
# Uso: powershell -ExecutionPolicy Bypass -File .\tools\exp02-auditar-backups.ps1
# Nunca envia backups para a Internet e nunca grava em particoes do tablet.
param(
    [string]$BackupDir = "C:\platform-tools\pipa_backup"
)

$ErrorActionPreference = "Stop"
$nomes = @("boot_b.img", "vendor_boot_b.img", "dtbo_b.img", "vbmeta_b.img")
if (-not (Test-Path -LiteralPath $BackupDir -PathType Container)) {
    throw "Pasta de backup nao encontrada: $BackupDir"
}

$relatorio = foreach ($nome in $nomes) {
    $caminho = Join-Path $BackupDir $nome
    if (-not (Test-Path -LiteralPath $caminho -PathType Leaf)) {
        [pscustomobject]@{
            Arquivo = $nome; Bytes = 0; Formato = "AUSENTE"
            HeaderVersion = ""; SHA256 = ""; Detalhe = "Nao examinado"
        }
        continue
    }

    $stream = [System.IO.File]::OpenRead($caminho)
    try {
        $tamanho = $stream.Length
        $header = New-Object byte[] 4096
        $lidos = $stream.Read($header, 0, $header.Length)
    }
    finally {
        $stream.Dispose()
    }

    $formato = "DESCONHECIDO"
    $versao = ""
    $detalhe = "Formato nao identificado; nao empacotar."
    if ($lidos -ge 48 -and [System.Text.Encoding]::ASCII.GetString($header, 0, 8) -eq "ANDROID!") {
        $formato = "ANDROID-BOOT"
        $v = [System.BitConverter]::ToUInt32($header, 40)
        $versao = "$v"
        $kernelBytes = [System.BitConverter]::ToUInt32($header, 8)
        if ($v -le 4) {
            if ($v -le 2) {
                $ramdiskBytes = [System.BitConverter]::ToUInt32($header, 16)
                $pageBytes = [System.BitConverter]::ToUInt32($header, 36)
                $detalhe = "kernel=$kernelBytes ramdisk=$ramdiskBytes page=$pageBytes"
            }
            else {
                $ramdiskBytes = [System.BitConverter]::ToUInt32($header, 12)
                $detalhe = "kernel=$kernelBytes ramdisk=$ramdiskBytes page=4096"
            }
        }
        else { $detalhe = "Versao de boot inesperada: revisar manualmente." }
    }
    elseif ($lidos -ge 12 -and [System.Text.Encoding]::ASCII.GetString($header, 0, 8) -eq "VNDRBOOT") {
        $formato = "VENDOR-BOOT"
        $versao = "$([System.BitConverter]::ToUInt32($header, 8))"
        $detalhe = "Header vendor boot; DTB e ramdisk exigem analise posterior."
    }
    elseif ($lidos -ge 32 -and $header[0] -eq 0xD7 -and $header[1] -eq 0xB7 -and $header[2] -eq 0xAB -and $header[3] -eq 0x1E) {
        $formato = "DTBO-TABLE"
        $detalhe = "Tabela DTBO reconhecida; overlays ainda nao inspecionados."
    }
    elseif ($lidos -ge 4 -and [System.Text.Encoding]::ASCII.GetString($header, 0, 4) -eq "AVB0") {
        $formato = "AVB-VBMETA"
        $detalhe = "Metadados AVB reconhecidos; nao alterar/assinar automaticamente."
    }

    [pscustomobject]@{
        Arquivo = $nome
        Bytes = $tamanho
        Formato = $formato
        HeaderVersion = $versao
        SHA256 = (Get-FileHash -LiteralPath $caminho -Algorithm SHA256).Hash.ToLowerInvariant()
        Detalhe = $detalhe
    }
}

$relatorio | Format-List
Write-Host ""
Write-Host "AUDITORIA EXP02 SOMENTE LEITURA. Nenhuma imagem foi alterada."
Write-Host "Nao envie os arquivos .img ao GitHub. Envie apenas esta saida textual para revisao."
