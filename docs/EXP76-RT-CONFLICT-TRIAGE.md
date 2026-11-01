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
