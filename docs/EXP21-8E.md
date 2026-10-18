# EXP21.8E — Comparação estrutural A/B offline e inspeção de VBMeta (pré-boot)

**Data:** 18/10/2026. **Entrada:** EXP21.8D backup binário A `PASS_REAL` (4/4; 335675392 bytes) e EXP12 backup B (4/4) homologados. `FLASH_READY=false`.

## Objetivo da ferramenta preparada

Comparar **somente arquivos Windows** do slot A (`C:\platform-tools\pipa_backup_a`) e do slot B (`C:\platform-tools\pipa_backup`), sem depender de ADB, fastboot, root ou tablet ligado.

Entrega na conversa: `PipaExperimental-EXP21-8E-offline-ab-structural.zip`.

- SHA-256 ZIP: `144352e417ca42e7735176d67b8985fbc900e99571f9fc14b822090946642b37`.
- `EXP21-8E/EXP21-8E-offline-ab-structural.py`: SHA-256 `3dfebc4309994ac061766113f6de7c961713385ddc6e461bb7ef32ecddc452b5`.
- `EXP21-8E/EXP21-8E-LEIA-ME.txt`: SHA-256 `c1edc5e1bf4fad8bfd45a5c1dd538dc5adaf86710b3feaeeaf1ff5e80728f045`.

O Python usa apenas stdlib e é **somente leitura**: verifica SHA256 e tamanho das 8 partições frente a pinos homologados, rejeita qualquer divergência, depois decodifica estruturalmente:
- `boot`: `ANDROID!`, Android Boot v3, header, tamanho do kernel/ramdisk e comprimento compacto.
- `vendor_boot`: `VNDRBOOT`, versão 3, page 4096, header size 2112, vendor ramdisk, DTB.
- `dtbo`: tabela `0xd7b7ab1e`, limites de entrada/offset, magic FDT `d00dfeed` nas árvores declaradas.
- `vbmeta`: `AVB0`, versão, blocos de autenticação/auxiliares, limites de descritores, `algorithm_type`, `flags`, `rollback_index`, `rollback_index_location`, tags, descritores de hash e seus comprimentos/digests declarados. **Isso NÃO verifica criptograficamente as assinaturas, a cadeia de confiança, os digests contra as imagens ou política de boot real.** `flags=3` em B foi registrado anteriormente, mas não presumir flags em A.

## Comandos Windows / PowerShell 5.1

```powershell
Expand-Archive `
  -LiteralPath "$env:USERPROFILE\Downloads\PipaExperimental-EXP21-8E-offline-ab-structural.zip" `
  -DestinationPath "$env:USERPROFILE\Downloads" -Force

python "$env:USERPROFILE\Downloads\EXP21-8E\EXP21-8E-offline-ab-structural.py" --self-test

python "$env:USERPROFILE\Downloads\EXP21-8E\EXP21-8E-offline-ab-structural.py" `
  --slot-a "C:\platform-tools\pipa_backup_a" `
  --slot-b "C:\platform-tools\pipa_backup"
```

## Evidência de execução

**Local, pelo assistente:** Python compilado sintaticamente (`py_compile`), autoteste sintético `EXP21.8E SYNTHETIC OFFLINE STRUCTURE SELFTEST: PASS`, conferência do ZIP e hashes. O autoteste inclui detecção de header boot inválido e ponteiro AVB fora dos limites. **Não houve processamento das 8 imagens reais** nesta etapa: elas permanecem no Windows do usuário e não foram anexadas. **`EXP21.8E_REAL_AB_AUDIT=PENDING`.**

Referências técnicas AOSP:
- https://source.android.com/docs/core/architecture/bootloader/boot-image-header
- https://source.android.com/docs/core/architecture/dto/partitions
- https://android.googlesource.com/platform/external/avb/+/refs/heads/master/libavb/avb_vbmeta_image.h
- https://android.googlesource.com/platform/external/avb/+/main/avbtool.py

## Interpretação e bloqueios

Os quatro hashes A observados na EXP21.8B são diferentes de B, e o cabeçalho `boot_a` tem tamanhos de kernel e ramdisk diferentes de `boot_b`; essas diferenças podem refletir builds diferentes. A decodificação de AVB não confere uma assinatura contra uma raiz de confiança OEM, não identifica necessariamente a versão da instalação do slot A e não valida restauração de um boot quebrado. Mesmo após `EXP21.8E=PASS` estrutural, os critérios `SLOT_A_BOOTABLE=UNPROVEN`, `RECOVERY_BROKEN_BOOT=UNTESTED`, `FLASH_READY=false` permanecem.

**Não executar** `fastboot boot`, `fastboot flash`, `set-active`, `adb root` ou alterações de KernelSU na EXP21.8E.
