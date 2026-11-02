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

A árvore acumulada do Stage19 inclui o header novo do RT-140 `include/linux/rcu_assign_pointer.h`, contendo uma macro `rcu_assign_pointer` independente da versão da E404. O RT-140 também alterou `include/linux/rbtree.h` para incluir esse header, embora a E404 originalmente incluísse `linux/rcupdate.h`.

A correção `tools/exp76-rt-stage21-rcu-include.py` restaura a inclusão E404 em `rbtree.h`, exige uma única definição da macro E404 em `rcupdate.h`, verifica por SHA256 o header RT extra e preserva o arquivo novo sem depender dele a partir de `rbtree.h`. O script falha se o Stage20 não tiver terminado com 64 rejeições ou se o código-fonte tiver desviado da base conhecida.

Este estágio **não remove** rejeitos adicionais; o alvo continua em **64 arquivos `.rej`**. A eliminação do aviso Clang21 `-Wmacro-redefined` ainda depende de executar o novo workflow. A equivalência semântica completa de RCU, afinidade do scheduler e ciclo de vida de sleeping_lock permanecem pendentes. As únicas saídas permitidas seguem sendo auditoria e compilação de objetos — nenhum kernel bootável é produzido.

`EXP76_STAGE21_SOURCE=COMMITTED`; `EXP76_STAGE21_CI=PENDING`; `FLASH_READY=false`.

## Stage22 — gate de preparação ARM64 antes dos objetos

**Situação de CI:** não foi possível extrair o resultado do Stage21 por um run ID de GitHub Actions confirmado. O conector de execuções por SHA retorna apenas workflows originados de PR, não os runs de push deste branch. Nenhum erro de Clang posterior ao Stage20 é declarado como confirmado neste estágio.

O script `tools/exp76-stage18-clang21-object-diagnostic.sh` agora executa `make prepare` em arm64 com Clang 21 pinado, registrando `prepare.rc`, `prepare.log`, `prepare.errors.txt` e `prepare-status.txt`:

- Quando `prepare` falha, os três objetos **não são compilados**, cada objeto registra `attempted=false`, `exit_code=null` e `skip_reason=BLOCKED_BY_PREPARE` em `OBJECT_DIAGNOSTIC.json`.
- Quando `prepare` passa, a CI compila separadamente `cpupri.o`, `core.o` e `fork.o` e registra os códigos individuais.
- O teste de regressão `tests/test_exp76_stage22_prepare_parser.py` cobre três cenários: preparação falha, compilação parcialmente falha e três objetos completos. As verificações da CI incluem esses testes antes de construir a árvore de ensaio.
- O artefato diagnóstico passa a incluir os relatórios dos Stages 19, 20 e 21 para permitir verificar que as mudanças de cabeçalho foram efetivamente aplicadas.

`make prepare` é apenas um pré-requisito de compilação, não um kernel. Não há `Image`, `vmlinux` ou `boot.img`, e não ocorre escrita no dispositivo.

`EXP76_STAGE22_SOURCE=COMMITTED`; `EXP76_STAGE22_CI=UNVERIFIED`; `EXP76_RT_TARGET_REJECTS=64`; `FLASH_READY=false`.

## Stage23 — gate para arquivos gerados pelo Kbuild ARM64

O `Kbuild` fixado da E404 indica que `make prepare` gera `include/generated/asm-offsets.h`, `include/generated/bounds.h` e `include/generated/timeconst.h`. O Stage22 capturava somente o código de saída do `make`; agora o Stage23 exige os três arquivos presentes e não vazios antes de tentar compilar os objetos.

O novo `tools/exp76-stage23-prepare-gate.py` registra `prepare-make.rc` (código original), `prepare.rc` (resultado do gate), `PREPARE_GATE.json`, `prepare.errors.txt` e `prepare.first-error-context.txt`. Caso `make prepare` retorne zero com cabeçalhos ausentes, o gate usa o código sintético **97**, sem alterar o resultado original registrado. Em caso de falha real do `make`, preserva o código original e captura o contexto de até 12 linhas antes e oito depois do primeiro erro identificável.

O Stage23 preserva a regra de não tentar `cpupri.o`, `core.o` e `fork.o` quando o gate de preparação falha. O teste `tests/test_exp76_stage23_prepare_gate.py` contém quatro cenários determinísticos de regressão e foi executado no ambiente local antes da publicação.

Não houve nova aplicação do patch PREEMPT_RT ou remoção de rejeitos nesta etapa: a meta continua em **64 `.rej`**. O resultado real do Clang 21 posterior ao Stage22 ainda requer os logs da CI.

`EXP76_STAGE23_SOURCE=COMMITTED`; `EXP76_STAGE23_LOCAL_TESTS=4_PASS`; `EXP76_STAGE23_CI=UNVERIFIED`; `KERNEL_BUILT=false`; `FLASH_READY=false`.

## Stage24 — canal de evidência persistente, independente dos IDs do conector

Os Stages 20 e 21 usam entradas verificadas no artefato da auditoria Stage19: o rejeito `include/linux/swap.h.rej` tem SHA256 `445ee7f190e53347b5d25fbbcc9e29ba37a946763323743de2b9044ec8261370`, e a versão upstream de `include/linux/rcu_assign_pointer.h` tem SHA256 `32bf555037ac9f9506dbd0ceef386f31d5bc3fdc79b75ac9a1184ce95df07e1d`. Essas verificações confirmam os insumos, não a compilação dos objetos.

O conector GitHub utilizado não lista todas as execuções originadas por `push` ao consultar um SHA; por isso o workflow Clang21 agora possui um job de publicação de evidências separado, com `contents:write`, enquanto o job de compilação permanece `contents:read`.

- O coletor `tools/exp76-stage24-collect-ci-evidence.py` lê os JSONs `OBJECT_DIAGNOSTIC.json`, `PREPARE_GATE.json` e os manifestos Stages 19–21 quando estão presentes, mantendo explicitamente `null` ou `artifact_present=false` quando ausentes.
- O job publica apenas JSON resumido e limitado no branch isolado `exp76-ci-evidence`, nos arquivos `ci-evidence/clang21-latest.json` e `ci-evidence/runs/<run_id>.json`.
- Os registros incluem o commit fonte real e o URL `https://github.com/nywuer777/Pipa-Experimental-Kernel/actions/runs/<run_id>`, tornando possível consultar posteriormente o log com o ID real.
- Os testes `tests/test_exp76_stage24_evidence.py` verificam artefato ausente, resultado completo e a preservação do arquivo `latest` diante de uma publicação atrasada de ID anterior.

A meta permanece em 64 rejeições pendentes, e a semântica do scheduler ainda precisa de revisão. A publicação do canal é uma mudança de observabilidade; ela não prova que `make prepare` passou e não produz `Image`, `vmlinux` nem `boot.img`.

`EXP76_STAGE24_EVIDENCE_SOURCE=COMMITTED`; `EXP76_STAGE24_CI=UNVERIFIED`; `KERNEL_BUILT=false`; `FLASH_READY=false`.

## Stage25 — smoke do canal de evidências e resumo direto da CI

O arquivo `ci-evidence/clang21-latest.json` não estava presente na última consulta após o Stage24. Sem esse arquivo e sem um ID de run posterior confirmado, não há resultado novo de `make prepare`, `asm-offsets.s` ou dos três objetos.

Para separar problemas de publicação de problemas de compilação, foi criado o workflow leve `.github/workflows/exp76-stage25-relay-smoke.yml`. Ele não baixa Clang nem executa `make`: roda os três testes do coletor Stage24 e, após sucesso, tenta publicar `ci-evidence/relay-health.json` e `ci-evidence/relay-runs/<run_id>.json` no branch isolado `exp76-ci-evidence`.

O workflow principal `exp76-stage18-clang21-diagnostic.yml` passou a disponibilizar também um resumo `GITHUB_STEP_SUMMARY` com estado de `prepare`, códigos dos objetos e primeiras mensagens de erro, independente da escrita no branch de evidências. O job de compilação tem permissão explícita `contents: read`, enquanto o job de publicação mantém `contents: write`.

Se o heartbeat `relay-health.json` não aparecer, a publicação continua não demonstrada. Se aparecer, confirma a rota básica de escrita, não o funcionamento completo do compilador. A meta de rejeitos permanece 64 e nenhuma instalação/flash foi autorizada.

`EXP76_STAGE25_SOURCE=COMMITTED`; `EXP76_STAGE25_RELAY=UNVERIFIED`; `EXP76_STAGE25_CLANG21=UNVERIFIED`; `KERNEL_BUILT=false`; `FLASH_READY=false`.

## Stage25 — evidência real do Clang21, após Stage24

O canal de publicação foi validado pelo smoke `41376944941` (`collector_regression=success`). O diagnóstico da compilação `41376314394`, SHA `b98c8e787a0e5c002fbcfa3e5b09d613182ed1e8`, publicou `ci-evidence/clang21-latest.json`.

- `make prepare`: **PASS** (`gate_exit_code=0`), `asm-offsets.s` e os cabeçalhos gerados passaram.
- `kernel/sched/cpupri.o`: **PASS** (`exit_code=0`).
- `kernel/fork.o`: **FAIL** (`exit_code=2`) por `orig->cpus_ptr`, `orig->cpus_mask`, `tsk->cpus_ptr`, `tsk->cpus_mask` inexistentes em `task_struct` E404.
- `kernel/sched/core.o`: **FAIL** (`exit_code=2`) por `cpus_ptr` / `cpus_mask`, `migrate_disable` ausente e `check_task_state` não declarado.
- Stages 19, 20 e 21 aplicados conforme manifestos; **64 arquivos .rej** restantes. `KERNEL_BUILT=false`; `FLASH_READY=false`.

Evidência: https://github.com/nywuer777/Pipa-Experimental-Kernel/blob/exp76-ci-evidence/ci-evidence/clang21-latest.json

## Stage26 — ajuste cirúrgico do fork, sem alterar migração de CPU

O `task_struct` da E404 mantém `cpumask_t cpus_allowed` e `cpumask_t cpus_requested`, ambas embutidas, sem membros `cpus_ptr` ou `cpus_mask`. O `arch_dup_task_struct()` ARM64 desta base executa `*dst = *src`, duplicando a estrutura por valor. O código RT-140 que reatribui o ponteiro do filho para `&tsk->cpus_mask` é incompatível e desnecessário nessa representação.

`tools/exp76-rt-stage26-fork-affinity.py` remove somente essas duas linhas do `kernel/fork.c` pós-patch, exigindo evidências diretas da estrutura E404, cópia ARM64 por valor, código RT original e contagem pinada de 64 rejeitos. Os testes `tests/test_exp76_stage26_fork_affinity.py` incluem aplicação positiva e falhas por mudança da cópia ARM64 e dos campos de afinidade.

O código não substitui usos de `cpus_ptr` em `core.c`, não cria `migrate_disable` fictício e não declara o scheduler funcional. A nova CI deve confirmar se `kernel/fork.o` compila após o ajuste; somente então revisar as próximas incompatibilidades do scheduler core.

`EXP76_STAGE26_SOURCE=COMMITTED`; `EXP76_STAGE26_FORK_OBJECT_CI=PENDING`; `EXP76_RT_REJECT_TARGET=64`; `FLASH_READY=false`.

## Stage27 — reconciliação dos oito pontos de afinidade em core.c

Evidência de partida: o diagnóstico Clang21 mais recente acessível permanece no SHA `7babaa635098cc114e73eb25f6703b48516d1e57`, anterior ao Stage26, com `make prepare=PASS`, `cpupri.o=PASS`, `core.o=FAIL`, `fork.o=FAIL`. Não é confirmação de falha pós-Stage26.

O diff cumulativo do RT `4.19.325-rt140` substituiu a máscara embutida da E404 por referências `cpus_ptr`/`cpus_mask` em `kernel/sched/core.c`, embora `task_struct` E404 mantenha `cpumask_t cpus_allowed` e `cpumask_t cpus_requested`, com `nr_cpus_allowed` atualizado por `set_cpus_allowed_common()`.

O script `tools/exp76-rt-stage27-core-affinity.py` restaura os oito locais de afinidade alterados pelo RT (incluindo variantes `arg->campo` e `arg.campo`) e o comentário de proteção por locks. As substituições são fragmentos completos com cardinalidade exigida, precedidas da verificação do `task_struct` e da correção Stage26 em `fork.c`. O script mantém **64 arquivos `.rej`** e gera `stage27-status.json` antes da exportação do patch parcial.

Os testes `tests/test_exp76_stage27_core_affinity.py` cobrem uma aplicação positiva e falhas controladas por fragmento ausente, mudança da ABI E404 e ausência do ajuste Stage26. O coletor de evidências também foi atualizado para incluir os relatórios Stages 26–27.

**Limites:** `__migrate_disabled` continua referindo `p->migrate_disable`, e `wait_task_inactive` continua referindo `check_task_state` não portado. Por isso, `core.o` pode continuar falhando; sua compilação isolada não provaria segurança de migração nem equivalência PREEMPT_RT. Não há alteração das estruturas de task, bypass de avisos do Clang, kernel completo, boot.img ou flash.

`EXP76_STAGE27_SOURCE=COMMITTED`; `EXP76_STAGE27_CI=UNVERIFIED`; `EXP76_RT_TARGET_REJECTS=64`; `FLASH_READY=false`.

## Stage28 — `check_task_state` RT com `pi_lock`

**Evidência real Stage27:** execução Clang 21 `41378222225`, SHA `b16d214971f84b60bfe25d011a20a7a85e7b5b00`. O gate `make prepare` passou; `kernel/sched/cpupri.o` e `kernel/fork.o` passaram; `kernel/sched/core.o` falhou somente por `p->migrate_disable` ausente (`core.c:2002`) e `check_task_state` não declarado (`core.c:2392`). A auditoria confirmou Stages 19, 20, 21, 26 e 27 aplicados com 64 rejeições. Evidência: https://github.com/nywuer777/Pipa-Experimental-Kernel/actions/runs/41378222225.

O código RT de `wait_task_inactive()` verifica tanto `task->state` como `task->saved_state`. A aplicação parcial do patch acrescentou o segundo campo em `task_struct` e a chamada `check_task_state()` em `core.c`, mas perdeu a implementação auxiliar. Árvores Linux RT independentes implementam essa função sob `raw_spin_lock_irq(&p->pi_lock)`, comparando ambos os campos antes de `raw_spin_unlock_irq()`.

`tools/exp76-rt-stage28-task-state.py` introduz essa função estática imediatamente antes de `wait_task_inactive`, depois de exigir que `state`, `saved_state` e `pi_lock` existam e tenham o formato esperado na E404. O teste `tests/test_exp76_stage28_task_state.py` cobre aplicação única, campo ausente, lock alterado e duplicação. O script conserva a contagem de **64 rejeitos**.

O erro `migrate_disable` **não é contornado**. O RT necessita campos de estado, sincronização de scheduler e ciclos de desabilitar/habilitar migração; adicionar somente um membro ou um stub que retorne zero produziria compilação sem demonstrar correção. Stage28 mantém esse bloqueio visível até um port íntegro. Nenhuma imagem, módulo instalável ou flash é produzido.

`EXP76_STAGE28_SOURCE=COMMITTED`; `EXP76_STAGE28_CI=UNVERIFIED`; `EXP76_REJECTED_FILES_TARGET=64`; `KERNEL_BUILT=false`; `FLASH_READY=false`.

## Stage29 — ABI RT de migração em task_struct, sem ciclo de execução

**Evidência de partida:** Clang21 run `41381277114`, commit `a052f0655a7e4de1bfb727e8785dcc272273d380`. O gate `make prepare` passou; `cpupri.o` e `fork.o` compilaram. O único erro remanescente em `core.o` foi `p->migrate_disable` inexistente; o erro anterior de `check_task_state` desapareceu. Os manifestos registraram Stages 19, 20, 21, 26, 27 e 28 aplicados com 64 rejeições.

O rejeito original da atualização `include/linux/sched.h` contém `migrate_disable` e `migrate_disable_scheduled` para `CONFIG_SMP && CONFIG_PREEMPT_RT_BASE`, mais `pinned_on_cpu` sob `CONFIG_SCHED_DEBUG`, mas a mesma hunk tenta trocar a máscara E404 `cpus_allowed` por `cpus_ptr/cpus_mask`. Esta troca é incompatível com o scheduler e com os ajustes vendor de afinidade já validados.

`tools/exp76-rt-stage29-migration-abi.py` recupera **apenas** os campos RT com as mesmas condições de compilação, inserindo-os após `cpus_requested` e preservando `nr_cpus_allowed`, `cpus_allowed` e `cpus_requested`. O script inspeciona o rejeito original e `__migrate_disabled()`, exige 64 rejeições e falha se a ABI mudar. Em `__sched_fork()`, inicializa `migrate_disable=0`, `migrate_disable_scheduled=false` e `pinned_on_cpu=-1` sob os guards correspondentes. Seis testes sintéticos verificam execução sem escrita, aplicação positiva, campo duplicado, rejeito alterado, máscara vendor alterada e init de fork ausente.

**Contrato de segurança:** os campos não implementam `migrate_disable()` e `migrate_enable()`; continuam ausentes os hooks completos do scheduler, `rq->nr_pinned`, tratamento de hotplug e auditoria de `sleeping_lock`. Uma eventual compilação dos três objetos significa apenas compilação dos objetos: não demonstra link, PREEMPT_RT funcional, ABI Android preservada para instalação, ou capacidade de boot. Nenhuma imagem é gerada e `FLASH_READY=false`.

`EXP76_STAGE29_SOURCE=COMMITTED`; `EXP76_STAGE29_CI=UNVERIFIED`; `EXP76_REJECTS_TARGET=64`; `KERNEL_BUILT=false`; `FLASH_READY=false`.

## Stage30 — ampliar cobertura real do PREEMPT_RT sem link de kernel

**Evidência Stage29:** run `41385145583` sobre `04ce35fa20c6627a7db6b1b96c9e0ef308a9f922`. O Clang 21 completou `make prepare` e compilou `cpupri.o`, `core.o` e `fork.o` (**3/3**). O log de `core.o` ainda alertou: `migrate_disabled_sched` possui ligação interna, porém não possui definição disponível. Os Stages 19/20/21/26/27/28/29 foram aplicados; 64 rejeitos RT continuam sem resolução.

**Expansão diagnóstica:** o script `tools/exp76-stage30-object-coverage.py` compila individualmente, somente quando a base 3/3 passou, os seguintes alvos: `kernel/sched/rt.o`, `fair.o`, `deadline.o`, `idle.o`, `stop_task.o`, `kernel/cpu.o`, `kernel/locking/rtmutex.o`, `kernel/softirq.o` e `kernel/time/timer.o`. Cada alvo tem timeout, código de saída e resumo dos primeiros erros próprios. O script **não liga vmlinux, não gera Image/boot.img, não gera módulos e não escreve no dispositivo**.

A saída `exp76-stage30-report/OBJECT_COVERAGE.json` distingue os objetos tentados, compilados e bloqueados pelo gate inicial. Ela também registra a presença de declarações e definições de `migrate_disabled_sched` em `core.c`, mas explicitamente não interpreta uma definição como prova de corretude do runtime de migração. O collector Stage24 preserva esta saída resumida no branch `exp76-ci-evidence` sob `extra_object_coverage`. O teste `tests/test_exp76_stage30_object_coverage.py` verifica a allowlist dos nove objetos, aviso de helper ausente, gate inicial, alvo não permitido e compilação sintética de um objeto com warning.

**Ainda pendente:** resta portar o contrato PREEMPT_RT completo de `migrate_disable/enable`, `migrate_disabled_sched`, `rq->nr_pinned`, regras de hotplug, `sleeping_lock` e todos os demais rejeitos RT. Sucesso do Stage30 significa cobertura parcial de objetos, nunca kernel completo ou flash autorizado.

`EXP76_STAGE30_SOURCE=COMMITTED`; `EXP76_STAGE30_CI=UNVERIFIED`; `EXP76_RT_REJECTS=64`; `KERNEL_BUILT=false`; `FLASH_READY=false`.

## Stage31 — compatibilidade dos escalonadores RT, CFS e deadline com E404

**Evidência real Stage30:** execução `41386243228` no commit `6b78ce3a45366046caec4b1d0b67fc08c61a0152`. Os três objetos base compilaram e `make prepare` passou. Dos nove objetos adicionais, `kernel/sched/idle.o` e `kernel/sched/stop_task.o` compilaram. `rt.o` (2 erros), `fair.o` (1 erro) e `deadline.o` (3 erros) falharam em campos `cpus_ptr` não existentes em `task_struct` da E404; `cpu.o` não encontrou `cpu_nr_pinned`; `rtmutex.o` não encontrou `might_sleep_no_state_check`; `timer.o` não encontrou `timer_update_work`. `softirq.o` apresentou múltiplos erros de conflito de API e pré-processamento (inclusive `#else without #if`).

A árvore E404 `fed88a6024cd4d46c52eda607a95d97d7371ba81` possui `cpumask_t cpus_allowed` embutida e não possui `cpus_ptr`. A diff parcial RT Stage19 mostrou que somente **seis expressões de código** (duas em `rt.c`, uma em `fair.c`, três em `deadline.c`) e **um comentário** foram alterados para essa ABI incompatível.

`tools/exp76-rt-stage31-class-affinity.py` substitui exatamente esses sete fragmentos, restaura o comentário referente a `cpus_allowed`, exige a estrutura vendor e preserva as 64 rejeições. Nenhuma alteração é feita nos estados de migração, na política de scheduler ou nos locks. Os sete cenários de `tests/test_exp76_stage31_class_affinity.py` verificam modo sem escrita, aplicação, expressão ausente, troca da ABI, rejeito faltante, expressão duplicada e fonte parcialmente alterada.

O pipeline Clang 21 mantém o gate base 3/3 e executa os nove objetos adicionais; o coletor persiste o manifesto Stage31 no branch `exp76-ci-evidence`.

**Limites:** a correção não resolve `cpu_nr_pinned`, `might_sleep_no_state_check`, `timer_update_work`, `softirq`, `migrate_disabled_sched` nem o restante da árvore RT. Ainda não existe kernel completo, link `vmlinux`, boot.img ou autorização de flash.

Evidência: https://github.com/nywuer777/Pipa-Experimental-Kernel/blob/exp76-ci-evidence/ci-evidence/clang21-latest.json

`EXP76_STAGE31_SOURCE=COMMITTED`; `EXP76_STAGE31_CI=UNVERIFIED`; `EXP76_RT_REJECTS=64`; `EXP75_PERMANENT=PRESERVED`; `KERNEL_BUILT=false`; `FLASH_READY=false`.

## Stage32 — correção do gate de afinidade NUMA que bloqueou a Stage31

**Falha real:** GitHub Actions `41388920664`, SHA `27f7e3a6ffbad853a0ad4385f3d70f26ee8e07ad`. O job de validação de scripts concluiu com sucesso, incluindo `EXP76_STAGE31_CLASS_AFFINITY_REGRESSIONS=7_PASS`, mas a auditoria abortou antes do gate `make prepare`:

```text
ValueError: kernel/sched/fair.c: unrecognized remaining RT affinity reference
```

O patch RT-140 aplicado à E404 modifica **três expressões** de afinidade em `fair.c`, mais um comentário; o script Stage31 havia tratado somente uma expressão e o comentário. Os pontos adicionais são o teste da CPU de origem em `task_numa_compare()`, `cur->cpus_ptr`, e o teste de CPU candidata em `task_numa_find_cpu()`, `env->p->cpus_ptr`.

Stage32 atualiza `tools/exp76-rt-stage31-class-affinity.py` para cobrir esses dois locais, restaurando o acesso às máscaras embutidas `&cur->cpus_allowed` e `&env->p->cpus_allowed`. O total do port de `rt.c`, `fair.c` e `deadline.c` é agora **nove fragmentos exatos** (oito expressões C e um comentário). O script falha se uma ocorrência sumir, duplicar, ou restar `->cpus_ptr` nos três arquivos. O manifesto registra `stage32_fair_numa_affinity_reconciled=true`.

Os testes `tests/test_exp76_stage31_class_affinity.py` passaram a exigir os nove fragmentos e incluem dois novos casos específicos: ausência do teste NUMA de origem e duplicação do teste NUMA de destino. O workflow existente executa esses testes e a auditoria antes do Clang 21; nenhuma alteração de configuração de hardware, flash, política de scheduler, estado de migração ou locks foi introduzida.

**Estado de evidência:** Stage31 falhou na auditoria e **não** produziu novos objetos. O placar real anterior permanece `3/3` objetos base e `2/9` objetos adicionais. As próximas saídas precisam validar se o Stage32 desbloqueia a auditoria e permite compilar `rt.o`, `fair.o` e `deadline.o`.

`EXP76_STAGE32_SOURCE=COMMITTED`; `EXP76_STAGE32_CI=UNVERIFIED`; `EXP76_RT_REJECTS=64`; `EXP75_PERMANENT=PRESERVED`; `KERNEL_BUILT=false`; `FLASH_READY=false`.

## Stage33 — três referências cpus_ptr preexistentes na E404, não no patch RT

**Falha real Stage32:** Clang21 run `41392088296`, commit `53b56b6a4cb3ed587443ae19381696a72e314382`, com testes `EXP76_STAGE32_FAIR_NUMA_REGRESSIONS=9_PASS`, mas auditoria `Stage31` interrompida por `ValueError: kernel/sched/fair.c: unrecognized remaining RT affinity reference`. A compilação dos objetos foi ignorada pelo job após a falha; não há um novo placar de Clang.

O exame da árvore E404 original no commit fixado `fed88a6024cd4d46c52eda607a95d97d7371ba81` confirmou **três** outras ocorrências de `cpus_ptr` em `kernel/sched/fair.c` anteriores ao RT: a expressão `for_each_cpu_and(cpu, cpu_smt_mask(target), p->cpus_ptr)` de `select_idle_smt()`, o comentário `cannot be migrated ... due to cpus_ptr` e o comentário `isn't true due to cpus_ptr constraints`. Nenhuma dessas ocorrências fazia parte do diff parcial de Stage19 utilizado como fonte das substituições Stage31/32.

O script de port `tools/exp76-rt-stage31-class-affinity.py` agora contém **12 fragmentos exatos** (nove expressões C e três comentários), dos quais nove vêm do RT e três já existiam na E404. A máscara embutida `cpus_allowed` é usada no caminho SMT; os comentários também passam a referir a mesma ABI. O gate final verifica tokens `cpus_ptr`/`cpus_mask` em todas as linhas dos três arquivos, reporta até oito linhas de contexto se restarem ocorrências e nunca escreve parcialmente o port se houver divergência.

O teste `tests/test_exp76_stage31_class_affinity.py` agora inclui as três ocorrências da E404 como fixtures independentes e falha na ausência de qualquer uma. No manifesto `stage31-status.json`, `stage33_preexisting_vendor_fair_cpus_ptr_reconciled=true` registra a correção aplicada. O Stage33 usa os workflows existentes; não altera parâmetros do dispositivo nem as rotinas de migração e locking do kernel.

O último resultado *válido* de compilação continua sendo Stage30: **3/3 objetos base e 2/9 objetos extras**, com 64 rejeitos RT, até nova execução com Stage33. `KERNEL_BUILT=false`; `FLASH_READY=false`; EXP75 preservado.

`EXP76_STAGE33_SOURCE=COMMITTED`; `EXP76_STAGE33_CI=UNVERIFIED`; `EXP76_RT_REJECTS=64`.
