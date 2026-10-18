# EXP14 — Auditoria de reconstrução lógica byte-exata do boot v3 original

**Dispositivo:** Xiaomi Pad 6 `pipa`, backup da partição `boot_b.img`, slot ativo `_b`. **Sem instalação, sem alteração dos arquivos de backup e sem gerar imagem de boot nova.**

## Motivação e evidência anterior

- EXP06 produziu ARM64 `Image` 30349336 bytes (SHA256 `7b3c971a6bd92e8e609e4c56fb6e33df78a7668463e9bcfc342aa1cdee9a0033`), mas isso **não é** `boot.img`.
- EXP12 passou com 4/4 backups originais reais e confirmou `boot_b.img` Android boot header v3, kernel offset 4096 e kernel size 30349336, ramdisk genérica offset 30355456 e size 1849345.
- EXP13.2 encontrou `dtbo` AVB MATCH, `boot` AVB MISMATCH, `vendor_boot` AVB MISMATCH, sem tocar nos arquivos.
- EXP13.3 manual comparou `SHA256(vbmeta_b.img[0:5184])` e a propriedade `ro.boot.vbmeta.digest`: igualdade exata `f6a9a87fa3187d6c2d544d724c1c0e4a36a2c365dec1b2ab86f91f16178e3c9c`.
- Usuário confirma que seu bootloader está **desbloqueado**; propriedades `green/locked` divergentes não devem ser usadas como prova de bloqueio ou liberação para flash.

## Implementação

A ferramenta permanente [`tools/exp14-boot-v3-segmented-roundtrip.ps1`](https://github.com/nywuer777/Pipa-Experimental-Kernel/blob/main/tools/exp14-boot-v3-segmented-roundtrip.ps1) executa:

1. Valida hash integral fixado do backup original `boot_b.img` (`31f57cded5fa4b37426b4387b58c1c7330703a1c1a8a5aa584b348fcbb78c2f4`) e a capacidade de 201326592 bytes.
2. Lê Android Boot v3, versão 3, header size 1580, página de 4096, magic de kernel ARM64 e assinatura gzip da ramdisk.
3. Confere offset e size dos componentes internos já validados na EXP12, além do SHA256 do kernel original `a72fff8f285419f6f45c7e3d1c43fb1fe5958878b5ce53ab9291148ad9b7acdd`.
4. Recalcula hash do backup completo lendo os **cinco segmentos** na ordem exata: página do header, kernel, padding do kernel, ramdisk genérica, todo o restante da partição. O resultado precisa ser idêntico ao SHA256 do arquivo completo.
5. Registra SHA256 da cmdline (1536 bytes a partir do offset 44) sem imprimir seu conteúdo.
6. Não produz uma imagem derivada ou gravada. Também não invoca `mkbootimg`, ADB, fastboot nem comandos de alteração de arquivo.

### Layout esperado da imagem original

| Região | Offset inicial | Bytes |
| --- | ---: | ---: |
| Página do header | 0 | 4096 |
| Kernel ARM64 original | 4096 | 30349336 |
| Padding até a próxima página | 30353432 | 2024 |
| Ramdisk genérica | 30355456 | 1849345 |
| Dados posteriores (padding + restante da partição) | 32204801 | 169121791 |
| **Total** | **0** | **201326592** |

Esses valores são um **plano estrutural calculado a partir de evidência EXP12**, não uma leitura EXP14 já concluída no computador do usuário.

### Testes

- O CI [#39150026965](https://github.com/nywuer777/Pipa-Experimental-Kernel/actions/runs/39150026965) e o CI [#39150243657](https://github.com/nywuer777/Pipa-Experimental-Kernel/actions/runs/39150243657) **falharam antes de executar as etapas do job, sem logs de teste ou artefato**. Também ocorreu esse tipo de erro na EXP13.3. Não declarar aprovação do PowerShell no GitHub.
- Um **modelo Python independente executado localmente** com fixture sintética verificou segmentação de página/header, kernel, padding não-zero, ramdisk e cauda, com hash idêntico após concatenação e rejeição de corrupção. Nesse mesmo teste, a `Image` real EXP06 extraída do ZIP foi conferida com `ARMd`, comprimento e SHA256 originais. Evidência local: `EXP14-independent-check.json`.
- O arquivo privado `boot_b.img` original **não está no ambiente do assistente**; a execução real EXP14 no Windows continua pendente.
- O script também oferece `-SelfTest` para validar seu funcionamento no próprio PowerShell antes de acessar backup. A homologação local virá com `EXP14 REAL BOOT-V3 SEGMENTED ROUNDTRIP: PASS`.

## Execução no computador Windows

Faça download do script no GitHub, em sessão autenticada, ou use a versão local autônoma disponibilizada na conversa. O repositório é privado e `raw.githubusercontent.com` sem autenticação devolve 404. Para a versão permanente:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\platform-tools\exp14-run.ps1" -SelfTest
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\platform-tools\exp14-run.ps1" -BootPath "C:\platform-tools\pipa_backup\boot_b.img"
```

Com aprovação, somente o hash e offsets são mostrados. O arquivo original continua intacto.

**Limitação fundamental:** reconstrução *lógica* do digest de uma imagem original preservando os cinco segmentos **não equivale a um teste de reempacotamento independente `mkbootimg`**, de criação de uma `boot.img` flashável, de preservação de root ou de inicialização. A EXP14 não comprova a aceitação de um kernel modificado. `FLASH_READY=false`.

**Próximo portão:** homologar PowerShell em Windows real, confirmar ferramenta/versão de repack sem gravar partição e estabelecer rollback/recovery reproduzível antes de criar um candidato instalável.
