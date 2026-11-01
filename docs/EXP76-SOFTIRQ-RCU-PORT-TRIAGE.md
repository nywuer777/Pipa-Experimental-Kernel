# EXP76 — próximas dependências do PREEMPT_RT: softirq e RCU

## Baseline da auditoria

- EXP75 instalado permanece intacto, `FLASH_READY=false`.
- Fonte E404 fixada no commit `fed88a6024cd4d46c52eda607a95d97d7371ba81`.
- Patch RT oficial para `4.19.325-rt140`, distinto da base E404 `4.19.404R`.
- O relatório EXP76 Stage 6, workflow `41336943804`, apresentou 73 arquivos com rejeições após seis estágios fonte, sem compilação RT.
- O Stage 7 de `kernel/locking/Makefile` e `percpu-rwsem.c` está sob validação. Nunca inferir `71` arquivos até a conclusão positiva da CI.
- Artefato de auditoria: https://github.com/nywuer777/Pipa-Experimental-Kernel/actions/runs/41336943804/artifacts/13095159059

## `kernel/softirq.c` — seis hunks ainda rejeitados

Rejeito `overlay-hunks/critical-rejects/kernel/softirq.c.rej` (SHA-256 `c667be6e853b3aad605f32b556d709c5996bd2c8719029687b079280cb61ca4e`):

- Hunk 1 introduz `ktimer_softirqd`, `TIMER_SOFTIRQS`, runners por CPU e estados de tasks para softirq bloqueadas em locks.
- Hunk 2 altera a lógica de `wakeup_softirqd`.
- Hunk 3 altera as verificações de execução de `ksoftirqd`.
- Hunks 4 e 5 modificam `__do_softirq()`, softirq em RT e o tratamento de preempção.
- Hunk 6 acrescenta integração em `irq_enter()`.

Portar isoladamente um desses trechos sem estados de tasks, `pi_blocked_on`, temporizadores e integração com `rtmutex` pode produzir deadlocks ou regressões de latência. Antes de aplicar: comparar `struct task_struct` (incluindo `sleeping_lock` e `softirqs_raised`), `irq_stat`, `__do_softirq`, `irq_exit` e `local_bh_disable/enable` na árvore pós-patch.

## `kernel/rcu/tree.c` — vinte hunks ainda rejeitados

O rejeito no artifact contém 20 hunks. Áreas: quiescent states, GP sequence, `rcutorture`, `rcu_implicit_dynticks_qs`, `__rcu_process_callbacks`, `invoke_rcu_callbacks`, `call_rcu_sched`/`call_rcu_bh`, synchronize/barrier, online/offline CPU e `rcu_init`.

Os hunks de `invoke_rcu_callbacks` são materialmente diferentes de pequenas mudanças de sintaxe; envolvem execução de callbacks e política de prioridade/latência. RCU e softirq devem passar por revisão conjunta da política de execução em contexto RT, incluindo CPU hotplug/suspend.

## Etapa seguinte depois do Stage 7

1. Resolver `kernel/locking/Makefile` e o rejeito de `percpu-rwsem.c` somente após validação dos objetos `mutex-rt.o`, `rwsem-rt.o`, `rwlock-rt.o` e do `rcuwait_wait_event` de três argumentos.
2. Capturar snapshots de `task_struct`, `softirq.c` e RCU pós-aplicação parcial para auditoria de dependências, sem modificar softirq/RCU por tentativa.
3. Selecionar hunks coesos por contrato de API, não por contagem de arquivos.
4. Não habilitar `CONFIG_PREEMPT_RT_FULL` nem criar imagem até revisão dos rejeitos críticos e validação de compilação Clang 21.

`EXP76_RT_SOFTIRQ_RCU=REVIEW_REQUIRED`; `KERNEL_BUILT=false`; `FLASH_READY=false`.
