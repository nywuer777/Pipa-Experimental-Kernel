# EXP76 Stage 18 — compilação diagnóstica real, Clang 21, sem flash

## Objetivo

Investigar falhas reais de compilação nas unidades `kernel/sched/cpupri.o`, `kernel/sched/core.o` e `kernel/fork.o` a partir da árvore de código-fonte parcial EXP76 (Stage 17).

Workflow: https://github.com/nywuer777/Pipa-Experimental-Kernel/actions/workflows/exp76-stage18-clang21-diagnostic.yml

- E404 pinada: `fed88a6024cd4d46c52eda607a95d97d7371ba81`.
- RT upstream: `4.19.325-rt140`, versão distinta da E404 4.19.404R.
- Clang do EXP75: commit Android LLVM `b54cd2c8e9e0bb057aef3804d42d39c5ac4674c7`, `clang-r563880c`, Clang 21.0.0 build 14054515.
- Arquivos de fonte com rejeições `.rej` após Stage 17: **66**.
- A árvore temporária **não** contém todos os shims inline do EXP75, a configuração final do EXP75 ou sua integração exata de KernelSU. Erros de compilação podem vir dessas diferenças, além de PREEMPT_RT.

## Contrato de afinidade da E404

A estrutura `include/linux/sched.h:task_struct` contém `cpumask_t cpus_allowed` e `cpumask_t cpus_requested`; não declara `cpus_ptr` ou `cpus_mask`.

`kernel/sched/core.c:set_cpus_allowed_common()` copia `new_mask` para `&p->cpus_allowed` e atualiza `nr_cpus_allowed`. `kernel/cgroup/cpuset.c:cpuset_fork()` passa `&current->cpus_allowed` para `set_cpus_allowed_ptr()`. `kernel/fork.c:dup_task_struct()` duplica a estrutura do pai por `arch_dup_task_struct()`.

A aplicação parcial de RT-140 introduziu **32 referências a `->cpus_ptr` e nove a `->cpus_mask` em 18 arquivos**, conforme CI Stage 16. `kernel/fork.c` introduziu uma correção de ponteiro de filho para a máscara recém-introduzida pelo RT, mas esses membros não existem na E404. Simplesmente declarar novos campos sem ajustar todas as escritas e as rotinas de criação/migração produziria máscaras divergentes, com possíveis erros de afinidade.

**Nenhum port automático de afinidade foi aplicado no Stage 18.** `kernel/sched/cpupri.c.rej` permanece pendente.

## Procedimento da CI Stage 18

1. Validar ferramentas e instalar dependências Linux arm64.
2. Baixar o Clang 21 pinado por commit (o mesmo compilador do EXP75), verificando versão.
3. Reconstruir E404 + overlays de fonte e o patch RT parcial via `tools/exp76-rt-compat-audit.sh`.
4. Inicializar submódulo KernelSU na árvore de ensaio (registrar sucesso/falha).
5. Gerar `vendor/pipa_defconfig` em diretório de saída isolado, solicitar `CONFIG_PREEMPT_RT_FULL=y`, executar `olddefconfig` e conferir a configuração efetiva. Se Kconfig retirar RT, registrar bloqueio de configuração sem executar objetos.
6. Compilar **apenas** `kernel/sched/cpupri.o`, `kernel/sched/core.o` e `kernel/fork.o` com Clang21, coletando códigos de retorno e primeiras mensagens de erro.
7. Publicar `OBJECT_DIAGNOSTIC.json` e logs. **Nenhum `Image`, `vmlinux`, `boot.img` ou firmware será produzido.**

A falha de build é resultado esperado e tecnicamente útil; sucesso no workflow de diagnóstico não significa que os objetos compilaram. Verificar `status.txt`, `preempt-config.txt` e `OBJECT_DIAGNOSTIC.json` no artifact antes de declarar qualquer marco.

## Próximas ações condicionadas aos logs

- **CONFIG_GENERATION_FAILED**: corrigir dependências ausentes / Kconfig vendor.
- **RT_CONFIG_NOT_ESTABLISHED**: revisar `kernel/Kconfig.preempt` e símbolos de seleção do PREEMPT_RT na E404.
- **OBJECT_DIAGNOSTIC_CAPTURED**: classificar o primeiro erro real de headers/scheduler/affinity e preparar correção completa e isolada, com novo diagnóstico.
- **Não habilitar flash** até um build kernel completo, compatibilidade Android/KernelSU e testes reversíveis de inicialização/toque/Ethernet/suspensão.

`EXP76_RT_PORT=INCOMPLETE`; `EXP75_PERMANENT=PRESERVED`; `FLASH_READY=false`.


## Resultado real da primeira compilação (2026-11-01)

- Workflow: https://github.com/nywuer777/Pipa-Experimental-Kernel/actions/runs/41350824272 — **SUCCESS como execução de diagnóstico**, não como build do kernel.
- Artefato: https://github.com/nywuer777/Pipa-Experimental-Kernel/actions/runs/41350824272/artifacts/13100618610
- O Clang21 pinado foi validado; `CONFIG_PREEMPT_RT_FULL=y` ficou ativo na configuração efetiva.
- Os alvos `kernel/sched/cpupri.o`, `kernel/sched/core.o` e `kernel/fork.o` **falharam com exit code 2**. Os três pararam antes de compilar seus próprios objetos, na dependência `arch/arm64/kernel/asm-offsets.s`.
- As **primeiras** mensagens de C são `rcupdate.h:493` (redefinição de `rcu_assign_pointer`), `sched.h:2108/2124` (macros `task_is_traced` e `task_is_stopped_or_traced` colidindo com novas funções), `sched.h:2197/2202` (`sleeping_lock` ausente), `rwsem.h:217` (`#endif` sem `#if`) e `interrupt.h:3` (condicional não encerrado).
- `swap.h:346` também falhou, mas **não foi o primeiro erro**. O diagnóstico inicial que o destacava foi corrigido após inspeção completa do log.
- Não houve compilação de `Image`, `vmlinux` ou `boot.img` e não foi executada qualquer ação de flash.

## Stage 19 — correção delimitada em revisão

`tools/exp76-rt-stage19-header-fixes.py` aplica correções à árvore temporária após Stage 17:

- Completa o ramo RT de `rwsem.h` com `rwsem_rt.h` e definições lockdep; mantém o ramo não RT separado. O reject específico de `rwsem.h` é removido **somente** depois de conferir seu hash.
- Fecha o condicional de `interrupt.h` e declara `thread_do_softirq` / `__raise_softirq_irqoff_ksoft`, exigindo definições correspondentes no código RT pós-patch. O restante do reject de `interrupt.h` permanece sem port, especialmente `softirq_check_pending_idle`.
- Remove as macros antigas `task_is_traced` e `task_is_stopped_or_traced` que colidem com as funções RT já aplicadas, e introduz o campo `sleeping_lock`. O reject de `sched.h` com afinidade de CPU continua pendente e o ciclo de vida do campo exige auditoria.
- Retira o include duplicado de `rcu_assign_pointer.h` de `rcupdate.h`, mantendo a macro própria da E404.

A meta estrutural é reduzir **66 para 65 arquivos com rejeições**. **Esta meta não comprova compilação nem correção de semântica.** A nova CI deverá verificar se o Clang21 progride além de `asm-offsets.s` e reportar quaisquer erros subsequentes.

`EXP76_STAGE18_OBJECTS=3_FAILED`; `EXP76_STAGE19_VALIDATION=PENDING`; `KERNEL_BUILT=false`; `FLASH_READY=false`.

## Stage19 — CI confirmada em 2026-11-01

- Auditoria [41352077738](https://github.com/nywuer777/Pipa-Experimental-Kernel/actions/runs/41352077738): executou Stage19 e confirmou **65** arquivos ainda com `.rej`.
- Diagnóstico [41352077574](https://github.com/nywuer777/Pipa-Experimental-Kernel/actions/runs/41352077574): `CONFIG_PREEMPT_RT_FULL=y` e Clang 21 validados; **3/3 objetos falharam** ainda em `arch/arm64/kernel/asm-offsets.s`.
- Primeiro erro fatal: `include/linux/percpu-rwsem.h:120/130` acessa `rw_sem.owner`, que não existe no `struct rw_semaphore` definido em `rwsem_rt.h`; `RWSEM_OWNER_UNKNOWN` também não pertence ao ramo RT.
- Outro erro fatal: `include/linux/swap.h:346` chama `DECLARE_LOCAL_IRQ_LOCK(swapvec_lock)` sem importar `linux/locallock.h`.
- Aviso pendente: `rcu_assign_pointer` redefinido; o port RT troca `rbtree.h` para importar `rcu_assign_pointer.h`, mas a E404 ainda define sua própria macro em `rcupdate.h`.

## Stage20 — correção de headers delimitada, validação da CI pendente

O novo `tools/exp76-rt-stage20-headers.py`:

- Integra a única inclusão `linux/locallock.h` presente no rejeito original de `swap.h` (SHA256 `445ee7f190e53347b5d25fbbcc9e29ba37a946763323743de2b9044ec8261370`); esse rejeito específico é removido.
- Restringe as duas atualizações de `rw_sem.owner` em `percpu-rwsem.h` ao ramo `CONFIG_RWSEM_SPIN_ON_OWNER && !CONFIG_PREEMPT_RT_FULL`, preservando E404 não RT e os mapas lockdep.
- Espera **64** arquivos com rejeitos após a aplicação na árvore temporária. O exportador e os dois workflows verificam esse gate.
- Não altera `rcu_assign_pointer` sem primeiro conferir os caminhos de inclusão no novo diagnóstico; também não resolve `cpus_ptr`, `cpus_mask` nem o ciclo de vida de `sleeping_lock`.

**Estado do Stage20 após publicação:** o teste local sintético passou; build do kernel e validação da CI ainda não comprovados. É um passo para ultrapassar `asm-offsets.s`, não uma declaração de compatibilidade RT completa.

`EXP76_STAGE20_PENDING_CI=true`; `EXP75_PERMANENT=PRESERVED`; `FLASH_READY=false`.

## Stage21 — E404 RCU include reconciliation (source-only, CI pendente)

A árvore acumulada do Stage19 inclui o header novo do RT-140 \`include/linux/rcu_assign_pointer.h\`, contendo uma macro \`rcu_assign_pointer\` independente da versão da E404. O RT-140 também alterou \`include/linux/rbtree.h\` para incluir esse header, embora a E404 originalmente incluísse \`linux/rcupdate.h\`.

A correção \`tools/exp76-rt-stage21-rcu-include.py\` restaura a inclusão E404 em \`rbtree.h\`, exige uma única definição da macro E404 em \`rcupdate.h\`, verifica por SHA256 o header RT extra e preserva o arquivo novo sem depender dele a partir de \`rbtree.h\`. O script falha se o Stage20 não tiver terminado com 64 rejeições ou se o código-fonte tiver desviado da base conhecida.

Este estágio **não remove** rejeitos adicionais; o alvo continua em **64 arquivos \`.rej\`**. A eliminação do aviso Clang21 \`-Wmacro-redefined\` ainda depende de executar o novo workflow. A equivalência semântica completa de RCU, afinidade do scheduler e ciclo de vida de sleeping_lock permanecem pendentes. As únicas saídas permitidas seguem sendo auditoria e compilação de objetos — nenhum kernel bootável é produzido.

\`EXP76_STAGE21_SOURCE=COMMITTED\`; \`EXP76_STAGE21_CI=PENDING\`; \`FLASH_READY=false\`.
