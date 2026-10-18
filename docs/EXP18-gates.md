## EXP18.1 — HOMOLOGAÇÃO REAL DO INVENTÁRIO (18/10/2026)

O usuário executou `EXP18-1-recovery-preflight.ps1` em Windows PowerShell, com o tablet pipa conectado via ADB. Ambas as fases concluíram com aprovação:

```text
EXP18.1 SYNTHETIC RECOVERY PREFLIGHT: PASS
NO PRIVATE FILES READ. NO DEVICE COMMANDS. FLASH_READY=false
EXP18.1 REAL WINDOWS RECOVERY INVENTORY: PASS
DEVICE connected_adb=True product=pipa slot=_b authorized_count=1
TOOLS adb_present=True fastboot_version_available=True
BACKUPS sha256_verified=4 count=4 source_slot=_b
EXP06 original_zip_sha256_verified=True
RECOVERY_INFO fastboot_mode_transport=NOT_TESTED rollback_restore=NOT_TESTED
NO REBOOT. NO IMAGE CREATED. NO PARTITION MODIFIED. FLASH_READY=false
```

**Interpretação exata:** há backups e ZIP EXP06 verificados, ADB autorizado no Android, Fastboot instalado e slot `_b`; **a conexão USB Fastboot real não foi testada**, e não existe prova de restauração/rollback. Essa aprovação é limitada ao inventário no modo Android e não autoriza gravar imagens. O usuário informou que o bootloader está desbloqueado; ainda existem propriedades do Android `green/locked` conflitantes e será importante consultar `getvar unlocked` no modo bootloader, sem tomar um sinal isolado como prova absoluta.

**Próximo gate EXP18.2:** coletar `fastboot devices -l`, `getvar product`, `getvar current-slot`, `getvar is-userspace`, `getvar unlocked` (apenas leitura), sem automatizar reboot ou operações de escrita. `FLASH_READY=false`.

## EXP18.1 — Inventário inicial real de conexão e ferramentas (18/10/2026)

O usuário confirmou no PowerShell local:

```text
fastboot version 37.0.1-15733141
Installed as C:\platform-tools\fastboot.exe
List of devices attached
[serial omitido] device product:pipa model:23043RP34G device:pipa transport_id:6
_b
```

**Conclusão efetiva:** o executável `fastboot.exe` está instalado e executa `--version`; o ADB reconhece um Xiaomi Pad 6 (pipa) autorizado; o Android reporta slot ativo `_b`. **Não foi testada comunicação fastboot com o dispositivo em modo bootloader**, nem acesso de emergência, rollback, recovery ou comportamento em caso de falha de boot.

O usuário informou expressamente que o bootloader está desbloqueado, mas o `getprop` previamente coletado reportou `locked`; essa contradição continua em aberto. Não tomar `fastboot --version` como prova de estado de desbloqueio.

Ferramenta nova: [`tools/exp18-1-recovery-preflight.ps1`](https://github.com/nywuer777/Pipa-Experimental-Kernel/blob/main/tools/exp18-1-recovery-preflight.ps1). Auditor **somente leitura**, usando ADB `devices -l`, duas propriedades `getprop`, versão local do Fastboot e `Get-FileHash` de quatro backups mais o ZIP EXP06 com referências aprovadas anteriormente. Saídas de CI/PowerShell real desse novo script ainda **pendentes**. O autoteste não lê arquivos privados nem executa ADB. Sucesso não autoriza flash: `FLASH_READY=false`.

# EXP18 — Critérios de aceitação para candidato kernel EXP06 (somente offline)

**Data:** 2026-10-18 | **Dispositivo:** Xiaomi Pad 6 (pipa) | **Slot de origem:** `_b`.

## Evidências homologadas

- **EXP12**: hashes íntegros dos quatro backups originais (`boot_b.img`, `vendor_boot_b.img`, `dtbo_b.img`, `vbmeta_b.img`).
- **EXP13**: auditoria estrutural AVB aprovada. A identidade do blob original `vbmeta_b.img[0:5184]` coincide com `ro.boot.vbmeta.digest` — `f6a9a87fa3187d6c2d544d724c1c0e4a36a2c365dec1b2ab86f91f16178e3c9c`.
- **EXP13.2**: descritores hash de `boot` e `vendor_boot` não correspondem ao material salvo; descritor hash de `dtbo` corresponde. `flags=3` top-level; não inferir automaticamente política efetivamente aplicada pela cadeia de firmware.
- **EXP14**: leitura segmentada de todo o backup original produziu SHA-256 igual ao arquivo inteiro.
- **EXP15**: troca virtual do kernel por EXP06 passou. Novo digest de partição hipotética: `c50a7b4d8447426331adbfae9296439a957069c0860a1d36d476b63aae083f00`; **nenhum arquivo foi escrito**.
- **EXP16**: serialização canônica Android Boot v3 em memória `MATCH` na imagem original compacta.
- **EXP17**: execução **real Windows** da ferramenta `mkbootimg` oficial AOSP produziu `RESULT=MATCH`, 32.206.848 bytes idênticos, SHA-256 `202aaaf67fe5c0a963965c4e29f67866b509916e0bdff15dde38ef55b3d321e7`, `FIRST_DIFFERENT_OFFSET=NONE`. O workflow sintético GitHub Actions falhou antes das etapas; **não** declarar esse CI aprovado.

## Escopo da EXP18

Avançar da verificação do *original* para o desenho de um candidato offline EXP06. Não confundir três propriedades diferentes:

1. **Integridade byte a byte:** tamanho exato de `Image`, versão do cabeçalho, kernel no offset 4096, cabeçalho+cmdline+ramdisk+padding idênticos ao original, determinismo de reconstrução da imagem compacta.
2. **Compatibilidade de inicialização:** depende de KernelSU, módulos, DTB/DTBO, ramdisk, bootloader e políticas AVB. Não foi testada nem comprovada.
3. **Recuperação:** prova operacional de caminho reversível para o slot original, acesso fastboot/bootloader, arquivos originais com SHA verificado, mídia/driver/cabo estáveis, limites de AVB e política de A/B. Ainda não foi homologada.

## Condições não negociáveis

- Não modificar backup original, `vbmeta`, `vendor_boot`, `dtbo` ou layout da partição.
- Não gerar pacote rotulado `flash ready`, nem usar `fastboot flash`/`fastboot boot` como parte da EXP18 enquanto a recuperação real não for validada.
- Usar somente insumos de hashes fixados no relatório EXP12 e EXP06; rejeitar qualquer variação, inclusive erro de caractere na string SHA-256 (regressão aprendida na EXP13.2.1).
- A área após a imagem compacta (169.119.744 bytes) **não pode ser inferida como vazia** nem descartada em reconstrução de partição inteira.
- Registrar hashes dos arquivos originais e do produto offline de maneira separada; **não** interpretar correspondência do original com o `mkbootimg` como prova de que o candidato inicializa.
- Bootloader **desbloqueado conforme o usuário**, apesar de `getprop green/locked`; investigar discrepância antes de qualquer decisão de instalação, sem substituir relato do usuário por inferência das propriedades.
- `FLASH_READY=false` até existir verificação independente do caminho de rollback.

## Próximo trabalho

1. Auditar o procedimento offline de produção de candidato e qualquer diferença em relação ao `mkbootimg` original que passou na EXP17.
2. Preparar validação de recuperação e inventário de ferramentas no PC sem comandos de escrita no Android.
3. Criar checklist formal de aceite: integridade, identidade, origem, rollback, DTB/DTBO, KernelSU, AVB e limitação técnica do bootloader.
4. Somente após esses requisitos, discutir teste isolado e reversível.

**Estado atual:** `EXP17=PASS_REAL` e `FLASH_READY=false`.
