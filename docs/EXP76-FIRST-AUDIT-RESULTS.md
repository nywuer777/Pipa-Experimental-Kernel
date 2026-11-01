# EXP76 — relatório da primeira auditoria PREEMPT_RT e namespaces

## Evidência da CI — execução 41332474573 (PASS como auditoria)

- Execução: https://github.com/nywuer777/Pipa-Experimental-Kernel/actions/runs/41332474573
- Artefato: https://github.com/nywuer777/Pipa-Experimental-Kernel/actions/runs/41332474573/artifacts/13094200533
- Fonte E404: `fed88a6024cd4d46c52eda607a95d97d7371ba81`.
- Patch RT: `patch-4.19.325-rt140.patch.xz` (hash conferido pelo CI), **não** é da mesma versão que E404 `4.19.404R`.
- `e404.apply_check=FAIL`, `e404.reject_count=82`.
- `overlay.apply_check=FAIL`, `overlay.reject_count=82`.
- Os 82 caminhos com rejeições são **idênticos** entre a árvore E404 e a reconstrução parcial dos overlays disponíveis. Isso só indica que esses overlays não alteraram as rejeições textuais; não prova compatibilidade semântica EXP75.
- `CONFIG_PREEMPT_RT_FULL_ENABLED=false`; nenhum kernel RT foi compilado ou executado.

## Rejeições por área (82 caminhos com .rej)

| Área | Quantidade |
|---|---:|
| include/ | 20 |
| kernel/ (exceto sched, locking e rcu) | 15 |
| kernel/rcu/ | 8 |
| mm/ | 8 |
| drivers/ | 7 |
| kernel/sched/ | 6 |
| kernel/locking/ | 4 |
| arch/arm64/ | 3 |
| fs/ | 3 |
| arch/ (outras) | 2 |
| init/ | 2 |
| lib/ | 2 |
| net/ | 1 |
| scripts/ | 1 |

Pontos críticos para a primeira revisão de port: `kernel/sched/core.c`, `kernel/sched/fair.c`, `kernel/locking/rtmutex.c`, `kernel/rcu/tree.c`, `kernel/softirq.c`, `kernel/time/hrtimer.c`, `include/linux/spinlock_types.h`, `arch/arm64/include/asm/thread_info.h`. Todos requerem revisão específica; caminhos de outras arquiteturas não devem ser usados como comprovação de segurança no pipa.

## Uname: medição no EXP75 permanente

- `CONFIG_UTS_NS=y` conforme `/proc/config.gz`.
- `/proc/self/ns/uts` e `/proc/1/ns/uts` não existem nos contextos shell e root observados.
- `u:r:shell:s0`: `toybox uname -r` -> `5.10.404R`.
- `u:r:ksu:s0`: `toybox uname -r` -> `4.19.404R`.
- Root lê `/proc/sys/kernel/osrelease` -> `4.19.404R`.
- Ausência das entradas no procfs não comprova namespace UTS diferente, e a compilação de CONFIG_UTS_NS não garante exposição de `/proc/*/ns/uts` nessa árvore.
- Origem do `5.10.404R` **não identificada**. Presença do domínio SELinux `ksu` não prova que KernelSU/SUSFS fez a alteração.

## Estado e gates

`EXP76_RT_AUDIT=PASS` significa apenas que o pipeline produziu relatório íntegro. `RT_PATCH_APPLY=FAIL` significa que o port RT está bloqueado até resolver as 82 rejeições e conflitos semânticos.

`EXP75_PERMANENT=PRESERVED`, `EXP76_RT_BUILD=NOT_STARTED`, `EXP76_UNAME_FIX=NOT_APPLIED`, `FLASH_READY=false`.
