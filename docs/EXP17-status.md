## EXP17.1 — Autoteste real no Windows: PASS

Usuário confirmou Python 3.12.10 instalado, iniciador corrigido em `Downloads\EXP17\EXP17-run-windows.ps1` e saída: `EXP17.1 PYTHON_RUNTIME=VALIDATED selector=py`, `EXP17 LOCAL SYNTHETIC WRAPPER SELFTEST: PASS`, `OFFICIAL_AOSP_MKBOOTIMG_EXECUTED=False`, `NO ORIGINAL BACKUP READ`, `FLASH_READY=false`. Os erros anteriores 9009 foram resolvidos; a execução com `-FetchAosp` e `boot_b.img` ainda está pendente. Não homologar o `mkbootimg` oficial apenas com esse autoteste.

# EXP17 — Estado de validação do AOSP mkbootimg (18/10/2026)

A EXP16 foi aprovada pelo usuário no Windows real, incluindo resultado MATCH de SHA-256 dos 32206848 bytes compactos originais: 202aaaf67fe5c0a963965c4e29f67866b509916e0bdff15dde38ef55b3d321e7.

O pacote local EXP17 contém wrapper Python/PowerShell para reconstrução exclusivamente da imagem compacta ORIGINAL, com ferramenta mkbootimg.py oficial AOSP baixada por Gitiles e conferida usando hashes Git blob. O script usa diretório temporário, verifica o SHA-256 original do backup e compara o arquivo reconstruído byte a byte. Arquivos temporários excluídos ao término. Nenhum kernel EXP06 incorporado; nenhum flash executado.

O autoteste sintético local do wrapper Python passou. **A reprodução com mkbootimg oficial sobre o backup real ainda não foi executada.**

CI [#39152847156](https://github.com/nywuer777/Pipa-Experimental-Kernel/actions/runs/39152847156): failure antes da execução de etapas, sem logs de testes; não foi homologado o oficial nesse workflow.

Fonte AOSP principal: mkbootimg.py Git blob SHA1 ec2958179691a434df917cd1b6f196edaa80e31d; gki/generate_gki_certificate.py Git blob SHA1 739c61b04a9dbd95cafa5196533e3a472c31f2d9. Exigir correspondência completa antes de invocar o AOSP.

Estado FLASH_READY=false. O resultado da EXP17 ainda não demonstra bootabilidade de kernel novo, AVB, KernelSU ou rollback.

