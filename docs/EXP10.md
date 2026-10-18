# EXP10 — auditoria diferencial EXP06 × EXP09

**Status: VALIDADO EM CI (SEM FLASH).** Execução [#39143754826](https://github.com/nywuer777/Pipa-Experimental-Kernel/actions/runs/39143754826), resultado **success**. Artefato `pipa-exp10-differential-1` (#12142761956), publicado em 18/10/2026.

## Proveniência e integridade

- EXP06 experimental (Clang21, `schedutil` 1500 μs): GitHub Actions #39136149722; artefato ZIP SHA256 `e32af6b61163fba4724211986823fc4ffab759956d213ef15b7fcda042241402`; `Image` SHA256 `7b3c971a6bd92e8e609e4c56fb6e33df78a7668463e9bcfc342aa1cdee9a0033`.
- EXP09 controle limpo (Clang21, `schedutil` padrão 2000 μs): GitHub Actions #39140258202; artefato ZIP SHA256 `f65ec9512217e29dd85419a78420173c81ff83017b51cdc123d4476356273fd6`; `Image` SHA256 `0f526f5d70266d4348ddddea592b9f6078e73cd4cfb56163d45b53aaf9633317`.
- Ambos usam a árvore E404 fixada em `fed88a6024cd4d46c52eda607a95d97d7371ba81`, AOSP Android Clang 21 build 14054515 e KernelSU.
- Ambos produzem `Image` ARM64 com 30349336 bytes, o mesmo tamanho do kernel `boot_b` de backup.
- DTB e DTBO byte a byte idênticos nos dois builds e aos backups reais anteriores (respectivamente SHA256 `9b92c1aa019fffdfaf3bfe36dcd84c2858c804109c100b684e08f62228881117` e `6a0e109590742ce67713d738aef1320e015e9abc6b509d5be7f6e9ed46dd4f9c`).

## Comparação forense

Dos 30349336 bytes de cada kernel, exatamente **39 bytes** diferem, em **5 páginas de 4096 bytes** e 11 sequências contíguas de alterações. A rotina não ignorou nem normalizou bytes silenciosamente: cada um foi identificado.

| Categoria da diferença | Bytes |
| --- | ---: |
| Instrução ARM64 `MOVZ w9` em `schedutil` | **2** |
| Horários registrados em duas strings de compilação | 8 |
| Nota GNU build-id | 20 |
| Campo mtime de três cabeçalhos CPIO `newc` embutidos | 9 |
| **Total** | **39** |

A diferença funcional detectada é uma única instrução ARM64 de 32 bits no offset de arquivo **538488**:

- EXP09 controle: `0x5280fa09` → `MOVZ w9, #2000`.
- EXP06 patch: `0x5280bb89` → `MOVZ w9, #1500`.

A instrução ocupa 4 bytes e **2 bytes de sua codificação diferem**. Não significa que o código tenha apenas 2 bytes de tamanho. O destino e a classe da instrução coincidem. O resultado comprova que o valor padrão `schedutil` do código compilado foi alterado de 2000 para 1500 µs.

As 8 diferenças de horário são consequência de builds independentes; a nota GNU build-id (20 bytes) acompanha a identidade do binário final e os campos CPIO `mtime` refletem horários de empacotamento. Essas regiões **não demonstram alteração de uma ramdisk de dispositivo**.

As únicas diferenças de `.config` são:
- EXP06: `CONFIG_PIPA_EXP_SUGOV=y` / EXP09: não listado.
- EXP06: `CONFIG_PIPA_EXP_SUGOV_RATE_LIMIT_US=1500` / EXP09: não listado.

O restante do Kconfig é igual. Não inferir desse resultado que ambas as compilacões são **bit-reproducible** quando executadas em datas diferentes.

## Implementação

- Código: [`tools/exp10_forensic_diff.py`](https://github.com/nywuer777/Pipa-Experimental-Kernel/blob/main/tools/exp10_forensic_diff.py).
- CI: [`.github/workflows/exp10-forensic-diff.yml`](https://github.com/nywuer777/Pipa-Experimental-Kernel/blob/main/.github/workflows/exp10-forensic-diff.yml).
- Relatório produzido pelo CI: `EXP10-differential.md`, `EXP10-differential.json` e `exp10-report-sha256.txt` no artefato `pipa-exp10-differential-1`.
- A CI rejeita qualquer alteração inesperada nos artefatos: verifica SHA256 dos ZIPs e das Images, DTB/DTBO, cabeçalho ARM64, duas diferenças do Kconfig, contagem de 39 bytes e codificação MOVZ de 2000→1500.

## Limites para aprovação de testes em hardware

- O kernel experimental **ainda não foi iniciado no tablet**. Não há prova de boot, manutenção de root, desempenho, estabilidade térmica ou FPS.
- Mudar o *default* de `schedutil` só tem efeito se esse governor/esse valor for usado no runtime; um valor em sysfs ou outro governor pode prevalecer.
- `CONFIG_KSU=y` comprova compilação com KernelSU, não que o root sobreviverá à troca.
- O backup `boot_b` é Android Boot v3; uma raw `Image` **não é** uma `boot.img`.
- Preservar os backups e validar estratégia de rollback e repack antes de testar qualquer imagem.
- **`FLASH_READY=false`**, nenhum comando de flash ou boot instalável liberado.

**Próximo ciclo sugerido: EXP11 — reconstrução com metadados reproduzíveis e auditoria de empacotamento reversível sem instalação.** Isso evitará confundir timestamps e build-id com diferenças funcionais no futuro.
