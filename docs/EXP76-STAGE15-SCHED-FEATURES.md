# EXP76 — Stage 15: scheduler PREEMPT_LAZY na ABI da E404

## Evidência aprovada

- GitHub Actions: https://github.com/nywuer777/Pipa-Experimental-Kernel/actions/runs/41348415516 — **SUCCESS**.
- Artifact: https://github.com/nywuer777/Pipa-Experimental-Kernel/actions/runs/41348415516/artifacts/13100566266 (`exp76-rt-compat-AUDIT-ONLY-53`).
- Base E404: `kvsnr113/xiaomi_sm8250_kernel_e404@fed88a6024cd4d46c52eda607a95d97d7371ba81`.
- PREEMPT_RT de referência: `patch-4.19.325-rt140`, não correspondente à base E404 4.19.404R.

## Falha de interface identificada

A E404 usa `#define SCHED_FEAT_*` e `#define sched_feat(x) SCHED_FEAT_##x`. O patch upstream RT esperava `SCHED_FEAT(...)` em `kernel/sched/features.h`. Após aplicação parcial, `kernel/sched/core.c` chama `sched_feat(PREEMPT_LAZY)` dentro de `#ifdef CONFIG_PREEMPT_LAZY`, mas a E404 não definia `SCHED_FEAT_PREEMPT_LAZY`.

O reject original `kernel/sched/features.h.rej` tem 1 hunk e SHA-256 `fd7467a2ddf05a3ded4819726925c260d2ab0faae02121e6b53ed73376e3b164`. O `SCHED_FEAT(TTWU_QUEUE, true)` é **linha de contexto upstream**, não mudança inserida — diferença identificada no teste inicial e corrigida no verificador.

## Port exato

O script `tools/exp76-rt-stage15-sched-features.py`:
- preserva `#define SCHED_FEAT_TTWU_QUEUE 0` da E404, sem reativar wake queue em non-RT;
- define `SCHED_FEAT_PREEMPT_LAZY 1` quando `CONFIG_PREEMPT_LAZY=y`, e `0` em outros casos;
- exige a implementação `resched_curr_lazy()` com `sched_feat(PREEMPT_LAZY)` e o gate `CONFIG_PREEMPT_LAZY` no código pós-patch;
- exige o Kconfig `PREEMPT_LAZY` selecionado sob `HAVE_PREEMPT_LAZY && PREEMPT_RT_FULL`;
- confere SHA-256 do .rej e remove apenas `kernel/sched/features.h.rej` depois da aplicação.

`tools/exp76-stage15-feature-cc-preflight.py` compila **apenas um probe C com includes e assertions**, nas três condições:
1. non-RT → TTWU_QUEUE=0, PREEMPT_LAZY=0;
2. RT sem PREEMPT_LAZY → TTWU_QUEUE=0, PREEMPT_LAZY=0;
3. RT com PREEMPT_LAZY → TTWU_QUEUE=0, PREEMPT_LAZY=1.

Resultado: `EXP76_STAGE15_HOST_C_FEATURE_TESTS=3_PASS`. Isso valida o cabeçalho e o pré-processador; **não é compilação do kernel**.

## Fonte cumulativa

- De 67 para **66 arquivos** com hunks `.rej`.
- Exportação: `partial-source/EXP76-RT-PARTIAL-SOURCE-NONFLASH.patch` dentro do artefato do run.
- SHA-256: `42884725e5c2030bf3a561461c991a5b80785ed922a8d2102cf20fbd66ed96ff`.
- 19 arquivos novos de fonte RT incluídos.
- `git apply --check` do patch cumulativo sobre E404 limpa: **PASS**.
- Limites: ainda existem 66 arquivos com rejeições, incluindo scheduler, softirq, RCU, drivers; não há kernel RT compilado, teste de boot, latência, touch, Ethernet ou suspend.
- EXP75 permanente permanece intacto. `CONFIG_PREEMPT_RT_FULL_ENABLED=false`; `KERNEL_BUILT=false`; `FLASH_READY=false`.

## Próximo gate

Portar contratos de scheduler prioritários (por exemplo, `kernel/sched/cpupri.c`, `core.c`, `fair.c`), sincronizados com locking, softirq e RCU, e preparar o primeiro compile preflight real com Clang 21. Não interpretar sucesso de script textual como kernel apto para boot.
