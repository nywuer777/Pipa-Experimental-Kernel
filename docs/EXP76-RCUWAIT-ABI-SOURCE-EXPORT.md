# EXP76 — Stage 10: reconciliação de rcuwait e exportação de fonte parcial

## Observação de API (confirmada em GitHub Actions)

- Run de diagnóstico: https://github.com/nywuer777/Pipa-Experimental-Kernel/actions/runs/41340207688
- Base original E404: `include/linux/rcuwait.h` declara `extern void rcuwait_wake_up(struct rcuwait *w)`, e `kernel/exit.c` define a mesma assinatura.
- Após `git apply --reject` do RT-140, **`kernel/exit.c` define `int rcuwait_wake_up(struct rcuwait *w)`**, mas o hunk correspondente do cabeçalho foi rejeitado. Não deixar essa interface divergente.
- O `include/linux/rcuwait.h.rej` original tem quatro hunks, com SHA-256 `ddbd68a50a46cb0aa1871629b6d50519d9ce97ceba5af83301f538f579a96742`.
- Hunk 1 (`sched/signal.h`) e hunk 2 (`task_struct __rcu *task`) já existem no cabeçalho E404. Os outros dois contêm mudanças mistas: retorno de `rcuwait_wake_up`, helper `rcuwait_active`, preparação da espera e limpeza via `finish_rcuwait`.

## Escopo do port Stage 10

O script `tools/exp76-rt-stage10-rcuwait.py` verifica:
1. SHA do `.rej` integral e estrutura de quatro hunks.
2. Presença dos includes/pointer RCU já incorporados na E404.
3. A implementação **real pós-RT** com retorno `int` e acesso RCU ao campo `task`.
4. A existência do macro `rcu_access_pointer` e do contrato E404 de espera de três parâmetros.

Só então altera a declaração do header para retorno `int` e introduz `static inline int rcuwait_active()`. Não modifica a semântica atual de `rcuwait_wait_event()`, nem introduz `finish_rcuwait` sem reconciliar a função e os consumidores. Os dois hunks restantes ficam registrados em `rcuwait.h.rej`, sem removê-los por completo.

**Status confirmado:** CI https://github.com/nywuer777/Pipa-Experimental-Kernel/actions/runs/41340512006 — **SUCCESS**.
- `rcuwait_active()` foi adicionado no checkout RT e a declaração foi ajustada para `int rcuwait_wake_up()`, conforme `kernel/exit.c` pós-RT.
- Dois hunks RCUWAIT equivalentes foram reconhecidos; **dois hunks RCUWAIT continuam pendentes**. O lifecycle de `rcuwait_wait_event` não foi alterado.
- Restam 71 arquivos `.rej`; `CONFIG_PREEMPT_RT_FULL` não foi ativado e nenhum kernel foi compilado.

## Reprodutibilidade: patch cumulativo parcial

`tools/exp76-export-partial-source.py` exporta o delta completo `EXP76-RT-PARTIAL-SOURCE-NONFLASH.patch` após todos os stages, usando a E404 pinada como base. Inclui arquivos de fonte RT novos (via `git add --intent-to-add`) e exclui `.rej` e arquivos temporários. A exportação só passa se `git apply --check` na E404 limpa validar a reaplicação. Artefato inclui SHA-256 e manifesto.

Mesmo com reapply PASS, **há 71 arquivos com rejeições funcionais**. O patch não é compilado nem adequado para boot/flash e não contém `boot.img`.

`KERNEL_BUILT=false`; `CONFIG_PREEMPT_RT_FULL_ENABLED=false`; `FLASH_READY=false`.

## Patch cumulativo de código-fonte — hash verificado

- Artefato oficial da CI: https://github.com/nywuer777/Pipa-Experimental-Kernel/actions/runs/41340512006/artifacts/13097132822
- Nome: `exp76-rt-compat-AUDIT-ONLY-34`.
- Dentro do ZIP: `partial-source/EXP76-RT-PARTIAL-SOURCE-NONFLASH.patch` com **719148 bytes** e SHA-256 `62c1070560442052b31818a8046890e5a3159cf91649b118c078726a6fe08831`.
- Inclui **19 arquivos novos de fonte RT** que seriam omitidos por uma exportação simples de `git diff` sem `git add --intent-to-add`.
- A CI conferiu `git apply --check` sobre a E404 limpa no commit `fed88a6024cd4d46c52eda607a95d97d7371ba81`: **PASS**.
- O patch é **incompleto**, com 71 arquivos rejeitados, vários hunks RT de RCU e softirq ainda por reconciliar. Não é candidato de boot, não é imagem de kernel, não é release. `FLASH_READY=false`.
