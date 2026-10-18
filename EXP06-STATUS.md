# EXP06 — recuperar paridade do toolchain (SEM FLASH)

## Evidências da EXP05 (backups reais do Xiaomi Pad 6)

- Slot ativo: `_b`.
- Kernel original de `boot_b.img`: 30349336 bytes, SHA-256 `a72fff8f285419f6f45c7e3d1c43fb1fe5958878b5ce53ab9291148ad9b7acdd`.
- Kernel EXP01: 30349328 bytes, SHA-256 `bb20a6a936ff730d89dab8ca354ccb0ea7fe427594b8b60d2e1c424873970b11`.
- 29/29 blocos de 1 MiB diferem; primeiro byte diferente no offset **1**.
- E404 original: `Linux version 4.19.404R`, Android Clang/LLD **21.0.0**, Android build ID **14054515**, based on **r563880c**, produzido em **2026-08-23** (build `#14`).
- EXP01: `Linux version 4.19.404R`, Ubuntu Clang/LLD **18.1.3**, compilado em **2026-10-18** (build `#1`).
- O hash do ZIP EXP01 e ambos os hashes dos kernels foram confirmados na auditoria local. A diferença de oito bytes no final pode ser padding, porém a divergência real começa no cabeçalho ARM64 e atinge todos os blocos.
- `CONFIG_MODULES=n` na compilação EXP01 — ainda não comprovado para o E404 atualmente executado.
- Nenhuma inferência de desempenho, boot ou compatibilidade ABI decorre apenas destes hashes.

## Fonte verificada do compilador Android

O repositório oficial do AOSP `platform/prebuilts/clang/host/linux-x86` contém a pasta `clang-r563880c`; a alteração publicada em 2025-09-06 reporta **clang 21.0.0, build 14054515**. Versão fixada para investigação de ambiente:

`b54cd2c8e9e0bb057aef3804d42d39c5ac4674c7`

Link: https://android.googlesource.com/platform/prebuilts/clang/host/linux-x86/+/b54cd2c8e9e0bb057aef3804d42d39c5ac4674c7/

Isso identifica a **revisão do prebuilt** que coincide com a string compilada do E404, mas não prova que todo o restante das flags, configuração, patches e ambiente original seja o mesmo.

## GitHub Actions

`.github/workflows/exp06-aosp-clang-probe.yml` tenta clonar por sparse fetch apenas `clang-r563880c`, sob revisão fixa, e confere:

- `clang --version` contém `clang version 21.0.0` e `14054515`;
- LLVM LLD disponível;
- revisão Git da origem exata;
- tamanho do toolchain e espaço em disco do runner.

**A sondagem não compila nem instala kernel.** Só depois de aprovada faz sentido experimentar uma compilação com o mesmo toolchain, preservando EXP01 como resultado de referência.

## Próximos portões

1. Aprovação da aquisição e identificação do Android Clang21 no runner do GitHub;
2. Segunda compilação ARM64 com esse compiler, E404 fonte fixa e patch EXP01 idêntico, documentando flags e hash;
3. Se viável, compilar controle sem patch no **mesmo** ambiente para distinguir efeitos do EXP01 das diferenças de ferramenta;
4. Conferir `/proc/config.gz` (caso exista), root, módulo ABI e versão em execução;
5. Apenas depois auditar empacotamento reversível sem sobrescrever a única cópia de um slot funcional.

**Não há boot.img, AnyKernel3 instalável nem comando fastboot flash nesta fase.**

## Resultados de execução (18/10/2026)

- **Sondagem do prebuilt oficial:** GitHub Actions [#39135672153](https://github.com/nywuer777/Pipa-Experimental-Kernel/actions/runs/39135672153) **aprovado**; `Android (14054515, +pgo, +bolt, +lto, +mlgo, based on r563880c) clang version 21.0.0` reproduz o identificador do E404 original. O checkout sparse ocupou **3,7 GiB**; a compilação completa ainda não fazia parte dessa sondagem.
- **Recompilação EXP06 com compilador alinhado:** GitHub Actions [#39136149722](https://github.com/nywuer777/Pipa-Experimental-Kernel/actions/runs/39136149722), disparada com workflow `.github/workflows/exp06-clang21-build.yml`. Não afirmar sucesso nem hash até a conclusão do job.
- **Medida de segurança:** nenhuma etapa gera `boot.img` e não existem operações de gravação no dispositivo.
