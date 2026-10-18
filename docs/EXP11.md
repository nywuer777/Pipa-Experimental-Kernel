# EXP11 — Normalização forense reproduzível e pré-auditoria de boot v3 (sem flash)

**Concluído (CI):** [Pipa EXP11 run #39144485436](https://github.com/nywuer777/Pipa-Experimental-Kernel/actions/runs/39144485436) — `success`. Artefato do relatório: `pipa-exp11-canonical-1` (#12143006322), SHA-256 do ZIP `3ca2be50cafa70bd4949bed59b44d8b71a956c97183e76211fb0a93f9a53d20e`, validade 17/11/2026.

## Escopo efetivamente realizado

Esta fase implementa uma **normalização determinística para fins de auditoria** de duas compilacões já concluídas e um **pré-check de layout de boot, somente leitura**. Não é uma demonstração de que o kernel pode ser recompilado byte a byte de modo determinístico em qualquer ambiente. Esse é um objetivo distinto, ainda não demonstrado.

### 1. Isolamento funcional revalidado

- Fontes: EXP06 (patch de `schedutil`, 1500 µs) e EXP09 (controle E404, 2000 µs).
- Ambos os artefatos ZIP, ambos os kernels `Image`, DTB e DTBO tiveram hashes verificados antes da análise.
- Kernel ARM64 de ambos os builds: **30.349.336 bytes**.
- Divergências originais: **39 bytes**.
- Diferenças em metadados de build: **37 bytes** (8 em duas strings de timestamp, 20 em GNU build-id, 9 em três cabeçalhos CPIO `newc`); a classificação é checada contra padrões estruturais, não com uma lista arbitrária de offsets.
- Após neutralizar **somente na memória** esses 37 bytes: restam **2 bytes diferentes**, ambos na codificação de uma instrução ARM64 `MOVZ w9` no offset 538488.
- A instrução expõe a constante **1500 (EXP06) vs 2000 (EXP09)**.
- Se esses últimos dois bytes forem neutralizados **somente para comparação**, ambos os buffers apresentam SHA-256 canônico comum:
  `2f87ad47c3c42e9236cece6fc1bd09ee2b72785ac8b25c9beeddae56f914f5ee`.
- Hashes intermediários após remover apenas metadados:
  - EXP06: `4caa2897c7ef654fe9d2d53abc9632882f67f50975397113d1ae4ee27e22185c`;
  - EXP09: `4e2f82ddeea8bb663e229a390f7d672012d193e77903291a7401f8d70c7a5d2d`.
- **Nenhuma Image normalizada foi gravada**. Apenas hashes e um relatório JSON foram publicados.

Ferramenta: [`tools/exp11_canonical_diff.py`](https://github.com/nywuer777/Pipa-Experimental-Kernel/blob/main/tools/exp11_canonical_diff.py).

### 2. Auditoria offline de boot v3 sem modificar imagens

Foi acrescentado [`tools/exp11_offline_boot_preflight.py`](https://github.com/nywuer777/Pipa-Experimental-Kernel/blob/main/tools/exp11_offline_boot_preflight.py). A ferramenta lê **localmente** os seguintes backups privados da partição `_b`:

- `boot_b.img` (SHA-256 `31f57cded5fa4b37426b4387b58c1c7330703a1c1a8a5aa584b348fcbb78c2f4`);
- `vendor_boot_b.img` (SHA-256 `a24ea921db6014a49f9895cc5c18efbb6c6674d697f25cde3b7a1670a643c28c`);
- `dtbo_b.img` (SHA-256 `f4168f76d092362ac438543d74938d83e3e567a37abb16e4d61fe7ba764588e2`);
- `vbmeta_b.img` (SHA-256 `86d703c2ea2f73a55aa86374329bd89ffd975c0e95e33645a156cfdc343889ff`).

Além disso, valida o ZIP **original** da EXP06 (`pipa-exp06-clang21-1.zip`; SHA-256 `e32af6b61163fba4724211986823fc4ffab759956d213ef15b7fcda042241402`) e o SHA-256 da `Image`.

Checa:

1. Boot v3 (`ANDROID!`, header 1580, alinhamento de 4096 bytes, ARM64 `ARMd`, kernel e generic ramdisk gzip);
2. Kernel do backup original, SHA-256 `a72fff8f285419f6f45c7e3d1c43fb1fe5958878b5ce53ab9291148ad9b7acdd`;
3. Generic ramdisk sem alteração (SHA-256 `d2a62b4ca809b28ddd0ae25388af051c874fbacfecb6b965243b7d6b81465ee9`);
4. Vendor_boot v3, incluindo vendor ramdisk gzip íntegra e DTB FDT íntegra;
5. DTBO table v0 com entrada(s) FDT dentro dos limites;
6. Vbmeta `AVB0` com leitura estrutural de versão/algoritmo/flags, **sem alegação de validação criptográfica AVB**;
7. `Image` experimental tem **mesmo comprimento** que o kernel de backup, portanto a posição da ramdisk **não precisaria** ser deslocada numa hipotética substituição. Nenhuma substituição ocorre.

**A auditoria completa dos backups privados reais continua PENDENTE**; o CI usa *somente fixtures sintéticas*, nunca imagens do tablet. A validação de SHA em material real deve ser feita localmente pelo usuário.

#### Execução opcional no Windows (Python 3 instalado)

Baixe `tools/exp11_offline_boot_preflight.py` e `tools/exp10_forensic_diff.py` do GitHub, mantendo **ambos na mesma pasta**, por exemplo `C:\platform-tools`. Baixe o ZIP original `pipa-exp06-clang21-1.zip` (artefato [EXP06](https://github.com/nywuer777/Pipa-Experimental-Kernel/actions/runs/39136149722/artifacts/12140930183)) para Downloads e execute:

```powershell
py -3 C:\platform-tools\exp11_offline_boot_preflight.py --backup-dir C:\platform-tools\pipa_backup --exp06-zip "$env:USERPROFILE\Downloads\pipa-exp06-clang21-1.zip" --report C:\platform-tools\exp11-preflight.json
```

A execução só lê `.img` e `.zip`; o único arquivo opcional gerado é um relatório `.json` pequeno. Se `py -3` não estiver disponível, esse passo pode ser feito mais tarde sem comprometer o resultado do CI.

#### Testes sintéticos

O script [`tests/exp11_synthetic_preflight.py`](https://github.com/nywuer777/Pipa-Experimental-Kernel/blob/main/tests/exp11_synthetic_preflight.py) verificou, no GitHub Actions, cenários válidos e rejeições para header de boot inválido, ARM64 magic incorreto, ramdisk fora de limites, DTB de vendor inválida, DTBO com offset impossível e vbmeta sem magic. A análise do ZIP rejeitou intencionalmente um artefato corrompido. Tudo com **`flash_ready=false`**.

## Portão de segurança

**`FLASH_READY=false`**: nenhuma `boot.img`, nenhuma partição escrita, nenhuma imagem normalizada, nenhuma recuperação ou rollback operacional comprovado. O tamanho do kernel e a coincidência DTB/DTBO não bastam para confirmar boot, manutenção de root KernelSU ou desempenho de jogos.

Próximo objetivo: obter o relatório local de pré-checagem do backup original e, em fase separada, planejar método reversível de empacotamento **sem instalar** e validação independente de AVB/ramdisks/rollback. Não usar `fastboot flash`, `fastboot boot` nem substituir o slot ativo nesta fase.
