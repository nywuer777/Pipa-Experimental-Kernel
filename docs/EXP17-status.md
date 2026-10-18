## EXP17 — HOMOLOGAÇÃO EM WINDOWS REAL: PASS (18/10/2026)

O usuário executou o wrapper EXP17.1 com Python 3.12.10 usando `-FetchAosp` sobre o backup original `C:\platform-tools\pipa_backup\boot_b.img`.

```text
EXP17.1 PYTHON_RUNTIME=VALIDATED selector=py
EXP17 REAL OFFICIAL AOSP MKBOOTIMG COMPACT REPACK CHECK
BACKUP_SHA256=verified HEADER=v3 SOURCE_BLOB_SHA256=verified
ORIGINAL_COMPACT_SHA256=202aaaf67fe5c0a963965c4e29f67866b509916e0bdff15dde38ef55b3d321e7
AOSP_REBUILT_SHA256=202aaaf67fe5c0a963965c4e29f67866b509916e0bdff15dde38ef55b3d321e7
COMPACT_BYTES=32206848
FIRST_DIFFERENT_OFFSET=NONE
RESULT=MATCH
TEMPORARY_FILES_DELETED_ON_EXIT=True
NO PARTITION MODIFIED. FLASH_READY=false
```

**Conclusão:** reproduziu exatamente todos os 32.206.848 bytes compactos de um Android Boot v3 *original* com ferramenta `mkbootimg` AOSP e sua fonte fixada; nenhuma diferença nos bytes compactos e nenhum flash. A cauda da partição de 201.326.592 bytes não fez parte do repack compacto nem foi presumida vazia. A divergência AVB observada nos descritores `boot` e `vendor_boot` e o estado contraditório reportado do bootloader não foram resolvidos por esse teste. Os testes anteriores EXP12–EXP16 continuam válidos dentro de seus próprios escopos.

**Status de homologação:** execução real no Windows **APROVADA**; workflow GitHub Actions sintético da EXP17 permaneceu com `failure` antes de iniciar etapas e não deve ser apresentado como aprovado. A aprovação material é a saída do usuário.

**Gate EXP18:** se for preparado candidato EXP06 por repack, preservar de forma verificada o cabeçalho, cmdline, ramdisk e padding, conferir origem, tamanho, hashes e resultados; guardar backup original intacto e validar mecanismo de recuperação/rollback antes de qualquer instalação. Esta homologação da imagem original **não prova** que o kernel EXP06 inicia, que KernelSU ou AVB aceitam a alteração, nem autoriza flash. `FLASH_READY=false`.

## EXP17.1 — Autoteste real no Windows: PASS

Usuário confirmou Python 3.12.10 instalado, iniciador corrigido em `Downloads\EXP17\EXP17-run-windows.ps1` e saída: `EXP17.1 PYTHON_RUNTIME=VALIDATED selector=py`, `EXP17 LOCAL SYNTHETIC WRAPPER SELFTEST: PASS`, `OFFICIAL_AOSP_MKBOOTIMG_EXECUTED=False`, `NO ORIGINAL BACKUP READ`, `FLASH_READY=false`. Os erros anteriores 9009 foram resolvidos; a execução subsequente com `-FetchAosp` e `boot_b.img` foi concluída com MATCH; ver homologação acima. Não homologar o `mkbootimg` oficial apenas com esse autoteste.

# EXP17 — Estado de validação do AOSP mkbootimg (18/10/2026)

A EXP16 foi aprovada pelo usuário no Windows real, incluindo resultado MATCH de SHA-256 dos 32206848 bytes compactos originais: 202aaaf67fe5c0a963965c4e29f67866b509916e0bdff15dde38ef55b3d321e7.

O pacote local EXP17 contém wrapper Python/PowerShell para reconstrução exclusivamente da imagem compacta ORIGINAL, com ferramenta mkbootimg.py oficial AOSP baixada por Gitiles e conferida usando hashes Git blob. O script usa diretório temporário, verifica o SHA-256 original do backup e compara o arquivo reconstruído byte a byte. Arquivos temporários excluídos ao término. Nenhum kernel EXP06 incorporado; nenhum flash executado.

O autoteste sintético local do wrapper Python passou. **A reprodução com mkbootimg oficial sobre o backup real foi executada e aprovada (veja o registro de homologação acima).**

CI [#39152847156](https://github.com/nywuer777/Pipa-Experimental-Kernel/actions/runs/39152847156): failure antes da execução de etapas, sem logs de testes; não foi homologado o oficial nesse workflow.

Fonte AOSP principal: mkbootimg.py Git blob SHA1 ec2958179691a434df917cd1b6f196edaa80e31d; gki/generate_gki_certificate.py Git blob SHA1 739c61b04a9dbd95cafa5196533e3a472c31f2d9. Exigir correspondência completa antes de invocar o AOSP.

Estado FLASH_READY=false. O resultado da EXP17 não demonstra bootabilidade de kernel novo, AVB, KernelSU ou rollback.

