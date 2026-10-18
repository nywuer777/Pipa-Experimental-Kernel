# EXP02 — auditoria de boot e compatibilidade (SEM FLASH)

**Dispositivo:** Xiaomi Pad 6 (pipa), Snapdragon 870, crDroid 16 / Android 16.
**Base experimental:** EXP01; E404 main-bpf em `fed88a6024cd4d46c52eda607a95d97d7371ba81`.

## Evidencia inicial

- GitHub Actions da EXP01: run `39112000643`, resultado success.
- Artefato de origem: `pipa-exp01-5-build`; `Image` ARM64 compilada (30.349.328 bytes).
- SHA-256 da `Image`: `bb20a6a936ff730d89dab8ca354ccb0ea7fe427594b8b60d2e1c424873970b11`.
- Header ARM64 (offset 0x38, bytes `41 52 4d 64`) confirmado.
- `CONFIG_PIPA_EXP_SUGOV=y`, `CONFIG_PIPA_EXP_SUGOV_RATE_LIMIT_US=1500` e `CONFIG_KSU=y`.
- Build produziu `Image.gz-dtb`, mas o artefato publicado contem somente `Image` e logs; ainda nao temos DTB/DTBO separado e validado.
- **Kernel compilado nao e boot.img. Root compilado nao comprova root funcional em boot.**

## Regras de seguranca

1. EXP02 nao possui comandos `fastboot flash`, `dd`, `magiskboot repack` nem ZIP instalavel.
2. Nao enviar `boot_b.img`, `vendor_boot_b.img`, `dtbo_b.img` e `vbmeta_b.img` ao GitHub. Auditar localmente no Windows.
3. Preservar os backups de ambos os slots disponiveis; registros atuais confirmam apenas backups do slot `_b`, nao recuperacao completa.
4. Nao presumir que o `pipa-config` historico (header Linux 4.19.113) corresponde ao kernel E404 ativo 4.19.404R.
5. Antes de qualquer instalacao, inspecionar o boot header da ROM em execucao, a posicao do DTB, DTBO, modulos, AVB, root/ramdisk e procedimento concreto de recuperacao.
6. Nenhuma promessa de FPS: 2000 para 1500 microssegundos e uma hipotese experimental, nao resultado medido.

## CI

Workflow `.github/workflows/exp02-audit.yml` baixa o artefato **fixado** do run 39112000643, verifica SHA256 e header ARM64, confere Kconfig e registra no relatorio JSON tudo o que ainda nao foi examinado. A verificacao resulta em **HOST_BINARY_AUDITED_NOT_FLASHABLE**, nunca `FLASH_READY`.

Execute apenas se o artefato ainda existir; expiracao original em **2026-10-25**. Para builds futuros, atualizar deliberadamente os IDs e hashes apos revalidacao.

## Auditoria dos backups no Windows (somente leitura)

O script utiliza apenas PowerShell e .NET, sem instalar WSL, Ubuntu ou Python.

Abra PowerShell no computador que possui os backups e rode:

```powershell
Invoke-WebRequest -Uri "https://raw.githubusercontent.com/nywuer777/Pipa-Experimental-Kernel/main/tools/exp02-auditar-backups.ps1" -OutFile ".\\exp02-auditar-backups.ps1"
powershell -NoProfile -ExecutionPolicy Bypass -File ".\\exp02-auditar-backups.ps1" -BackupDir "C:\\platform-tools\\pipa_backup"
```

**Importante:** como o repositório está privado, o download via raw URL sem autenticação pode falhar. Prefira baixar pelo navegador autenticado em GitHub, abra o arquivo e execute-o localmente. Revise o script antes de executá-lo. Ele abre as imagens com `OpenRead`, examina apenas o cabeçalho e calcula SHA-256 em streaming.

Cole somente o resultado textual para analisar header version e DTB/AVB. Nao mova ou modifique os arquivos backup.

## Saida esperada da EXP02

- Relatorio JSON de auditoria da compilacao (GitHub);
- Cabecalhos e hashes dos backups locais (PowerShell);
- Decisao fundamentada sobre quais componentes podem ou nao ser reutilizados no empacotamento de uma **futura** EXP03.

Nenhum componente e considerado instalavel sem fechar essas verificacoes.
