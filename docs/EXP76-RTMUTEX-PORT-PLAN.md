# EXP76 — reconciliação RT de `kernel/locking/rtmutex.c`

## Fonte de evidência

- E404 fixado: `kvsnr113/xiaomi_sm8250_kernel_e404@fed88a6024cd4d46c52eda607a95d97d7371ba81`.
- RT oficial: `patch-4.19.325-rt140.patch.xz` com SHA verificado pela CI, mas base diferente de 4.19.404R.
- Artefato da auditoria EXP76 `41334079554`: `overlay-hunks/critical-rejects/kernel/locking/rtmutex.c.rej`, SHA-256 `e9e65a6d2aa9213e00f05859bc93df5a1d64e7b7100c369caa7aacdf0986f3c5`.
- O arquivo apresentou **1 hunk rejeitado**, mas outros hunks do mesmo arquivo foram aplicados textualmente. A árvore parcial não deve ser tratada como compilável.

## Contrato do slowlock precisa ser revisado

No E404 original, `rt_mutex_slowlock()` usa um `struct rt_mutex_waiter waiter` local na pilha e passa `&waiter` para `task_blocks_on_rt_mutex()`, `__rt_mutex_slowlock()`, `remove_waiter()` e `rt_mutex_handle_deadlock()`.

O hunk RT rejeitado:
- Muda as chamadas para receberem `waiter` como ponteiro.
- Introduz o argumento `ww_ctx` em `__rt_mutex_slowlock`, tratamento `__mutex_lock_check_stamp()` e `ww_mutex_account_lock()`.
- Troca o tratamento de `-EDEADLK` para o contexto `ww_mutex`.
- Espera `rt_mutex_handle_deadlock(ret, chwalk, lock, waiter)`, mas o E404 original expõe `rt_mutex_handle_deadlock(ret, chwalk, struct rt_mutex_waiter *w)` — **três argumentos**, não quatro.

Conclusão: o conflito não é de indentação. É uma alteração de API e comportamento de waiters, detecção de deadlock e contextos `ww_mutex`. A implementação correta depende dos protótipos e usos **após** as demais mudanças RT parcialmente aplicadas. Copiar o hunk ou apenas ajustar `&waiter` não basta.

## Gate antes de resolver o hunk

1. Examinar o `kernel/locking/rtmutex.c` **pós-aplicação parcial** e `include/linux/rtmutex.h`, não só o E404 original.
2. Verificar assinaturas e chamadas de `rt_mutex_slowlock`, `__rt_mutex_slowlock`, `task_blocks_on_rt_mutex`, `remove_waiter`, `rt_mutex_handle_deadlock`, `ww_mutex_account_lock`.
3. Rastrear a origem/tempo de vida do waiter, `ww_ctx` e os casos `-EDEADLK`/`-EALREADY`.
4. Garantir que a mesma política de locking se aplica a `spinlock.c`, `spinlock_types.h`, `rwsem`, `softirq` e aos drivers Qualcomm.
5. Aplicar commit isolado, inspecionar `git diff --check`, compilar com Clang21 e verificar os erros reais. Nenhuma compilação RT ainda foi executada.
6. Manter EXP75 em `boot_b` e não fornecer imagem de flash a partir de uma árvore com rejeições.

O Stage 2 em `tools/exp76-rt-stage2-port.py` captura trechos do arquivo pós-patch parcial no relatório `stage2/locking-source-excerpts.txt` **sem modificar rtmutex.c**, para revisão subsequente.

`RTMUTEX_PORT=REVIEW_REQUIRED`; `CONFIG_PREEMPT_RT_FULL_ENABLED=false`; `FLASH_READY=false`.
