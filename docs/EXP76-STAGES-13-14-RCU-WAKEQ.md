# EXP76 — Stages 13 e 14: RCU consolidado e ABI de wake queue

## Evidência reproduzível

- GitHub Actions: https://github.com/nywuer777/Pipa-Experimental-Kernel/actions/runs/41343130642 — **SUCCESS**.
- Artefato: https://github.com/nywuer777/Pipa-Experimental-Kernel/actions/runs/41343130642/artifacts/13097977456 (`exp76-rt-compat-AUDIT-ONLY-47`).
- Fonte E404 fixada: `kvsnr113/xiaomi_sm8250_kernel_e404@fed88a6024cd4d46c52eda607a95d97d7371ba81`.
- Port parcial de PREEMPT_RT: `patch-4.19.325-rt140`, versão não idêntica à base E404 `4.19.404R`.

## Stage 13 — RCU-bh da árvore E404 já consolidado

- `include/linux/rcutree.h.rej`, SHA-256 `f247e4e76f87d2b4a922ea9956dbd38d9e681717c1c87a92ee90b920a4f90929`, contém 2 hunks antigos.
- A E404 possui `synchronize_rcu_bh()` como inline que chama `synchronize_rcu()`, e `rcu_barrier_bh()` como inline que chama `rcu_barrier()`, ambos em `include/linux/rcupdate.h`. A função `rcu_barrier()` é declarada no `rcutree.h` da E404.
- A árvore RCU usa `rcu_segcblist`, não as duas instâncias `rcu_sched_state`/`rcu_bh_state` esperadas pelo patch mais antigo.
- O Stage 13 **não muda fonte**: arquiva o rejeito integral, confirma interfaces e retira `rcutree.h.rej` da árvore temporária.
- Resultado da CI: rejeições em **69 → 68 arquivos**.

## Stage 14 — API de wake queues de locking RT

- `include/linux/sched/wake_q.h.rej`, SHA-256 `2b090ffb89ce9d08eb6e4f17e0db78fc382f107eaec09d51d19900f7e2d0042d`, contém um hunk de interface.
- No checkout pós-aplicação parcial do RT, `kernel/sched/core.c` define `__wake_q_add(head, task, bool sleeper)` e `__wake_up_q(head, bool sleeper)`, mas o header E404 ainda declara as funções antigas diretamente.
- O Stage 14 reconcilia o cabeçalho com esses símbolos, com wrappers para `wake_q_add()`, `wake_q_add_sleeper()`, `wake_up_q()`, `wake_up_q_sleeper()`.
- Os gates inspecionam os símbolos de `kernel/sched/core.c`, o campo `wake_q_sleeper` em `task_struct` e a API `wake_up_lock_sleeper()` antes de substituir o texto.
- Resultado da CI: rejeições em **68 → 67 arquivos**.

## Exportação e limites

- O patch `partial-source/EXP76-RT-PARTIAL-SOURCE-NONFLASH.patch` exportado pela CI inclui **19 novos arquivos de fonte RT**.
- SHA-256 do patch cumulativo após Stage 14: `ea5a4afbd4f868dc512dbc84aa791146fc0ab1fead2c099e7d78352977582bbe`.
- Reaplicação por `git apply --check` sobre a E404 limpa: **PASS**.
- O port ainda possui 67 arquivos com rejeições de hunks. Em especial, `kernel/sched/core.c`, `kernel/sched/fair.c`, `kernel/softirq.c` e `kernel/rcu/tree.c` exigem reconciliação semântica.
- Nem `CONFIG_PREEMPT_RT_FULL=y`, nem build Clang21 de EXP76, nem boot/touch/network/suspend foram validados.
- EXP75 instalado permanece intocado. `KERNEL_BUILT=false`; `FLASH_READY=false`.

## Próximo passo técnico

Auditar a geração do scheduler: `kernel/sched/features.h` da E404 usa `#define SCHED_FEAT_*`, e já tem `SCHED_FEAT_TTWU_QUEUE 0`; a versão de RT-140 espera `SCHED_FEAT(...)`. É necessária adaptação por símbolos da E404 antes de portar a opção `PREEMPT_LAZY`. A contagem de hunks não substitui um build de teste.
