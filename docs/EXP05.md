# EXP05 — comparação binária real entre E404 e EXP01

Estado: **ferramenta implementada e testada, aguardando execução nos backups privados do tablet**.

## Fechamento da EXP04 (Xiaomi Pad 6, slot `_b`)

Os dados a seguir foram coletados pelo usuário localmente, sem modificar as partições.

- `boot_b.img` SHA256: `31f57cded5fa4b37426b4387b58c1c7330703a1c1a8a5aa584b348fcbb78c2f4`.
- Kernel original: 30349336 bytes; SHA256 `a72fff8f285419f6f45c7e3d1c43fb1fe5958878b5ce53ab9291148ad9b7acdd`.
- SHA256 dos primeiros 30349328 bytes do kernel original: `9f1e5383e0a57d29979d4c0e8fdbef195170afa88eaebb1405bd6fecd3cfe340`.
- Kernel EXP01 compilado: 30349328 bytes; SHA256 `bb20a6a936ff730d89dab8ca354ccb0ea7fe427594b8b60d2e1c424873970b11`.
- Resultado: `DIFFERENT_PREFIX` — há diferenças antes dos 8 bytes finais.
- Últimos 8 bytes do kernel original: `ffffffffffffffff`; isso pode ser preenchimento, **não identifica** as outras diferenças.
- Ramdisk genérico SHA256: `d2a62b4ca809b28ddd0ae25388af051c874fbacfecb6b965243b7d6b81465ee9`.
- Ramdisk vendor SHA256: `8e0841f5271c164654b0a43561671a7a9e2364430ee1d650c114c8f55144c8e6`.
- DTB SHA256: `9b92c1aa019fffdfaf3bfe36dcd84c2858c804109c100b684e08f62228881117`.
- Tabela DTBO SHA256: `6a0e109590742ce67713d738aef1320e015e9abc6b509d5be7f6e9ed46dd4f9c`.
- AVB: `flags=3`, assinatura **não verificada**.

## Nova descoberta da configuração EXP01

A compilação da `Image` usa `Linux version 4.19.404R`, Clang **18.1.3** do Ubuntu e KernelSU integrado.

O arquivo `exp01-work/out/.config` do artefato confirmado contém:

```text
# CONFIG_MODULES is not set
CONFIG_KSU=y
CONFIG_PIPA_EXP_SUGOV=y
CONFIG_PIPA_EXP_SUGOV_RATE_LIMIT_US=1500
```

`CONFIG_MODULES=n` na compilação EXP01 é evidência da compilação, **não prova** que o E404 atual do tablet usa esse estado. Não tratar um `pipa-config` legado como equivalente.

## Nova ferramenta: `tools/exp05-compare-kernels.ps1`

Script PowerShell 5.1/7, **somente leitura** dos backups e da `Image`. Ele:

1. Confere SHA256 do ZIP oficial de artefatos da EXP01 e da `Image`.
2. Confere SHA256 do backup `boot_b.img` e do kernel original.
3. Compara a `Image` com o payload de kernel dentro de `boot_b.img` por blocos de 1 MiB.
4. Registra número de blocos diferentes e **primeiro offset de byte diferente**, inclusive quando os tamanhos são distintos.
5. Identifica a string compilada `Linux version ...` em ambos os binários.
6. Exibe os primeiros 64 bytes do header ARM64 para comparação.
7. Não gera boot.img, não escreve nos backups e não modifica o dispositivo.

A ferramenta é testada em GitHub Actions com `Image` real da EXP01 e `boot` **sintético**. Nenhum backup privado é enviado ao CI.

## Executar no Windows

1. Baixe no navegador autenticado o `pipa-exp01-5-build` da [execução EXP01 aprovada](https://github.com/nywuer777/Pipa-Experimental-Kernel/actions/runs/39112000643), e salve o ZIP em `Downloads`. O nome esperado é `pipa-exp01-5-build.zip`; se ele estiver diferente, ajuste o argumento.
2. Baixe `tools/exp05-compare-kernels.ps1` do repositório para `C:\platform-tools\exp05-compare-kernels.ps1`. Revise seu conteúdo antes da execução.
3. Execute:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\platform-tools\exp05-compare-kernels.ps1" -BackupDir "C:\platform-tools\pipa_backup" -Exp01Zip "$env:USERPROFILE\Downloads\pipa-exp01-5-build.zip"
```

4. Envie apenas a **saída textual**. Não envie arquivos `.img` nem `boot` ao GitHub.

O arquivo do GitHub Actions expira em 25/10/2026, a menos que seja preservado antes. Hash ZIP fixo: `048c88f81c1909242eafbb1ff97e03dc1668a56b83bc8e02849bda4240a8897d`.

## Status de segurança

**EXP05 não monta boot, não grava partições, não garante compatibilidade de ABI, root, DTB/DTBO, ROM nem boot.** Comparação binária é apenas uma das evidências; `FLASH_READY=false` continua obrigatório.
