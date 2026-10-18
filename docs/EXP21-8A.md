# EXP21.8A — Tamanho dos dispositivos de bloco do slot A (root autorizado, somente metadados)

**Data:** 18/10/2026 | **Pré-requisitos:** EXP21.7 comprovou `uid=0(root)`, `gid=0(root)`, SELinux `u:r:ksu:s0`, `EXIT_CODE=0` pelo KernelSU. O Android continua no slot `_b`; a EXP21.6 comprovou `root:root`, modo `0600`, em oito nós de bloco do slot A/B.

## Escopo

O comando `blockdev --getsize64` abre um dispositivo de bloco **somente para consultar capacidade** (bytes), usando `BLKGETSIZE64`; não lê o conteúdo da partição, não copia dados e não solicita alterações. Isso é diferente de `blockdev --setro`, `--setrw`, `--flushbufs` e `--rereadpt`, que **não são permitidos**. Referência oficial do código Android Toybox: https://android.googlesource.com/platform/external/toybox/+/b73f894/toys/other/blockdev.c .

A execução root exige que o usuário **aceite especificamente esta consulta**. O programa KernelSU pode registrar novas autorizações; essas consultas não deveriam alterar setores do dispositivo.

## Comandos de inventário, com Android iniciado no slot B

```powershell
$adb = "C:\platform-tools\adb.exe"
& $adb shell getprop ro.boot.slot_suffix

$parts = @("boot_a","vendor_boot_a","dtbo_a","vbmeta_a")
foreach ($part in $parts) {
    Write-Output "=== $part ==="
    & $adb shell "su -c 'blockdev --getsize64 /dev/block/by-name/$part'"
    Write-Output "EXIT_CODE=$LASTEXITCODE"
}
```

**Comparação de referência dos tamanhos do slot B (backups EXP12)**

| Tipo de partição | Bytes do backup B |
| --- | ---: |
| `boot_b.img` | 201326592 |
| `vendor_boot_b.img` | 100663296 |
| `dtbo_b.img` | 33554432 |
| `vbmeta_b.img` | 131072 |

Se os tamanhos do slot A coincidirem com B, isso demonstra simetria de **capacidade física de partição**; não demonstra igualdade de conteúdo. Se qualquer consulta falhar ou retornar um tamanho diferente, interromper avanço para hashes e investigar. Não tentar `chmod`, `setenforce`, `su` alternativos ou alterações na tabela de partições.

## Próximo portão — EXP21.8B

Somente após homologação de EXP21.8A, preparar procedimento autorizado **somente leitura** de SHA-256 para as quatro partições A. A EXP21.8A **não autoriza** nem executa hashing. Os SHA-256 novos precisam ser ligados aos nomes, tamanhos e slot medidos; um digest sem referência previamente aprovada não comprova versão de ROM ou capacidade de recuperação. Também é necessário avaliar `system/vendor` e integridade AVB para aceitar A como fallback.

**Estado:** `EXP21.7_ROOT_ID=PASS_REAL`; `EXP21.8A_PARTITION_CAPACITY=PENDING`; `SLOT_A_RECOVERY=UNPROVEN`; `FLASH_READY=false`.
