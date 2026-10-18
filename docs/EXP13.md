# EXP13 — Auditoria AVB estrutural e dos índices de rollback (somente leitura)

## Estado — 18/10/2026

A EXP12 foi homologada **nos backups reais do usuário** no PowerShell Windows, com 4/4 hashes de imagens, offsets e componentes preservados: `EXP12 REAL SLOT-B OFFLINE PREFLIGHT: PASS`. A imagem EXP06 de `30349336` bytes preserva o tamanho do kernel do `boot_b` original.

**EXP13 implementada e aprovada apenas em testes sintéticos:** [GitHub Actions #39146734296](https://github.com/nywuer777/Pipa-Experimental-Kernel/actions/runs/39146734296), `success`. O auditor real será executado localmente e sua saída precisa ser revisada antes de fechar a fase. Artefato `pipa-exp13-avb-windows-1`, ID 12143448567.

## Fundamentação AOSP

Referência canônica: [`AvbVBMetaImageHeader` em libavb](https://android.googlesource.com/platform/external/avb/+/refs/heads/main/libavb/avb_vbmeta_image.h).

O cabeçalho AVB possui 256 bytes e é big-endian na serialização. Registra tamanhos de blocos de autenticação/auxiliar; offsets relativos de hash, assinatura, chave pública e descritores; `rollback_index` (offset 112, uint64); `flags` (offset 120, uint32); localização do rollback (offset 124, uint32); e `release_string`.

As flags 0x1 e 0x2 representam, respectivamente, `HASHTREE_DISABLED` e `VERIFICATION_DISABLED`. Quando a flag de verificação desativada é aplicada conforme libavb, o processo de verificação não percorre os descritores; **a presença dessa flag no backup não comprova a política real do bootloader nem libera alteração de boot.**

A verificação criptográfica de assinatura, correspondência com uma *chave confiável conhecida*, cadeia de partições verificadas e índices de rollback persistidos em hardware **não é realizada**. A documentação oficial explicitamente diferencia a integridade de cabeçalho de `avb_slot_verify()` e do controle do armazenamento rollback.

## Ferramenta implementada

- [`tools/exp13-avb-offline.ps1`](https://github.com/nywuer777/Pipa-Experimental-Kernel/blob/main/tools/exp13-avb-offline.ps1): PowerShell 5.1 e 7, read-only.
- SHA256 integral obrigatório do `vbmeta_b.img`: `86d703c2ea2f73a55aa86374329bd89ffd975c0e95e33645a156cfdc343889ff`, tamanho esperado 131072 bytes.
- Verifica magic AVB0; versão major; alinhamento de 64 bytes de auth/aux; limites de offsets e comprimentos; número e campos de descritores; flags; índice e localização rollback; release string.
- Não envia a imagem para GitHub, não altera o dispositivo, não cria ou sobrescreve arquivos de partição. Imprime apenas texto.

### No Windows

O script foi fornecido diretamente ao usuário como arquivo `exp13-avb-offline.ps1` para evitar HTTP 404 em repositório GitHub privado. Para executá-lo após salvar o arquivo em Downloads:

```powershell
Copy-Item "$env:USERPROFILE\Downloads\exp13-avb-offline.ps1" "C:\platform-tools\exp13-run.ps1" -Force

powershell -NoProfile -ExecutionPolicy Bypass -File "C:\platform-tools\exp13-run.ps1" -VbmetaPath "C:\platform-tools\pipa_backup\vbmeta_b.img"
```

Consulta complementar de estado de boot, **também somente leitura**:

```powershell
C:\platform-tools\adb.exe shell getprop ro.boot.verifiedbootstate
C:\platform-tools\adb.exe shell getprop ro.boot.flash.locked
C:\platform-tools\adb.exe shell getprop ro.boot.vbmeta.device_state
C:\platform-tools\adb.exe shell getprop ro.boot.veritymode
C:\platform-tools\adb.exe shell getprop ro.boot.slot_suffix
```

Propriedade vazia não significa estado desbloqueado; confirmar a fonte.

## CI da EXP13

Teste sintético de cabeçalho AVB e descritores em Windows PowerShell 5.1 e 7; rejeição de desc alinhamento incorreto; falha fechada em imagem ausente; publicação de script testado em artefato. Os testes **não acessaram o `vbmeta_b.img` real do usuário**.

## Critérios pendentes para ensaio em hardware

- Análise de saída real da EXP13 e props de boot/AVB;
- Estratégia comprovada e reversível de backup/recovery para o `pipa` e slot ativo `_b`;
- Comportamento real de AVB e manutenção do KernelSU quando/SE uma imagem boot experimental for gerada;
- Garantir preservação e verificação independente da ramdisk, do cmdline e do header do boot na criação posterior do pacote;
- Teste controlado em hardware, apenas após decisão explícita.

**`FLASH_READY=false`; `BOOT_IMAGE_CREATED=false`; `AVB_SIGNATURE_VERIFIED=false`.**
