# EXP09 — identidade real do kernel: causa-raiz confirmada em código-fonte

**Dispositivo:** Xiaomi Pad 6 (`pipa`), slot ativo `_b`. **Sem flash e sem modificação do tablet.**

## Descoberta A: o `uname` é deliberadamente alterado pelo E404

O código-fonte fixado na EXP06 é:
- Repositório: `kvsnr113/xiaomi_sm8250_kernel_e404`;
- Commit: `fed88a6024cd4d46c52eda607a95d97d7371ba81`;
- Fonte de evidência: [`kernel/sys.c`](https://github.com/kvsnr113/xiaomi_sm8250_kernel_e404/blob/fed88a6024cd4d46c52eda607a95d97d7371ba81/kernel/sys.c).

Na syscall `newuname`, o código copia `utsname()` e modifica **apenas a cópia `tmp.release`** antes de devolvê-la ao processo. Os ramos verificados são:

```c
if (current_uid().val == 0 &&
    (!strncmp(current->comm, "bpfloader", 9) ||
     !strncmp(current->comm, "netbpfload", 10) ||
     !strncmp(current->comm, "netd", 4))) {
    strcpy(tmp.release, "5.10.404");
} else if (cur_uid >= 1000) {
    strlcpy(tmp.release, "5.10.404R", sizeof(tmp.release));
}
```

Logo, para o `shell` usual do ADB (UID 2000) o `uname -r` retorna `5.10.404R`. `/proc/version` usa `utsname()->release` por outro caminho (arquivo [`fs/proc/version.c`](https://github.com/kvsnr113/xiaomi_sm8250_kernel_e404/blob/fed88a6024cd4d46c52eda607a95d97d7371ba81/fs/proc/version.c)); sua saída continua `4.19.404R`.

O repositório contém Makefile com `VERSION=4`, `PATCHLEVEL=19`, `SUBLEVEL=404`, `EXTRAVERSION=R`. O payload `Image` presente no backup `boot_b.img` também identifica `Linux version 4.19.404R`. **A divergência 5.10 vs 4.19 foi resolvida como apresentação condicional de `uname`; não é evidência de um núcleo Linux 5.10.**

O bloqueio de leitura do `/proc/sys/kernel/osrelease` não é necessário para essa conclusão.

## Descoberta B: a configuração exposta por `/proc/config.gz` coincide com arquivo histórico

O arquivo `pipa-running-config.gz`, extraído localmente do dispositivo em 18/10/2026, descomprime para 170075 bytes. Esses bytes são **exatamente iguais** ao arquivo `arch/arm64/configs/stock_defconfig` no mesmo commit fixado do E404, comprovado pelo Git blob SHA:

```text
7376facb778195969c2b320be5bab9dcbb40b241
```

O arquivo é um defconfig histórico e declara:
- `Linux/arm64 4.19.113 Kernel Configuration`;
- `Compiler: clang version 10.0.6 for Android NDK`;
- `CONFIG_LOCALVERSION="-perf"`, `CONFIG_MODULES=y`, etc.

Isso **não comprova** que o kernel E404 4.19.404R em execução foi compilado com esse arquivo, nem explica a mecânica exata pela qual esse conteúdo foi embutido/exposto em `/proc/config.gz`. É possível que o conteúdo seja uma cópia legada embutida ou reaproveitada. A causa específica ainda não foi demonstrada.

### Correção da leitura EXP07

As 1.587 diferenças entre `/proc/config.gz` e `.config` EXP06 são diferenças **entre o arquivo histórico exposto e a EXP06**. **Não são 1.587 incompatibilidades comprovadas com o kernel instalado.**

O kernel EXP06 foi compilado com AOSP Android Clang 21 build 14054515, com KernelSU ativado, e o DTB/DTBO gerados são byte a byte idênticos aos componentes de backup correspondentes. Essas verificações não demonstram compatibilidade de inicialização/root nem ganho em jogos.

## Próximo objetivo

Criar um build de controle **sem o patch experimental** a partir da mesma fonte e do mesmo compilador AOSP Clang21, então comparar com a `Image` da EXP06:

- Controle E404 limpo + Android Clang21 + pipa_defconfig;
- EXP06 E404 + patch schedutil + Android Clang21 + pipa_defconfig;
- Comparar tamanhos, offsets, strings de identificação e hashes DTB/DTBO;
- Preservar tanto os artefatos anteriores como o kernel atual do tablet.

O controle esclarece o efeito de nosso patch em um ambiente idêntico. Ele **não** garante que a compilação de controle seja byte a byte igual ao E404 original de agosto, porque o ambiente e as flags exatas daquela compilação não estão integralmente disponíveis.

**`FLASH_READY=false`**. Nenhuma alteração do boot, KernelSU, AVB ou partições do dispositivo deve ser feita durante esse ciclo.
