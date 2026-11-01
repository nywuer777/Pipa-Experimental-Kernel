# EXP76 — compatibilidade de geração RCU e softirq no E404

## Contexto fixado

- Kernel E404 no commit `fed88a6024cd4d46c52eda607a95d97d7371ba81`; base do EXP75 funcional no Xiaomi Pad 6 pipa.
- Patch RT auditado: `4.19.325-rt140`, versão distinta de `4.19.404R`.
- EXP75 instalado **não foi alterado**. `FLASH_READY=false`.

## Stage 8 — evidência confirmada

Workflow aprovado: https://github.com/nywuer777/Pipa-Experimental-Kernel/actions/runs/41338832473

- `kernel/rcu/tree.c.rej` original, SHA-256 `af6142fea7219367bfdcf13db46ab291558234dd3db486462371c95845012242`, contém 20 hunks.
- O primeiro hunk acrescentaria sete includes que **já existem** em `kernel/rcu/tree.c`: `delay.h`, `gfp.h`, `oom.h`, `smpboot.h`, `jiffies.h`, `sched/isolation.h`, `../time/tick-internal.h`.
- O segundo hunk relevante atribui `rdp->rcu_iw.flags = IRQ_WORK_HARD_IRQ` como escalar. Na E404 o campo `flags` é `atomic_t` e **já** recebe `atomic_set(&rdp->rcu_iw.flags, IRQ_WORK_HARD_IRQ)` após `init_irq_work`.
- Dois hunks de fonte já equivalentes foram retirados **somente** do arquivo `.rej` da árvore temporária; `kernel/rcu/tree.c` ficou intocado.
- Restam **18 hunks RCU** e **71 arquivos contendo rejeições RT**. Nenhum novo `Image` RT foi compilado.

## Diferença de geração: RCU da E404

A análise direta da E404 fixada observou:

| Contrato/identificador | E404 |
|---|---|
| `struct rcu_state rcu_state` | Presente |
| `rcu_segcblist` | Presente |
| `rcu_preempt_deferred_qs` | Presente |
| `rcu_softirq_qs` | Presente |
| `rcu_bh_state` | Ausente |
| `rcu_sched_state` | Ausente |
| `for_each_rcu_flavor` | Ausente |
| `rcu_process_callbacks` legado | Ausente |

Portanto, hunks upstream RT-140 que mudam as instâncias separadas `rcu_bh_state` e `rcu_sched_state`, ou que criam `rcuc` com base no processamento antigo de flavors, **não podem ser transplantados sem reconciliação de API e semântica**. Não interpretar rejeições por divergência arquitetural como mero problema de contexto do patch.

## Diferença de geração: softirq

Na E404 fonte original:

- `DEFINE_PER_CPU(__u32, active_softirqs)` está presente.
- `ktimer_softirqd`, `softirq_check_pending_idle` e `softirq_set_runner` da proposta RT antiga não estão presentes.
- O `task_struct` original tem `pi_blocked_on`, mas não expõe `sleeping_lock` nem `softirqs_raised`. Estes são usados por um hunk de `softirq.c`.
- Os seis hunks rejeitados de `kernel/softirq.c` incluem mudanças na execução e wake-up de softirqs, timer, contexto BH, preempção e IRQ. Portar parcialmente exige revisão conjunta com RCU e `rtmutex`.

O script `tools/exp76-rt-stage9-rcu-softirq-abi.py` coleta os contratos na **árvore após aplicação parcial do RT**; não assume que ela é idêntica ao E404 original. Este script detecta desvio de geração, registra os sinais observados e impede que um port antigo seja declarado concluído só porque o texto passou em `git apply`.

## Gates para a integração

1. Definir política RCU/softirq consistente com o RCU de geração mais nova da E404.
2. Auditar `task_struct`, `pi_blocked_on`, `softirqs_raised`, `sleeping_lock` e o lifetime dos callbacks.
3. Validar CPU hotplug, suspend/resume, IRQ threading e workqueue, sem atropelar WALT ou as extensões Qualcomm.
4. Não promover `CONFIG_PREEMPT_RT_FULL=y` até que os contratos principais estejam corretos e o build Clang 21 seja reproduzível.
5. Qualquer imagem EXP76 exige testes de boot reversíveis antes de sequer considerar gravação permanente.

`EXP76_RT_STAGE8=PASS`; `EXP76_RCU_HUNKS_PENDING=18`; `EXP76_RT_REJECTED_FILES=71`; `EXP76_STAGE9=CI_PENDING`; `FLASH_READY=false`.
