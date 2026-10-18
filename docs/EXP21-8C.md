# EXP21.8C — Assinaturas e primeiros cabeçalhos do slot A (leitura somente leitura; não troca de slot)

**Data:** 18/10/2026. **Entrada homologada:** EXP21.8B `PASS_REAL` com os quatro SHA-256 medidos diretamente do slot A usando KernelSU; todos distintos dos hashes do slot B. Android ativo no slot `_b`, `FLASH_READY=false`.

## Objetivo

Ler **somente os primeiros 64 bytes de cada partição**, via `od -An -tx1 -N 64`, para identificar assinaturas esperadas e começar a comparar seus formatos de cabeçalho, sem gravar arquivos, copiar imagens completas ou alterar o slot ativo. Total máximo solicitado: **256 bytes de dados** de quatro partições (excluídas possíveis leituras internas adicionais dos dispositivos). Executar apenas sob root KernelSU que o usuário já aprovou na EXP21.7. Um resultado de magic `MATCH` **não prova bootabilidade, assinatura AVB validada, compatibilidade do firmware, conteúdo íntegro ou rollback**.

Assinaturas AOSP esperadas nos offsets zero:

| Partição A | Magic | Hex esperado |
| --- | --- | --- |
| `boot_a` | `ANDROID!` (8 bytes) | `414e44524f494421` |
| `vendor_boot_a` | `VNDRBOOT` (8 bytes) | `564e4452424f4f54` |
| `dtbo_a` | magic DT table (4 bytes) | `d7b7ab1e` |
| `vbmeta_a` | `AVB0` (4 bytes) | `41564230` |

Fontes:
- AOSP boot headers: https://source.android.com/docs/core/architecture/bootloader/boot-image-header
- AOSP DTBO header: https://source.android.com/docs/core/architecture/dto/partitions
- AOSP libavb `AVB_MAGIC`: https://android.googlesource.com/platform/external/avb/+/refs/tags/android-9.0.0_r47/libavb/avb_vbmeta_image.h
- AOSP Toybox `od -N -A -t`: https://android.googlesource.com/platform/external/toybox/+/refs/heads/main/android/linux/generated/help.h

## Windows PowerShell 5.1

```powershell
$adb = "C:\platform-tools\adb.exe"
$slot = (& $adb shell getprop ro.boot.slot_suffix | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or $slot -ne "_b") {
    throw "EXP21.8C: abortado, slot ativo inesperado: $slot"
}

$magic = [ordered]@{
    boot_a        = "414e44524f494421"
    vendor_boot_a = "564e4452424f4f54"
    dtbo_a        = "d7b7ab1e"
    vbmeta_a      = "41564230"
}

foreach ($part in $magic.Keys) {
    $out = (& $adb shell "su -c 'od -An -tx1 -N 64 /dev/block/by-name/$part'" | Out-String).Trim()
    $exit = $LASTEXITCODE
    $hex = ($out -replace '\s+', '').ToLowerInvariant()

    Write-Output "=== $part ==="
    Write-Output "EXIT_CODE=$exit"
    Write-Output "HEADER_64_HEX=$hex"

    if ($exit -ne 0 -or $hex -notmatch '^[0-9a-f]{128}$') {
        throw "EXP21.8C: leitura incompleta ou od indisponivel: $part"
    }

    if (-not $hex.StartsWith($magic[$part])) {
        throw "EXP21.8C: assinatura inesperada em $part"
    }

    Write-Output "MAGIC=MATCH"
}
```

Checar `EXIT_CODE=0`, exatamente 64 bytes hex por dispositivo e assinatura correta. Na ausência de `od` ou `su`, **parar**; não contornar SELinux ou modificar dispositivo. Este passo não tenta AVB verify nem lê descritores completos de VBMeta.

**Resultado esperado:** `EXP21.8C_HEADER_MAGIC=PASS/FAIL/PENDING`, `SLOT_A_RECOVERY=UNPROVEN`, `FLASH_READY=false`. O material de EXP21.8C servirá para determinar se cabe inspeção estrutural completa / análise de AVB offline dos dados A em uma fase posterior. Recomenda-se preservar backups legíveis dos dados A (com autorização, hashes após transferência, sem gravação ao dispositivo) antes de qualquer instalação de kernel experimental; o passo de 64 bytes não substitui backup.
