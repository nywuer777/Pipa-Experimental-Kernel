# EXP21.8B — SHA-256 das quatro partições do slot A, sem mudança de slot

**Data:** 18/10/2026 | **Pré-requisito:** EXP21.8A `PASS_REAL`, com capacidades exatas de todas as quatro partições A verificadas por `su -c 'blockdev --getsize64 ...'`, `EXIT_CODE=0`, Android ativo no slot `_b`.

## Proposta e limites

Calcular SHA-256 *dos bytes reais do dispositivo de bloco* de `boot_a`, `vendor_boot_a`, `dtbo_a` e `vbmeta_a`, sem fazer dump, copiar ou escrever imagens. Este passo precisa de **autorização específica do usuário para ler aproximadamente 335.675.392 bytes (320,125 MiB)** das quatro partições sob o root KernelSU já testado; consultar capacidade com `blockdev` não é prova de que a leitura inteira será permitida pelo SELinux/driver. Evitar leituras do tipo `dd` ou conteúdo sensível da partição userdata. `sha256sum` apenas lê cada nó para calcular o resumo; nenhuma saída é gravada em arquivo.

O AOSP distingue os metadados de slot da validade real de seu conteúdo: https://source.android.com/docs/core/ota/ab . Se o slot A tiver hash diferente do B, isso **não significa por si só falha**: ele pode conter build/versão anterior. Mesmo hashes idênticos em quatro partições **não garantem** compatibilidade com as outras partições, nem prova de bootabilidade/AVB/rollback.

## Comandos para Windows PowerShell 5.1

Executar **somente se autorizado**, com Android iniciado no slot `_b` e ADB autorizado:

```powershell
$adb = "C:\platform-tools\adb.exe"

$slot = (& $adb shell getprop ro.boot.slot_suffix | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or $slot -ne "_b") {
  throw "EXP21.8B bloqueada: nao esta no slot _b (slot=$slot)."
}

$parts = @("boot_a", "vendor_boot_a", "dtbo_a", "vbmeta_a")
foreach ($part in $parts) {
  Write-Output "=== SHA256 $part ==="
  $result = (& $adb shell "su -c 'sha256sum /dev/block/by-name/$part'" | Out-String).Trim()
  $code = $LASTEXITCODE
  Write-Output $result
  Write-Output "EXIT_CODE=$code"
  if ($code -ne 0 -or $result -notmatch '^[0-9a-fA-F]{64}\s+') {
    throw "EXP21.8B interrompida: leitura/hash falhou em $part."
  }
}
```

Este script tem lista fixa de quatro partições **A**, sem abrir ou modificar o slot `_b`. O retorno `EXIT_CODE=0` e o formato de digest SHA-256 de 64 caracteres hexadecimais são critérios de passagem. Em caso de falha na leitura, parar automaticamente, não tentar contornar SELinux, reconfigurar KernelSU, instalar módulos ou mudar slot.

## Referências de conteúdo do slot B homologadas no Windows (EXP12)

| Partição B | Tamanho (bytes) | SHA-256 original |
| --- | ---: | --- |
| `boot_b` | 201326592 | `31f57cded5fa4b37426b4387b58c1c7330703a1c1a8a5aa584b348fcbb78c2f4` |
| `vendor_boot_b` | 100663296 | `a24ea921db6014a49f9895cc5c18efbb6c6674d697f25cde3b7a1670a643c28c` |
| `dtbo_b` | 33554432 | `f4168f76d092362ac438543d74938d83e3e567a37abb16e4d61fe7ba764588e2` |
| `vbmeta_b` | 131072 | `86d703c2ea2f73a55aa86374329bd89ffd975c0e95e33645a156cfdc343889ff` |

Não forçar igualdade A/B: o objetivo é inventariar hashes reais A, associando digest, nome, tamanho e slot. **Um hash recém-calculado é uma identidade de conteúdo, não um selo de integridade frente a uma referência confiável**.

## Depois do teste

Se os quatro hashes forem obtidos, homologar a leitura sob contexto KernelSU no dispositivo e preservar os valores como evidência; avaliar diferencias A/B, detectar AVB descriptors/magic/estrutura com verificadores somente leitura. Para declarar slot A confiável como alternativa, ainda serão necessários metadados e/ou hashes confiáveis do firmware correspondente, compatibilidade de `vendor`/`system` e um plano comprovado de restauração sem dependência da inicialização de A.

**Estado atual:** `EXP21.8A=PASS_REAL`, `EXP21.8B_HASH_SLOT_A=PENDING`, `SLOT_A_RECOVERY=UNPROVEN`, `FLASH_READY=false`.
