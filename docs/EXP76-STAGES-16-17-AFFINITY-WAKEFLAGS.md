# EXP76 — Stages 16–17: ABI de afinidade e flags de wakeup

## Fonte e referências

- E404 pinado: `kvsnr113/xiaomi_sm8250_kernel_e404@fed88a6024cd4d46c52eda607a95d97d7371ba81`.
- RT oficial `4.19.325-rt140`, enquanto a E404 apresenta `4.19.404R`.
- CI aprovada para Stage 16: https://github.com/nywuer777/Pipa-Experimental-Kernel/actions/runs/41349269308
- CI aprovada para Stage 17: https://github.com/nywuer777/Pipa-Experimental-Kernel/actions/runs/41349568095

## Stage 16 — bloqueio de compilação encontrado, não corrigido

Na E404 pinada, `struct task_struct` contém `cpumask_t cpus_allowed`, sem campos `cpus_ptr` ou `cpus_mask`. A aplicação parcial do patch RT introduz **32 referências a `->cpus_ptr` e 9 a `->cpus_mask` em 18 arquivos**. São referências adicionadas em trechos de código da árvore RT; algumas pertencem a arquiteturas não ARM64 e requerem seleção de configuração antes de contar como falhas de build efetivas.

Impactos relevantes para pipa/arm64 incluem `kernel/sched/core.c`, `fair.c`, `deadline.c`, `rt.c`, `cpudeadline.c`, `kernel/fork.c` e `kernel/cgroup/cpuset.c`.

O rejeito `kernel/sched/cpupri.c.rej`, SHA-256 `46229fc23a4543f28fac12bad645f582a160086cc6d5cb6056b7909c01e53052`, tenta substituir usos de `&p->cpus_allowed` por `p->cpus_ptr`, que a E404 ainda não declara. **O arquivo .rej foi preservado.** Portar somente `cpupri.c` aumentaria a inconsistência.

O script `tools/exp76-rt-stage16-affinity-abi.py` publica o inventário no artefato `stage16/stage16-affinity-abi.json` e exige que a estrutura E404 e os chamadores atuais correspondam à evidência. O gate produz `COMPILE_BLOCKER_UNTIL_AFFINITY_ABI_RECONCILED` e não finge que um kernel foi compilado.

## Stage 17 — wakeup flag sem colisão

O rejeito `kernel/sched/sched.h.rej`, SHA-256 `2e7e8006d37cb7742259dd1c798c3ebb780b8fcbbb914f0dc4e877459d04bd6f`, continha dois hunks: `rq.nr_pinned` sob RT/SMP e `WF_LOCK_SLEEPER` com valor upstream `0x08`.

Na E404 `0x08` **já é `WF_TTWU`**, e os demais flags alcançam `WF_RQ_SELECTED=0x80`. Assim, `tools/exp76-rt-stage17-wake-flags.py` verifica a tabela completa, confirma que o código pós-RT usa `WF_LOCK_SLEEPER` e insere `#define WF_LOCK_SLEEPER 0x100`, sem colisão com os flags existentes.

Somente o hunk da flag foi marcado como tratado. O hunk `rq.nr_pinned` permanece no `sched.h.rej` (1 hunk pendente). Esta alteração é **port de código-fonte**; a semântica de wakeups ainda depende de compilação e testes do scheduler completo.

## Status da CI e artefato

- Run Stage 17: https://github.com/nywuer777/Pipa-Experimental-Kernel/actions/runs/41349568095 — **SUCCESS**.
- Artefato: https://github.com/nywuer777/Pipa-Experimental-Kernel/actions/runs/41349568095/artifacts/13100806075
- `EXP76_RT_STAGE16=AFFINITY_ABI_BLOCKER_DOCUMENTED` PASS.
- `EXP76_RT_STAGE17=COLLISION_FREE_WAKE_LOCK_FLAG_PORTED` PASS.
- Exportação cumulativa de código-fonte parcial com 19 arquivos novos, `git apply --check` sobre E404 pinada limpa: **PASS**.
- SHA-256: `46d5058530c8492713f6bd97b65a912ef19a9b050446121d80becb25d2f39698`.
- Permanecem **66 arquivos com rejeições**, sendo 1 hunk em `sched.h` ainda pendente. Redução de rejeitos não é métrica suficiente de correção de kernel.
- Sem `CONFIG_PREEMPT_RT_FULL=y`, compilação completa, teste no tablet ou imagem para flash.
- EXP75 permanente preservado; `FLASH_READY=false`.

## Próximo passo técnico

**Reconciliar o ABI de afinidade do scheduler como um contrato integral**, não por substituições pontuais de `cpus_ptr`. Revisar criação de tarefas, fork, inicialização e alteração de máscara, cpusets, políticas WALT e classes sched. Depois aplicar um build diagnóstico real com Clang21 pinado para verificar erros de compilação, sem produzir uma imagem destinada a flash.
