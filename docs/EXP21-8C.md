## EXP21.8C — HOMOLOGAÇÃO REAL DOS 64 BYTES EM CADA PARTIÇÃO A (18/10/2026)

O usuário executou o script em Windows PowerShell, validou previamente slot `_b`, utilizou `su -c 'od -An -tx1 -N 64 /dev/block/by-name/<nome_a>'` em quatro partições do slot A. Todas as leituras retornaram `EXIT_CODE=0` e `MAGIC=MATCH`:

| Partição A | Cabeçalho completo de 64 bytes (hex) |
| --- | --- |
| `boot_a` | `414e44524f4944211818d00109f11600a40100202c0600000000000000000000000000000000000003000000653430345f617267733d726f6d5f616f73702c64` |
| `vendor_boot_a` | `564e4452424f4f5403000000001000000080000000000001a29b3301616e64726f6964626f6f742e68617264776172653d71636f6d20616e64726f6964626f6f` |
| `dtbo_a` | `d7b7ab1e000a8147000000200000002000000001000000200000100000000000000a810700000040000000000000000000000000000000000000000000000000` |
| `vbmeta_a` | `41564230000000010000000000000000000002400000000000001100000000020000000000000000000000000000002000000000000000200000000000000200` |

## Decodificação dos campos efetivamente presentes nesses 64 bytes

Endianness: `boot` e `vendor_boot` Little Endian nos campos numéricos; `dtbo` e `vbmeta` Big Endian.

- `boot_a`: `ANDROID!`; formato `header_version=3`, `header_size=1580`; `kernel_size=30414872` bytes; `ramdisk_size=1503497` bytes; começo da cmdline `e404_args=rom_aosp,d...` (trecho incompleto, não inferir versão ou capacidade de boot). No B original, `kernel_size=30349336`, `ramdisk_size=1849345`; diferenças A−B respectivamente **+65536** e **−345848** bytes.
- `vendor_boot_a`: `VNDRBOOT`, `header_version=3`, `page_size=4096`, `vendor_ramdisk_size=20159394` bytes; no `vendor_boot_b`, `vendor_ramdisk_size=20412235` (diferença A−B = **−252841**).
- `dtbo_a`: `magic=d7b7ab1e`, `total_size=688455`, `header_size=32`, `entry_size=32`, `entry_count=1`, `entries_offset=32`, `page_size=4096`, `version=0`; primeira entrada `dt_size=688391` e `dt_offset=64`. O B original também tinha `688455` bytes de tabela/DTBO utilizados, mas seu SHA256 integral é diferente do A (EXP21.8B).
- `vbmeta_a`: `AVB0`, `required_libavb=1.0`, `authentication_data_block_size=576`, `auxiliary_data_block_size=4352`, `algorithm_type=2`; cabeçalho AVB convencional mede 256 bytes, de modo que o comprimento declarado `256+576+4352=5184` bytes cabe na partição. **Não foi lido o campo AVB flags (offset 120), nem a assinatura ou descritores**; não inferir chave aprovada/AVB/rollback válido.

Fontes AOSP:
- https://source.android.com/docs/core/architecture/bootloader/boot-image-header
- https://source.android.com/docs/core/architecture/dto/partitions
- https://android.googlesource.com/platform/external/avb/+/refs/heads/main/libavb/avb_vbmeta_image.h

**Resultado:** `EXP21.8C_HEADER_MAGIC=PASS_REAL` (quatro assinaturas), `EXP21.8C_BASIC_FIELDS=PARSED`. Esta validação detecta cabeçalhos plausíveis, mas não garante conteúdo completo, integridade criptográfica, compatibilidade com a ROM atual ou bootabilidade. **`SLOT_A_RECOVERY=UNPROVEN` e `FLASH_READY=false`.**

**Próximo gate EXP21.8D:** preservar cópias *somente leitura no dispositivo*, com gravação **exclusivamente no Windows**, verificando os SHA256 do A medidos na EXP21.8B. Sem PowerShell 5.1 `>`/pipeline para dados binários (pode recodificar os bytes), sem comandos de escrita no Android, sem mudança de slot. Teste real pendente, operação manual autorizada.

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
