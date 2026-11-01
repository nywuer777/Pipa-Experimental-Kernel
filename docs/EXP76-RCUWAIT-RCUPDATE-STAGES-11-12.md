# EXP76 — Stage 11/12: contratos de RCU e rcuwait

## Stage 11 — confirmação da CI

Workflow: https://github.com/nywuer777/Pipa-Experimental-Kernel/actions/runs/41341818389 (SUCCESS).

- O `kernel/rcu/update.c` pós-RT já contém `finish_rcuwait()` com `rcu_assign_pointer(w->task, NULL)` e `__set_current_state(TASK_RUNNING)`, e o símbolo é exportado.
- O `kernel/exit.c` pós-RT implementa `int rcuwait_wake_up(struct rcuwait *w)`.
- O Stage 11 completou `include/linux/rcuwait.h`: `prepare_to_rcuwait()`, declaração de `finish_rcuwait()`, encaminhamento de `rcuwait_wait_event` aos helpers, preservando `signal_pending_state()` e `-EINTR`.
- O `rcuwait.h.rej` foi removido da árvore de ensaio após conferir o SHA-256 de seu conteúdo e o contrato dessas funções.
- Rejeições remanescentes: **70 arquivos** após Stage 11; `git diff --check` PASS.
- O patch cumulativo, com 19 arquivos novos RT, foi reaplicado na E404 fixada (`git apply --check` PASS). Hash SHA-256: `d38f70d278329edae14fcf32c0a7756b94489c8198a3bdb5f3cfca38f2177c92`.

## Stage 12 — RCU-bh / lockdep, port em validação

- Arquivo: `include/linux/rcupdate.h`. Rejeito original de dois hunks, SHA-256 `f04f5a3c8feb733936d49bc13eda109f6a213c0867659282a455f7851914ce56`.
- A E404 já tem `static inline void call_rcu_bh(...)` chamando `call_rcu(...)`. Esse comportamento equivale à proposta RT de encaminhamento de callbacks, sem precisar duplicar a definição.
- Na árvore pós-RT, `kernel/rcu/update.c` coloca a implementação `rcu_read_lock_bh_held()` sob `#ifndef CONFIG_PREEMPT_RT_FULL`. O header de `DEBUG_LOCK_ALLOC` ainda declara função externa sem condição, gerando risco de referência faltante no modo RT.
- `tools/exp76-rt-stage12-rcupdate.py` introduz um `static inline` que encaminha para `rcu_read_lock_held()` **somente sob CONFIG_PREEMPT_RT_FULL**, preservando a declaração externa fora de RT e o helper existente sem `DEBUG_LOCK_ALLOC`.
- Meta após Stage 12: **69 arquivos** restantes com `.rej`, exportação cumulativa reproduzível, nenhum kernel compilado ou testado.
- **Status Stage 12:** https://github.com/nywuer777/Pipa-Experimental-Kernel/actions/runs/41342260781 — **SUCCESS**.
- `rcupdate.h` no checkout RT: `call_rcu_bh()` vendor preservado; `rcu_read_lock_bh_held()` inline sob `CONFIG_PREEMPT_RT_FULL`, com declaração externa preservada em modo não RT.
- 2 hunks originais do arquivo resolvidos; `rcupdate.h.rej` removido do ensaio.
- Restam **69 arquivos rejeitados** em todo o port RT parcial.
- Exportação cumulativa **PASS**: `git apply --check` na E404 pinada limpa. SHA-256 `0284b75814eb2aea53159a934aebe658a338622310215313eb67262744d17027`.
- Artifact `exp76-rt-compat-AUDIT-ONLY-40`: https://github.com/nywuer777/Pipa-Experimental-Kernel/actions/runs/41342260781/artifacts/13098385887
- `KERNEL_BUILT=false`; `CONFIG_PREEMPT_RT_FULL_ENABLED=false`; `FLASH_READY=false`.

## Gates não negociáveis

- E404 `4.19.404R` não coincide com RT `4.19.325-rt140`. Uma rejeição eliminada é apenas progresso de integração de fonte, não garantia de semântica completa.
- Revisar `softirq.c` e a árvore RCU adaptadas ao vendor antes de ativar `CONFIG_PREEMPT_RT_FULL`.
- Kernel EXP75 está instalado e intacto; `FLASH_READY=false`. Nenhuma imagem de boot/flash foi gerada pelo EXP76.
