# EXP76 / PREEMPT_RT — triagem técnica P0 (E404 4.19.404R)

Estado: source-port em investigação. Nenhum EXP76 compilado nem testado em dispositivo. `FLASH_READY=false`.

## Baseline e fonte upstream

- EXP75 confiável: `exp75-pie-restore-ci@9af9740d3534dbe2e87675866f114244cdd6a3e9`, boot permanente funcional no slot B.
- Fonte E404 fixada: `kvsnr113/xiaomi_sm8250_kernel_e404@fed88a6024cd4d46c52eda607a95d97d7371ba81`.
- Patch RT pinado: `4.19.325-rt140` (SHA-256 confirmado pela CI), **última série upstream 4.19-rt e EOL de 12/12/2024**. Anúncio do mantenedor: https://lkml.iu.edu/hypermail/linux/kernel/2412.1/06606.html
- E404 4.19.404R tem extensões vendor Android/Qualcomm/WALT; os patches não se aplicam diretamente. Não declarar viabilidade de runtime antes de revisar conflitos e integração de drivers.

## Evidência já coletada: relatórios github Actions

- Run de referência `41333274362`: audit PASS, `e404.apply_check=FAIL`, `overlay.apply_check=FAIL`, ambos com 82 caminhos .rej.
- Os arquivos .rej são **conflitos textuais de hunk**, não indicação automática de erro semântico ou equivalência. Aplicação parcial por `git apply --reject` também não produz uma árvore compilável garantida.
- O log detalhado mostra, por arquivo prioritário:
  - `kernel/sched/core.c`: 21 hunks rejeitados, 26 com aplicação textual.
  - `kernel/sched/fair.c`: 20 rejeitados, 11 aplicados.
  - `kernel/rcu/tree.c`: 20 rejeitados, nenhum aplicado.
  - `kernel/softirq.c`: 6 rejeitados, 11 aplicados.
  - `kernel/time/hrtimer.c`: 2 rejeitados, 11 aplicados.
  - `kernel/locking/rtmutex.c`: 1 rejeitado, 22 aplicados.
  - `arch/arm64/include/asm/thread_info.h`: 1 rejeitado, 3 aplicados.
  - `kernel/sched/Makefile`: 1 rejeitado.
- Esses números de hunks foram extraídos da saída `git apply --reject` do run e não devem ser confundidos com a contagem de 82 **arquivos**.

## Exemplo de incompatibilidade semântica: rtmutex

O hunk RT em `kernel/locking/rtmutex.c` procura `rt_mutex_handle_deadlock(ret, chwalk, lock, &waiter)`.
A árvore E404 pinada usa `rt_mutex_handle_deadlock(ret, chwalk, &waiter)`.
A diferença de assinatura indica deriva de API; **não** aplicar literalmente o hunk sem inspecionar a declaração/definição de `rt_mutex_handle_deadlock` e os chamadores. Um hunk com única rejeição pode representar risco maior que uma alteração trivial.

## Ordem de investigação para o port

1. Construir manifesto verificável de .rej com hunks completos, hashes e prioridades P0/P1; workflow `tools/exp76-rt-conflict-report.py` na branch. Isso torna o conflito revisável sem download manual do kernel.
2. Comparar `rtmutex.c`, `spinlock.c`, `spinlock_types.h`, `interrupt.h` e softirq; verificar transições spinlock/raw_spinlock, áreas IRQ/preempt e ordem de locks Qualcomm.
3. Revisar `sched/core.c`, `fair.c` e WALT vendor; reaplicar mudanças seletivas RT considerando versões de API e preempt counter da árvore.
4. Revisar RCU e interfaces de callback e CPU-idle sob RT (a ausência de qualquer hunk aceito em `rcu/tree.c` é sinal de alto desvio).
5. Revalidar arm64 Kconfig e `thread_info.h`; preservar o linker `-pie` da EXP75.
6. Só então compilar `Image` com `CONFIG_PREEMPT_RT_FULL=y` confirmado no `.config`, Clang21 pinado, drivers Novatek e RTL8153 e gating contra artifact flash.
7. Teste reversível `fastboot boot` após build, análise de dependências e plano de recuperação; só promover com evidência de boot, toque, suspend/resume, Ethernet e latência.

### Limites

O script atual de auditoria reconstrói EXP01, EXP24, EXP25A e aplica o ajuste de `uname`, mas **não** todos os shims inline de compatibilidade do workflow EXP75, sua configuração final ou KernelSU completo. As novas alterações devem permanecer em branch de desenvolvimento. `FLASH_READY=false`.


## Stage 1 comprovado — hunks localizados (2026-11-01)

Workflow: https://github.com/nywuer777/Pipa-Experimental-Kernel/actions/runs/41334455459

CI concluiu com success e confirmou:
- Manifesto anterior: 82 arquivos / 235 hunks rejeitados, mantido na íntegra como evidência.
- `arch/arm64/Kconfig`: o hunk para `select HAVE_PREEMPT_LAZY` foi aplicado à árvore temporária, hash do .rej conferido.
- `kernel/sched/Makefile`: o hunk para `swork.o` foi aplicado à árvore temporária, com `swork.c` e `swork.h` presentes.
- Remanescentes depois de portar os dois hunks: **80 arquivos com .rej**. O port permanece incompleto.
- `git diff --check` pós-stage1: PASS.
- `EXP76_UNAME_UID_SPOOF_REMOVED=PASS` na árvore temporária.
- `CONFIG_PREEMPT_RT_FULL_ENABLED=false`; `KERNEL_BUILT=false`; `FLASH_READY=false`.

Scripts: `tools/exp76-rt-conflict-report.py` e `tools/exp76-rt-stage1-port.py`. O port não foi aplicado à fonte EXP75 já instalada no tablet e não é um artefato de inicialização. Não confundir o sucesso de um job de auditoria com uma compilação do kernel.


## Stage 2 e Stage 3 — gates de fonte aprovados (2026-11-01)

- Stage 2 CI: https://github.com/nywuer777/Pipa-Experimental-Kernel/actions/runs/41334970325 (SUCCESS).
- Stage 3 CI: https://github.com/nywuer777/Pipa-Experimental-Kernel/actions/runs/41335389390 (SUCCESS).
- Stage 2: `arch/arm64/include/asm/thread_info.h` ganhou `preempt_lazy_count` após conferir `HAVE_PREEMPT_LAZY` da Stage 1, SHA-256 exato do hunk e layout vendor. Rejeições restantes: **79 arquivos**.
- Stage 3: `kernel/locking/rtmutex.c` teve o hunk de `rt_mutex_slowlock_locked` portado: `waiter` é ponteiro, `__rt_mutex_slowlock` recebe `ww_ctx`; o helper E404 `rt_mutex_handle_deadlock` permanece com três argumentos. A transformação verifica assinaturas e SHA-256 do hunk antes de alterar a árvore parcial. Rejeições restantes: **78 arquivos**.
- `git diff --check` após as alterações: PASS.
- A evidência de fonte pós-aplicação para `rtmutex` e `spinlock` está em `stage2/locking-source-excerpts.txt` no artifact do workflow.
- **Os três stages são ports de fonte isolados; não estabelecem equivalência semântica completa e não compilaram um kernel RT**.
- `CONFIG_PREEMPT_RT_FULL_ENABLED=false`; `KERNEL_BUILT=false`; `DEVICE_TESTED=false`; `FLASH_READY=false`.


## Stage 4 — guard das funções raw rwlock na árvore experimental

- CI da Stage 4: https://github.com/nywuer777/Pipa-Experimental-Kernel/actions/runs/41335919291 — **SUCCESS**.
- `kernel/locking/spinlock.c`: o hunk rejeitado `024a58992bd98d88b635d2692e3be4f32daa7529e75e48faeeb47681feed03c1` adiciona `#ifndef CONFIG_PREEMPT_RT_FULL` antes dos wrappers read/write. O fecho já vindo do patch original foi confirmado por análise de diretivas, e os condicionais ficaram balanceados.
- Rejeições restantes na árvore de ensaio: **77 arquivos** (82 originais menos os 5 arquivos portados nas stages 1–4).
- `include/linux/spinlock_types.h` segue com o hunk de substituição integral rejeitado. A E404 possui `RAW_SPIN_DEP_MAP_INIT`, `SPIN_DEP_MAP_INIT` e campos `wait_type_inner` que diferem do contexto upstream. O novo audit `tools/exp76-spinlock-type-abi-audit.py` compara esses contratos com os headers RT separados, sem modificá-los.
- **Não há `Image` RT. O sucesso desta etapa é exclusivamente de porta de fonte / estrutura.**

`EXP76_RT_STAGE4=PASS`; `EXP76_RT_REMAINING=77_FILES`; `SPINLOCK_TYPES_ABI_REVIEW=PENDING`; `FLASH_READY=false`.


## Stage 5 — spinlock type split com semântica lockdep E404

- CI de Stage 5: https://github.com/nywuer777/Pipa-Experimental-Kernel/actions/runs/41336502524 — **SUCCESS** em `source-only`.
- O reject pinado `include/linux/spinlock_types.h.rej`, SHA-256 `a15e8b5faf0abcdce61b99b1409a0359e94cf34eba098b3f22fdc34f03ff0599`, foi aplicado por transformação estritamente verificada após todas as stages anteriores.
- `spinlock_types.h`: inclui headers separados para RT e não RT; preserva `SPIN_DEP_MAP_INIT` com `LD_WAIT_CONFIG`.
- `spinlock_types_raw.h`: inicializador `RAW_SPIN_DEP_MAP_INIT` mantém `LD_WAIT_SPIN` em vez do inicializador upstream genérico.
- `spinlock_types_nort.h`: inicializador separado `___SPIN_LOCK_INITIALIZER` preserva a distinção do lockdep vendor.
- `git diff --check` e gates de conteúdo passam; **compatibilidade de compilação de structs/macros e comportamento do lockdep ainda não verificados**.
- Restam **76 arquivos com rejeições RT** na árvore do ensaio. A transformação só opera no checkout temporário da CI, não no tablet.
- `CONFIG_PREEMPT_RT_FULL_ENABLED=false`; `KERNEL_BUILT=false`; `FLASH_READY=false`.

Próximo gate: revisar dependências transversais entre `spinlock.h`, `spinlock_rt.h`, `rwlock_rt`, `mutex-rt`, `softirq` e os drivers Qualcomm, antes de qualquer compilação experimental.


## Stage 6 — equivalência de IRQ work e dependência swork (em validação)

- Rejeições de `include/linux/irq_work.h`, `kernel/time/tick-sched.c` e `include/linux/cgroup-defs.h` auditadas em artifact `exp76-rt-compat-AUDIT-ONLY-17` da CI `41336502524`.
- O E404 pinado **já define** `IRQ_WORK_HARD_IRQ BIT(3)` no header, e o `nohz_full_kick_work` usa `ATOMIC_INIT(IRQ_WORK_HARD_IRQ)`, preservando corretamente o tipo `atomic_t`. O patch RT tenta introduzir as mesmas capacidades usando contextos diferentes. Não duplicar o macro nem trocar o inicializador atômico por um inteiro.
- O único código-fonte a acrescentar no estágio 6 é `#include <linux/swork.h>` em `include/linux/cgroup-defs.h`, sujeito à confirmação de `swork.h` e `swork.c` no checkout pós-patch.
- Script `tools/exp76-rt-stage6-irq-work.py` confere os hashes SHA-256 exatos dos três arquivos `.rej`, a declaração `atomic_t`, o valor `BIT(3)`, o inicializador por CPU e os pré-requisitos swork antes de escrever. Elimina os dois rejeitos que a árvore já satisfaz, sem alterar seus arquivos.
- Meta da auditoria: reduzir 76 para **73 arquivos com rejeições**, sem compilação nem imagem de boot.
- **Status de execução:** aguarda a conclusão do workflow Stage 6; não marcar PASS com base apenas em commit ou sintaxe Python.

`FLASH_READY=false`.
