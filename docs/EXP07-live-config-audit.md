# EXP07 — auditoria da configuração recebida do tablet (18/10/2026)

## Resultado: NÃO AUTORIZADO PARA FLASH

O usuário extraiu `/proc/config.gz` do Xiaomi Pad 6 (slot `_b`) via ADB e o arquivo foi inspecionado localmente, sem modificação das partições.

Fontes verificadas:
- `pipa-running-config.gz`: 44819 bytes; SHA-256 `44bee1fe9d70ce449675c7ce83ea8745f8a2b5b23820e62d08a0670b9733896b`.
- Artefato da EXP06 `pipa-exp06-clang21-1`, run `39136149722`: SHA-256 do ZIP `e32af6b61163fba4724211986823fc4ffab759956d213ef15b7fcda042241402`.
- EXP06 `Image`: 30349336 bytes, SHA-256 `7b3c971a6bd92e8e609e4c56fb6e33df78a7668463e9bcfc342aa1cdee9a0033`.

### ALERTA: cabeçalho histórico na configuração exposta

O `/proc/version` confirma E404 `4.19.404R` / Android Clang **21.0.0**, build **14054515**. Contudo, `/proc/config.gz` começa com:

```text
# Linux/arm64 4.19.113 Kernel Configuration
# Compiler: clang version 10.0.6 for Android NDK
CONFIG_CLANG_VERSION=100006
```

A EXP06 compilada declara `Linux/arm64 4.19.404R`, Android Clang21, `CONFIG_CLANG_VERSION=210000`.

**Não se pode comprovar que o arquivo /proc/config.gz descreve fielmente a configuração efetivamente ativa do kernel 4.19.404R.** Pode conter uma imagem de configuração antiga incorporada ao binário. A causa da discrepância segue **não identificada**; não realizar merges cegos desse arquivo para o `pipa_defconfig`.

### Diferenças quantitativas entre arquivos

| Métrica | Quantidade |
| --- | ---: |
| Flags documentadas em /proc/config.gz | 5197 |
| Flags na .config EXP06 | 4649 |
| Símbolos em comum | 4294 |
| Símbolos únicos (união) | 5552 |
| Diferenças totais | **1587** |
| Flags presentes nos dois, com valores diferentes | **329** |
| Somente em /proc/config.gz | 903 |
| Somente na EXP06 | 355 |

Símbolo não listado ≠ comprovadamente desabilitado; diffs incluem diferenças entre árvores e releases Kconfig.

### Diferenças críticas (valores dos ARQUIVOS, não estado funcional comprovado)

| Símbolo | /proc/config.gz | EXP06 |
| --- | --- | --- |
| `CONFIG_MODULES` | y | n |
| `CONFIG_MODVERSIONS` | y | não listado |
| `CONFIG_MODULE_SIG` | y | não listado |
| `CONFIG_KSU` | não listado | y |
| `CONFIG_SCHED_WALT` | y | n |
| `CONFIG_SCHED_TUNE` | y | não listado |
| `CONFIG_SCHED_CASS` | não listado | y |
| `CONFIG_FTRACE` | y | n |
| `CONFIG_ARM64_PAN` | y | n |
| `CONFIG_ARM64_SVE` | y | n |
| `CONFIG_KALLSYMS` | y | n |
| `CONFIG_AUDIT` | y | n |
| `CONFIG_EROFS_FS` | n | y |
| `CONFIG_QCOM_KGSL` | y | y |
| `CONFIG_F2FS_FS` | y | y |
| `CONFIG_EXT4_FS` | y | y |
| `CONFIG_SECURITY_SELINUX` | y | y |
| `CONFIG_CPU_FREQ_GOV_SCHEDUTIL` | y | y |
| `CONFIG_PIPA_EXP_SUGOV_RATE_LIMIT_US` | não listado | 1500 |

Os símbolos `CONFIG_IKCONFIG=y` e `CONFIG_IKCONFIG_PROC=y` aparecem nos dois arquivos, mas não explicam por si só o descompasso do conteúdo.

### Dados positivos da EXP06 preservados

- Toolchain AOSP Android Clang 21 build 14054515 igual à string do E404 original;
- `Image` tem mesmo tamanho do kernel em backup, mas hash diferente;
- DTB da EXP06 é byte a byte idêntico ao DTB do `vendor_boot_b` de backup (SHA-256 `9b92c1aa019fffdfaf3bfe36dcd84c2858c804109c100b684e08f62228881117`);
- DTBO igualmente idêntico à tabela do `dtbo_b` (SHA-256 `6a0e109590742ce67713d738aef1320e015e9abc6b509d5be7f6e9ed46dd4f9c`).

**Tamanho de kernel e igualdade DTB/DTBO não provam inicialização, root, ABI ou FPS.**

### Próximo gate: conferência do runtime (somente leitura)

```powershell
C:\platform-tools\adb.exe shell uname -a
C:\platform-tools\adb.exe shell cat /proc/modules
C:\platform-tools\adb.exe shell cat /proc/sys/kernel/modules_disabled
C:\platform-tools\adb.exe shell ls -ld /sys/module
```

Esses comandos não modificam sistema. `/proc/modules` vazio isoladamente não prova `CONFIG_MODULES=n`.

Investigar origem da configuração incorporada, confronto com configuração realmente usada na build de 23/08/2026 e símbolos relevantes antes de qualquer pacote boot instalável.

**`FLASH_READY=false`**. Nenhuma partição foi escrita, e nenhum `boot.img` instalável foi produzido.
