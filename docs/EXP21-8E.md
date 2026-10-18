## EXP21.8E — HOMOLOGAÇÃO REAL DA AUDITORIA A/B OFFLINE (18/10/2026)

O usuário executou `--self-test` no Windows (`EXP21.8E SYNTHETIC OFFLINE STRUCTURE SELFTEST: PASS`) e a auditoria real offline das oito imagens, sem acessar o tablet ou gravar arquivos. Todos os oito `INPUT_SHA256=PASS`. Conclusão literal: `EXP21.8E A/B OFFLINE PINNED STRUCTURAL AUDIT: PASS`, `FLASH_READY=false`.

| Estrutura | Slot A | Slot B |
| --- | --- | --- |
| `boot` | v3, kernel `30414872`, ramdisk `1503497`, compacto `31928320` | v3, kernel `30349336`, ramdisk `1849345`, compacto `32206848` |
| `vendor_boot` | v3, vendor_ramdisk `20159394`, DTB `460314`, usado `20627456` | v3, vendor_ramdisk `20412235`, DTB `460314`, usado `20881408` |
| `dtbo` | v0, 1 entrada, tabela `688455` bytes, FDT size `688391` offset `64` | v0, 1 entrada, tabela `688455` bytes, FDT size `688391` offset `64` |
| `vbmeta` | AVB v1.0, `flags=3`, `alg=2`, `rollback=0`, `location=0`, `vbmeta_bytes=5184` | AVB v1.0, `flags=3`, `alg=2`, `rollback=0`, `location=0`, `vbmeta_bytes=5184` |

Ambos os VBMETA contêm 15 descritores (tags `[4,0,0,0,0,0,0,0,0,0,2,2,2,1,1]`) com 3 descritores HASH declarados. Detalhes das relações AVB:

| Slot | Descriptor HASH | `image_size` declarado | Digest declarado (SHA256, com salt de 32B) |
| --- | --- | ---: | --- |
| A | `boot` | `51240960` | `412abe70416021da640e0ac074a98ab2692827fdc9893f2da33a7c78688fb45e` |
| A | `dtbo` | `6402048` | `3cef1bea92e530404795198b3c2863fbb2e7980155fb2b8c953a6fd717da7ba2` |
| A | `vendor_boot` | `21651456` | `7c138a410bc3dba5f0f12ec681509d206dfd4616bce1c4eb60d413b95a4280d0` |
| B | `boot` | `31920128` | `1972e2761419d05d2ea16e6cce1182c56719778a96a6cad4af75414ccb59b7c9` |
| B | `dtbo` | `692224` | `0ed695518dbb2885fe0e31da603dcca1ea03d12f3021e5af5ac11da3a4c99680` |
| B | `vendor_boot` | `20697088` | `1c63f5ea5f39f7da98a7c0418deb8366acc4b98921b71f875c54134825746ea7` |

**Observações necessárias:** `dtbo FIELDS_DIFFER=[]` na saída significa **campos estruturais selecionados iguais**, não bytes idênticos: SHA256 integral A ≠ B. `vbmeta FIELDS_DIFFER=['hash_descriptors']` significa descritores diferentes, não validação de hashes frente ao conteúdo. Os `flags=3` anunciados pelos blobs top-level não autorizam inferir aceite do kernel EXP06, especialmente com `ro.boot.verifiedbootstate=green`/`locked` no Android e `fastboot getvar unlocked=yes` no bootloader. A assinatura digital de VBMeta **não foi validada**.

**Resultado:** `EXP21.8E_REAL_A_B_STRUCTURAL=PASS_REAL`, `SLOT_A_IMAGE_INVENTORY=COMPLETE_FOR_4_BOOT_PARTITIONS`. Ainda `SLOT_A_BOOTABILITY=UNPROVEN`, `BROKEN_BOOT_RECOVERY=UNTESTED`, `FLASH_READY=false`.

Próxima etapa planejada: `EXP21.8F`, computar `SHA256(salt || first(image_size) bytes)` para os seis descritores de A e B, com os oito arquivos completos primeiro validados contra hashes fixados; distinguir `MATCH`/`MISMATCH` de integridade dos arquivos, verificação de assinatura VBMeta e política real de bootloader. Referência avbtool oficial https://android.googlesource.com/platform/external/avb/+/main/avbtool.py .

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

**Local, pelo assistente:** Python compilado sintaticamente (`py_compile`), autoteste sintético `EXP21.8E SYNTHETIC OFFLINE STRUCTURE SELFTEST: PASS`, conferência do ZIP e hashes. O autoteste inclui detecção de header boot inválido e ponteiro AVB fora dos limites. **Não houve processamento das 8 imagens reais** nesta etapa: elas permanecem no Windows do usuário e não foram anexadas. **`EXP21.8E_REAL_AB_AUDIT=PASS_REAL`.**

Referências técnicas AOSP:
- https://source.android.com/docs/core/architecture/bootloader/boot-image-header
- https://source.android.com/docs/core/architecture/dto/partitions
- https://android.googlesource.com/platform/external/avb/+/refs/heads/master/libavb/avb_vbmeta_image.h
- https://android.googlesource.com/platform/external/avb/+/main/avbtool.py

## Interpretação e bloqueios

Os quatro hashes A observados na EXP21.8B são diferentes de B, e o cabeçalho `boot_a` tem tamanhos de kernel e ramdisk diferentes de `boot_b`; essas diferenças podem refletir builds diferentes. A decodificação de AVB não confere uma assinatura contra uma raiz de confiança OEM, não identifica necessariamente a versão da instalação do slot A e não valida restauração de um boot quebrado. Mesmo após `EXP21.8E=PASS` estrutural, os critérios `SLOT_A_BOOTABLE=UNPROVEN`, `RECOVERY_BROKEN_BOOT=UNTESTED`, `FLASH_READY=false` permanecem.

**Não executar** `fastboot boot`, `fastboot flash`, `set-active`, `adb root` ou alterações de KernelSU na EXP21.8E.
