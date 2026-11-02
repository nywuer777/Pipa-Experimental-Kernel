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

## Stage34 — restauração do worker RT dos timers a partir do rejeito original

**Evidência Clang21 Stage33:** run `41397136733`, SHA `d69a6b513ee7943d9697b767840e9277b06560c2`. `make prepare=PASS`; objetos iniciais `3/3 PASS`. Entre os nove objetos adicionais, **5/9 PASS**: `sched/rt.o`, `sched/fair.o`, `sched/deadline.o`, `sched/idle.o` e `sched/stop_task.o`. Os quatro bloqueios restantes são `cpu_nr_pinned` em `kernel/cpu.o`, `might_sleep_no_state_check` em `kernel/locking/rtmutex.o`, `timer_update_work` em `kernel/time/timer.o` e conflitos extensos de API/preprocessamento em `kernel/softirq.o`. O compilador também emitiu `-Wundefined-internal` sobre `migrate_disabled_sched` em `core.o`. Permanecem 64 rejeitos de aplicação de RT.

A atualização parcial do RT-140 em `kernel/time/timer.c` removeu a declaração de `timer_update_work`, acrescentou `timer_update_swork` e mudou o callback para `struct swork_event *`. Entretanto, o hunk de `kernel/time/timer.c.rej` não foi aplicado: `timers_update_nohz()` continuou chamando `schedule_work(&timer_update_work)`. O mesmo hunk rejeitado inclui `swork_queue(&timer_update_swork)`, `WARN_ON(swork_get())`, `INIT_SWORK` e `early_initcall(hrtimer_init_thread)`.

O port Stage34 em `tools/exp76-rt-stage34-timer-swork.py` usa **o conteúdo textual exato do rejeito** como pré-condição. Inspeciona `include/linux/swork.h`, `kernel/sched/swork.c` e `kernel/sched/Makefile` para exigir o backend real. Insere `#include <linux/swork.h>`, restaura a fila `swork_queue()` e insere a função de init exatamente como fornecida no patch RT. O teste `tests/test_exp76_stage34_timer_swork.py` cobre verificação sem escrita, aplicação positiva, rejeito divergente, backend inexistente, Makefile divergente, corpo timer alterado e contagem de rejeitos incorreta. O manifesto `stage34-status.json` preserva `remaining_rejected_files=64` e `flash_ready=false`.

**Limites:** a restauração de timer ainda exige prova de compilação no Clang21. Não prova execução correta de callbacks, inicialização completa do scheduler ou segurança PREEMPT_RT. Os componentes de CPU hotplug, rtmutex, softirq, migração e as demais rejeições continuam pendentes. Nenhuma alteração no EXP75, nenhum link de kernel, `Image` ou `boot.img`.

`EXP76_STAGE34_SOURCE=COMMITTED`; `EXP76_STAGE34_CI=UNVERIFIED`; `EXP76_RT_REJECTS=64`; `KERNEL_BUILT=false`; `FLASH_READY=false`.

## Stage35 — `might_sleep_no_state_check` original da RT em `kernel.h`

**Evidência Stage34:** execução Clang21 `41440311252` no commit `89f0e312fe2c50f0111c1c7c5eb859385ab0f9b5`, com `make prepare` PASS, objetos iniciais 3/3 e objetos adicionais **6/9** compilados. O `timer.o` passou após restauração do `swork`. Restaram `cpu.o` (chamada não declarada `cpu_nr_pinned`), `kernel/locking/rtmutex.o` (chamada não declarada `might_sleep_no_state_check`) e `softirq.o` (conflitos extensos de API/preprocessador). `sched/core.o` segue com warning `migrate_disabled_sched` sem definição. Permanecem 64 rejeitos.

O rejeito `include/linux/kernel.h.rej` na árvore E404 contém **duas definições RT não aplicadas** de `might_sleep_no_state_check`:

- Com `CONFIG_DEBUG_ATOMIC_SLEEP`: `do { ___might_sleep(__FILE__, __LINE__, 0); might_resched(); } while (0)`. O uso de três underscores é intencional: a variante sem verificação de estado não é a mesma coisa que `__might_sleep`.
- Sem `CONFIG_DEBUG_ATOMIC_SLEEP`: `do { might_resched(); } while (0)`.

`tools/exp76-rt-stage35-might-sleep.py` exige exatamente esses dois fragmentos no rejeito oficial, as duas posições originais em `include/linux/kernel.h`, a função auxiliar `___might_sleep` presente nas duas variantes da configuração, a chamada `might_sleep_no_state_check()` em `rtmutex.c` e 64 rejeitos RT. Só então insere as duas macros nos ramos existentes do cabeçalho, sem tocar em `rtmutex.c`, outras APIs de lock ou na semântica de `might_sleep()`.

`tests/test_exp76_stage35_might_sleep.py` cobre verificação sem escrita, aplicação positiva, rejeito divergente em ambos os ramos, declaração auxiliar ausente, chamada RT ausente, duplicação da macro e contagem de rejeições. O workflow Clang 21 e o collector Stage24 incluem o novo manifesto `stage35-status.json` e preservam `FLASH_READY=false`.

**Limites:** mesmo se `rtmutex.o` compilar, não há prova de locking funcional, ciclo de migração completo, kernel linkável, inicialização/boot ou integridade PREEMPT_RT. `cpu.o`, `softirq.o`, `migrate_disabled_sched` e as demais rejeições permanecem tarefas distintas.

`EXP76_STAGE35_SOURCE=COMMITTED`; `EXP76_STAGE35_CI=UNVERIFIED`; `EXP76_RT_REJECTS=64`; `EXP75_PERMANENT=PRESERVED`; `KERNEL_BUILT=false`; `FLASH_READY=false`.

## Stage36 — contrato de migração real e proteção contra `cpu_nr_pinned()` fictício

**Evidência disponível ao iniciar:** execução `41440311252` (Stage34) com `make prepare` PASS, `3/3` objetos base e `6/9` objetos adicionais compilados. O Stage35 restaurou `might_sleep_no_state_check()` e foi publicado no commit `cdfa1c11bf4c1cb00aba7ce8faacfffd50a11c76`, mas o relatório de Clang21 desse commit ainda não estava disponível ao iniciar Stage36. Em particular, não se afirma que `rtmutex.o` já compilou.

A chamada `cpu_nr_pinned(cpu)` em dois pontos do hotplug `kernel/cpu.c` faz parte de um contrato maior do RT-140. O rejeito real `kernel/sched/core.c.rej` contém as implementações de `migrate_disable()`, `migrate_disabled_sched()`, `migrate_enable()` e `cpu_nr_pinned()`. O `migrate_disable()` incrementa `this_rq()->nr_pinned` na primeira entrada; `migrate_enable()` decrementa o contador, acorda a tarefa responsável por derrubar a CPU quando necessário e pode agendar migração efetiva. O rejeito `kernel/sched/sched.h.rej` acrescenta o campo `rq->nr_pinned` sob `CONFIG_PREEMPT_RT_BASE && CONFIG_SMP`.

**Incompatibilidade obrigatória:** os helpers upstream alteram `p->cpus_ptr` e `p->cpus_mask` para fixar e restaurar a afinidade. A E404 conserva `cpus_allowed` e `cpus_requested` embutidos, e esse algoritmo deve ser portado por inteiro antes de habilitar o ciclo; simplesmente acrescentar `cpu_nr_pinned() { return 0; }` ou declarar um `rq->nr_pinned` nunca mantido mascararia o risco de hotplug e não é solução.

`tools/exp76-stage36-migration-contract.py` é uma **auditoria somente de leitura da fonte**: exige cardinalidades verificadas dos trechos originais rejeitados, as duas chamadas em `cpu.c`, os campos RT previamente introduzidos no `task_struct`, as declarações correspondentes em `preempt.h` e 64 rejeitos pendentes. Se alguém adicionar apenas um helper, uma definição isolada ou o contador sem completar o ciclo, o gate falha e exige nova auditoria. O JSON `stage36-status.json` lista os sete componentes pendentes e registra explicitamente `cross_file_runtime_contract_complete=false`.

`tests/test_exp76_stage36_migration_contract.py` cobre execução sem escrita, manifesto positivo e cinco cenários de drift além da contagem errada de rejeitos. Os workflows de auditoria e Clang21 incluem este gate antes de gerar o patch parcial, e o relay Stage24 registra o resultado no branch `exp76-ci-evidence`. Nenhuma semântica de migração foi alterada no Stage36.

**Pendências reais:** `cpu.o` depende do ciclo completo; `softirq.o` depende de revisão de API/preprocessador; `migrate_disabled_sched` permanece sem definição em `core.o` até o port verdadeiro; a resolução das 64 rejeições ainda é necessária. Nenhum `Image`, `boot.img`, `vmlinux` ou flash foi produzido.

`EXP76_STAGE36_SOURCE=COMMITTED`; `EXP76_STAGE36_CI=UNVERIFIED`; `EXP75_PERMANENT=PRESERVED`; `KERNEL_BUILT=false`; `FLASH_READY=false`.

## Stage37 — correção do contador de rejeitos no relatório de migração

**Falha confirmada:** execução Clang21 `41444634468` sobre `46c11ae2683e06fa587bf45ace7e26cd3a8acc37`. A validação de scripts passou nos Stages anteriores, inclusive `EXP76_STAGE35_MIGHT_SLEEP_REGRESSIONS=8_PASS`, mas `tests/test_exp76_stage36_migration_contract.py` falhou ao comparar `report["remaining_rejected_files"] == 64`. A auditoria e as compilações de objetos foram, por isso, ignoradas. Nenhum objeto novo foi compilado nesse job.

A causa está na própria ferramenta Stage36: a variável local `count` iniciou com o número de arquivos `*.rej`, mas o laço de verificação de `include/linux/preempt.h` reutilizou `count` para ocorrências de declarações. O manifesto saiu com o valor desta última contagem, não com o número de rejeitos. O gate de 64 rejeições **já estava correto**, mas o valor reportado era incorreto.

Stage37 separa `reject_count` de `declaration_count` e utiliza somente o primeiro para `remaining_rejected_files`. O teste positivo agora confronta o manifesto com `len(list(tree.rglob("*.rej")))` e há um caso negativo novo para declarações duplicadas em `preempt.h`. O teste passa a anunciar `EXP76_STAGE37_RT_MIGRATION_CONTRACT=8_PASS` quando executado.

**Verificação adicional:** os marcadores RT do rejeito `kernel/sched/core.c.rej` e o campo `nr_pinned` do rejeito `kernel/sched/sched.h.rej` foram comparados com o pacote original de auditoria E404: a cardinalidade usada pelo Stage36 está consistente. O próximo teste real da auditoria ainda depende da CI Stage37.

Nenhuma modificação na lógica do scheduler, ABI da E404, `cpu_nr_pinned`, migração ou `softirq` ocorre neste stage. Os 64 arquivos rejeitados permanecem pendentes. `EXP75_PERMANENT=PRESERVED`; `KERNEL_BUILT=false`; `FLASH_READY=false`.

## Stage38 — reconstituição da entrada RT do `softirq.c` com rejeitos reais

**Evidência Stage37:** a execução `41446901762`, SHA `e0f49beca67d885e43ffaca8d2c385f873deda1a`, confirmou que a auditoria Stage36 registrou **64 rejeitos**, os três objetos iniciais compilaram e os objetos adicionais chegaram a **7/9**. `kernel/locking/rtmutex.o` passou depois do port de `might_sleep_no_state_check()` da Stage35. Os dois objetos ainda sem compilação são `kernel/cpu.o` (ausência do ciclo real de `cpu_nr_pinned`) e `kernel/softirq.o`.

O patch RT parcialmente aplicado inseriu `#else /* !PREEMPT_RT_FULL */` e os handlers RT no `kernel/softirq.c`, mas os trechos que definiam o `#ifndef CONFIG_PREEMPT_RT_FULL` correspondente, `ktimer_softirqd` e os helpers de execução de vetores permaneceram em `kernel/softirq.c.rej`. Consequências da CI anterior incluíam `#else without #if`, definições duplicadas de `__local_bh_enable`, chamadas conflitantes e ausência de `handle_softirq` e `softirq_set_runner`.

**Port Stage38:** `tools/exp76-rt-stage38-softirq-entry.py` extrai diretamente os **três primeiros hunks rejeitados** da E404 fixada, com pré-condições exatas de fonte:
- preserva o registro `ktimer_softirqd`, máscara `TIMER_SOFTIRQS`, `softirq_check_pending_idle`, rastreadores por CPU e proteção contra avisos NOHZ falsos;
- restaura `wakeup_timer_softirqd` e `handle_softirq` a partir do rejeito, sem inserir uma implementação vazia;
- restabelece o `#ifndef CONFIG_PREEMPT_RT_FULL` antes da seção de softirqs convencional, incluindo os helpers não RT `ksoftirqd_softirq_pending`, `handle_pending_softirqs` e `run_ksoftirqd`, mantendo o `#else` RT já aplicado;
- valida a estrutura completa de diretivas `#if/#ifdef/#ifndef/#elif/#else/#endif` do arquivo modificado, falhando em qualquer `#else` órfão ou `#endif` excedente.

`tests/test_exp76_stage38_softirq_entry.py` exercita verificação sem escrita, aplicação com fragmentos originais, marcador RT ausente, hunk divergente, aplicação duplicada, número de rejeitos divergente, âncora de fonte ausente e estrutura de pré-processador inválida. O manifesto `stage38-status.json` mantém `full_softirq_semantics_verified=false` e `flash_ready=false`.

**Limites:** o Stage38 não afirma compilação de `softirq.o` antes de receber o novo log Clang21. O conjunto completo de 64 rejeições RT e a verificação de runtime continuam pendentes, incluindo `migrate_disable/enable`, `migrate_disabled_sched`, `rq->nr_pinned` e o hotplug em `kernel/cpu.c`. Sem `vmlinux`, `Image`, `boot.img` ou alteração do dispositivo.

`EXP76_STAGE38_SOURCE=COMMITTED`; `EXP76_STAGE38_CI=UNVERIFIED`; `EXP75_PERMANENT=PRESERVED`; `KERNEL_BUILT=false`; `FLASH_READY=false`.

## Stage39 — segunda guarda RT em `invoke_softirq`: CI Stage38 corrigida

**Falha real:** a execução Clang21 `41448935481` sobre `e32defde3e9b5b3f10c8a6ea2140fe0679b91d88` passou em `EXP76_STAGE38_SOFTIRQ_ENTRY_REGRESSIONS=7_PASS` e concluiu Stage36, mas o port de `softirq.c` interrompeu a auditoria com:

```text
ValueError: softirq.c:895: #else without #if
```

A Stage38 recuperou os três primeiros hunks rejeitados de `kernel/softirq.c.rej` e, com isso, restaurou o primeiro `#ifndef CONFIG_PREEMPT_RT_FULL`. A segunda guarda, dentro da função `invoke_softirq()`, está no **sexto hunk** rejeitado (`@@ -359,6 +831,7 @@ void irq_enter(void)`). A árvore E404 original contém `if (!force_irqthreads)` nesse ponto, enquanto o hunk RT original descreve um contexto de `ksoftirqd_running()`. Copiar o hunk literalmente não funciona; a diretiva é portada mantendo o corpo vendor e o `#else /* PREEMPT_RT_FULL */` já aplicado.

Stage39 atualiza `tools/exp76-rt-stage38-softirq-entry.py` para exigir exatamente o sexto hunk original, a função E404 `invoke_softirq()` e o segundo `#else` RT já presente. Insere `#ifndef CONFIG_PREEMPT_RT_FULL` imediatamente antes de `if (!force_irqthreads)`. A saída passa a exigir **duas** guardas restauradas e comprova o balanceamento de todas as diretivas pré-processadas antes de alterar a fonte. O manifesto `stage38-status.json` registra `original_rejected_hunks_consumed=4` e `stage39_invoke_softirq_guard_restored=true`.

A regressão `tests/test_exp76_stage38_softirq_entry.py` usa um segundo `invoke_softirq` sintético com o `#else` RT preexistente, verifica a guarda emparelhada e adiciona casos de rejeito divergente e contexto vendor alterado. A ferramenta não suprime erros de Clang nem substitui funções ausentes por stubs.

**Evidência pendente:** o Stage38 não executou a compilação de objetos após o erro de auditoria. Stage39 ainda precisa confirmar a auditoria e gerar um novo diagnóstico Clang21 de `kernel/softirq.o`. O último resultado de compilação preservado permanece 3/3 objetos base, 7/9 adicionais, com 64 rejeitos RT. `cpu.o` e o runtime de migração seguem pendentes.

`EXP76_STAGE39_SOURCE=COMMITTED`; `EXP76_STAGE39_CI=UNVERIFIED`; `EXP75_PERMANENT=PRESERVED`; `KERNEL_BUILT=false`; `FLASH_READY=false`.

## Stage40 — `task_struct.sleeping_lock` RT e inicialização em fork

**Contexto da fonte:** o rejeito oficial `include/linux/sched.h.rej` do patch `4.19.325-rt140` contém `int sleeping_lock;` exclusivamente sob `CONFIG_PREEMPT_RT_FULL`. A fonte E404 fixada conserva `cpus_allowed` e `cpus_requested` embutidos, sem `sleeping_lock`. O código de tratamento RT de `kernel/softirq.c`, restaurado dos rejeitos em Stage38/39, inclui `softirq_check_runner_tsk()` e lê `tsk->sleeping_lock` sob `tsk->pi_lock`. O campo falta na estrutura da E404 e deve ser portado antes de compilar esse caminho.

**Port Stage40:** `tools/exp76-rt-stage40-sleeping-lock.py` exige a ocorrência exata do campo no rejeito oficial, a leitura correspondente em `softirq.c`, o bloco de migração do Stage29 em `include/linux/sched.h`, a inicialização anterior de `migrate_disable` em `kernel/sched/core.c` e a contagem de 64 rejeitos RT. Insere somente:

```c
#ifdef CONFIG_PREEMPT_RT_FULL
	int sleeping_lock;
#endif
```

no `task_struct`, e inicializa `p->sleeping_lock = 0;` sob o mesmo `#ifdef` em `__sched_fork()`. Preserva a ABI vendor `cpus_allowed/cpus_requested` e evita copiar um valor de lock ativo para uma tarefa recém-criada. O teste `tests/test_exp76_stage40_sleeping_lock.py` cobre verificação sem escrita, aplicação positiva, rejeito alterado, ausência do leitor RT, inicialização duplicada, afinidade modificada, âncora do task ausente e número de rejeitos incorreto.

Os workflows de compatibilidade e diagnóstico Clang21 executam o script após Stage39. `stage40-status.json` é integrado ao relay de CI e diferencia campo aplicado de confirmação de compilação e validação de runtime.

**Estado de evidência atualizado:** execução Clang21 `41450161880` sobre Stage39 `2cbe9950e55df391a595226949abdcf1d9797ee3`, com auditoria PASS, `3/3` objetos base e `8/9` adicionais compilados, inclusive `softirq.o`; 64 rejeitos RT persistem. O Stage40 não é a causa desse sucesso já confirmado: restaura a ABI `sleeping_lock` como pré-requisito de outros caminhos de configuração. `kernel/cpu.o` ainda depende do ciclo real de `cpu_nr_pinned` e o kernel completo continua sem link ou validação de runtime.

`EXP76_STAGE40_SOURCE=COMMITTED`; `EXP76_STAGE40_CI=UNVERIFIED`; `EXP75_PERMANENT=PRESERVED`; `KERNEL_BUILT=false`; `FLASH_READY=false`.

## Stage41 — ciclo RT de migração e pinagem da runqueue, adaptado à E404

**Ponto de partida comprovado:** execução Clang21 `41455627896`, commit `1a4e831198dac1fed58278e4694c44cf45096f06`. A auditoria Stage40 foi aplicada, `make prepare` passou, 3/3 objetos iniciais e 8/9 adicionais compilaram. O único erro adicional foi em `kernel/cpu.o`, com duas chamadas de `cpu_nr_pinned` sem declaração; `core.o` continuava com `migrate_disabled_sched` declarado sem implementação. 64 arquivos `.rej` permanecem.

**Fonte do port:** último hunk rejeitado de `kernel/sched/core.c.rej`, originário do patch RT oficial `4.19.325-rt140` (marcador `@@ -7111,3 +7225,171 @@`), e campo `rq->nr_pinned` de `kernel/sched/sched.h.rej`. O script `tools/exp76-rt-stage41-migration-lifecycle.py` exige o hunk inteiro, o contador original com incremento/decremento, a lógica aninhada de `migrate_disable()`/`migrate_enable()`, o stopper assíncrono, o despertar do processo de CPU hotplug e os exports de símbolos RT (SMP e UP). Não usa uma função fictícia que sempre retorna zero.

**Diferença de ABI:** o RT upstream usa `p->cpus_ptr` para selecionar temporariamente a máscara da CPU, sem sobrescrever `p->cpus_mask`. A E404 não possui esses campos; consulta `p->cpus_allowed` embutido e mantém `p->cpus_requested` para outras finalidades. Stage41 acrescenta `cpumask_t migrate_disable_saved_mask` sob `CONFIG_SMP && CONFIG_PREEMPT_RT_BASE`, salva o valor anterior ao marcar a tarefa como pinada e restaura no `migrate_enable()` final. A integração de `__set_cpus_allowed_ptr()` redireciona atualizações de afinidade para a máscara salva quando a tarefa está pinada. `cpus_requested` é preservado.

O port também acrescenta `rq->nr_pinned` sob o mesmo contrato RT/SMP e declara `cpu_nr_pinned()` em `include/linux/cpu.h` para os dois consumidores de `kernel/cpu.c`. `kernel/sched/core.c` recebe os helpers de pinagem, o ciclo de migração aninhada e a definição real de `migrate_disabled_sched()`. A função `cpu_nr_pinned()` lê o contador atualizado na runqueue, **não um valor constante**. O código de migração assíncrona upstream conserva as verificações `arg->done` e `work->disabled`, sem substituí-las por silêncio.

`tests/test_exp76_stage41_migration_lifecycle.py` cobre modo de verificação sem escrita, aplicação, rejeito alterado, máscara incompatível, consumidor hotplug ausente, implementação duplicada e contagem de rejeitos divergente. A auditoria Clang21 ainda executa o gate base 3/3 e os nove objetos adicionais, arquivando `stage41-status.json` no ramo isolado `exp76-ci-evidence`.

**Limite técnico obrigatório:** Stage41 porta código-fonte e tenta a compilação, mas a correção dos 64 rejeitos restantes, a validação de pré-empção, pinagem sob concorrência, alterações simultâneas de afinidade, migração assíncrona, CPU hotplug, linkage completo e boot seguem **não comprovados**. A introdução de uma máscara própria requer revisão de concorrência e invariantes além do teste de objetos. Mesmo com `cpu.o` compilado, isso não libera `vmlinux`, `Image`, `boot.img` ou flash.

`EXP76_STAGE41_SOURCE=COMMITTED`; `EXP76_STAGE41_CI=UNVERIFIED`; `EXP76_RT_REJECTS=64`; `EXP75_PERMANENT=PRESERVED`; `KERNEL_BUILT=false`; `FLASH_READY=false`.

## Stage42 — handshake RT de CPU hotplug e hook TLB arm64

**Falha confirmada da Stage41:** execução Clang 21 `41461128644`, SHA `d28286adea4d8a486c5dd39f758d2cb8a8cb221a`. Auditoria `stage41.applied=true`, `make prepare` concluído e 64 rejeitos pendentes. Dos três objetos iniciais, `fork.o` e `cpupri.o` compilaram, mas `sched/core.o` falhou com `undeclared identifier 'takedown_cpu_task'` nas linhas 9306 e 9307, além de `implicit declaration of function 'tlb_migrate_finish'` na linha 9337. Todos os nove objetos adicionais foram pulados devido ao gate do core, portanto **não existe** placar Stage41 para `cpu.o`. O último placar com compilação adicional válida é 8/9, anterior ao Stage41.

**Hotplug:** o patch RT 4.19 usa `takedown_cpu_task` para despertar o processo de CPU offlining quando o último `migrate_disable()` libera a runqueue. A E404 parcialmente convertida já verifica `cpu_nr_pinned(cpu)` durante `take_cpu_down()`, mas não possuía o lado de espera e repetição do protocolo. Stage42 verifica em `kernel/cpu.c`, sob `CONFIG_PREEMPT_RT_BASE`, o ponteiro da tarefa de takedown, a espera `TASK_UNINTERRUPTIBLE` até `cpu_nr_pinned(cpu)==0`, a repetição de `stop_machine_cpuslocked()` após `-EAGAIN` e a limpeza do ponteiro em erro e conclusão. **Se o patch RT já instalou integralmente o protocolo, a fonte existente é reutilizada sem escrita ou duplicação**; se está ausente, o protocolo é aplicado; se está parcialmente presente, a auditoria falha sem alterar arquivos. `core.c` recebe a declaração externa somente sob `CONFIG_HOTPLUG_CPU && CONFIG_PREEMPT_RT_BASE`, preservando `wake_up_process(takedown_cpu_task)` e o decremento de `rq->nr_pinned`. Isso adapta o protocolo upstream, **não** substitui os contadores por retornos fixos. Referência pública de comportamento: `sched: Lazy migrate_disable processing`, commit RT `425c5b38779a860062aa62219dc920d374b13c17`.

**TLB:** a E404 usa `arch/arm64/include/asm/tlb.h` com `include/asm-generic/tlb.h`, e **nenhum dos dois define `tlb_migrate_finish`** na versão fixada. Stage42 preserva a chamada do RT sob `#ifdef tlb_migrate_finish`, sem introduzir um stub ou exigir um hook arquitetural não disponível. A ferramenta verifica as duas fontes de cabeçalho originais e se recusa a aplicar o tratamento quando o contrato arquitetural diverge.

`tools/exp76-rt-stage42-hotplug-tlb.py` faz todas as verificações antes de modificar dois arquivos do kernel; `tests/test_exp76_stage42_hotplug_tlb.py` inclui nove cenários de verificação/aplicação, falta de checagem da pinagem, hook TLB divergente, despertar upstream ausente, stopper ausente, reaplicação, contagem errada de rejeitos e regressões específicas para protocolo RT preexistente completo ou parcial. `stage42-status.json` é retransmitido à CI isolada. Nenhum artefato de boot ou imagem é criado.

**Aviso técnico:** a compilação Clang 21 de `core.o` e `cpu.o`, as invariantes de concorrência durante `migrate_enable`, `set_cpus_allowed_ptr`, CPU hotplug e uso de stopper ainda precisam de validação. As 64 rejeições do patch PREEMPT_RT e o link integral permanecem pendentes. `EXP76_STAGE42_SOURCE=COMMITTED`; `EXP76_STAGE42_CI=UNVERIFIED`; `EXP75_PERMANENT=PRESERVED`; `KERNEL_BUILT=false`; `FLASH_READY=false`.

## Stage43 — corrigir os pontos de chamada de `cpu_nr_pinned` no validador Stage42

**Falha confirmada:** execução Clang21 `41464488427`, SHA `7ca48b42b8750596dcf127e4603cdb1ffc0c3316`. O job `clang21-object-diagnostic` falhou na etapa `Validate object-only diagnostic scripts`, antes de instalar o compilador e antes do teste da árvore real. A exceção originou-se de `tests/test_exp76_stage42_hotplug_tlb.py` na asserção `kept.returncode == 0`: a ferramenta `tools/exp76-rt-stage42-hotplug-tlb.py` recusou o fixture upstream com `ValueError: Both original CPU pin consumers must remain`.

**Causa:** o script Stage42 exigia uma contagem invariável de duas ocorrências de `cpu_nr_pinned(cpu)`, mesmo quando o protocolo de hotplug ainda não fora adicionado. O hunk oficial de `kernel/cpu.c` no overlay RT efetivamente possui **duas chamadas**: `if (cpu_nr_pinned(cpu)) return -EAGAIN` na `take_cpu_down()`, e `nr_pinned = cpu_nr_pinned(cpu)` no laço de espera de `takedown_cpu()`. O fixture antigo criava uma chamada fictícia em `unused()` para satisfazer a contagem e, ao acrescentar o laço upstream, passava a conter **três ocorrências**, violando o próprio gate.

**Correção Stage43:** o script agora ancora `if (cpu_nr_pinned(cpu))` exatamente uma vez e diferencia as duas situações:
- **Antes do protocolo:** exige uma ocorrência de `cpu_nr_pinned(cpu)` (somente a verificação do stopper), valida âncoras E404 e insere o protocolo de espera e reentrada.
- **Protocolo upstream já aplicado:** exige duas ocorrências e uma ocorrência exata da atribuição `nr_pinned = cpu_nr_pinned(cpu);`, além do teste `if (nr_pinned == 0)`, da transição de estado, do label de repetição, do retorno `-EAGAIN` e das duas limpezas de `takedown_cpu_task`. Não altera a fonte se ela já corresponde ao protocolo completo.
- **Parcial ou inesperado:** falha antes de escrever, sem aceitar chamada artificial extra ou ausência de polling.

`tests/test_exp76_stage42_hotplug_tlb.py` remove a falsa função `unused()`, passa a representar o laço original `if (nr_pinned == 0)` e acrescenta casos de terceira chamada inesperada e leitura de contador ausente. O teste anuncia `EXP76_STAGE43_HOTPLUG_PIN_CALL_SITES_REGRESSIONS=11_PASS` quando executado com sucesso. O workflow Clang21 está rotulado para Stage43, preservando o `stage42-status.json` (pois a integração funcional original permanece a mesma) e o relay de evidências.

**Próximo gate técnico:** a CI Stage43 precisa concluir os testes e a auditoria da árvore real, para então compilar `kernel/sched/core.o` e `kernel/cpu.o` com Clang 21. A correção do teste não prova hotplug, migração, CPU offlining ou link de kernel. Os 64 rejeitos RT permanecem. `EXP75_PERMANENT=PRESERVED`; `KERNEL_BUILT=false`; `FLASH_READY=false`.

## Stage44 — escopo correto do protocolo RT em `takedown_cpu`

**Evidência confirmada:** na fonte E404 fixada `kernel/cpu.c` (commit `fed88a6024cd4d46c52eda607a95d97d7371ba81`), a âncora textual `irq_lock_sparse();` seguida de uma linha em branco ocorre **duas vezes**, nos caminhos de `bringup_cpu()` (linha 529) e `takedown_cpu()` (linha 920). O validador Stage42, mantido em Stage43, exigia incorretamente uma ocorrência única no arquivo inteiro e a substituição subsequente agia na primeira ocorrência, que é a de bringup. Isso impediria a auditoria da árvore real mesmo após a correção do fixture Stage43, e poderia posicionar a espera de tarefas pinadas na função errada caso a cardinalidade mudasse.

**Correção Stage44:** `tools/exp76-rt-stage42-hotplug-tlb.py` separa a fonte no único marcador `static int takedown_cpu(unsigned int cpu)` antes de validar a âncora de `irq_lock_sparse()`. O bloco `HOTPLUG_RT_WAIT` passa a ser inserido exclusivamente na parte após essa função. A parte anterior do arquivo, incluindo `bringup_cpu()`, é preservada byte a byte. A compatibilidade com hotplug RT integralmente aplicado continua intacta e segue rejeitando aplicações parciais ou duplicações.

`tests/test_exp76_stage42_hotplug_tlb.py` foi estendido para criar dois locais de `irq_lock_sparse()` no fixture, confirmar que a espera só aparece depois de `takedown_cpu`, preservar o primeiro local inclusive no caso de RT upstream preexistente, e falhar se surgir uma segunda âncora no trecho-alvo. Quando executar corretamente, imprime `EXP76_STAGE44_SCOPED_HOTPLUG_REGRESSIONS=12_PASS`. O workflow de diagnóstico é rotulado como Stage44, mantendo o manifesto de origem `stage42-status.json`.

**Estado:** a última CI publicada na branch de evidências ainda é `41464488427`, que falhou no fixture Stage42. A Stage43 e a Stage44 precisam confirmar execução na CI; a correção de escopo foi verificada textualmente na E404 mas não constitui evidência de compilação. O último conjunto de objetos válido anterior ao port de migração permanece 11/12; a CI Stage41 falhou em `core.o`, e `cpu.o` nem foi tentado. Persistem 64 rejeitos do patch RT, e o kernel completo continua não compilado.

`EXP76_STAGE44_SOURCE=COMMITTED`; `EXP76_STAGE44_CI=UNVERIFIED`; `EXP75_PERMANENT=PRESERVED`; `KERNEL_BUILT=false`; `FLASH_READY=false`.

### Evidência Stage43 obtida durante o port Stage44

Execução `41466506172`, commit `0ab9f979e57c5a07b309d56004a140167d5e3c95`: a etapa de teste `Validate object-only diagnostic scripts` passou, incluindo `EXP76_STAGE43_HOTPLUG_PIN_CALL_SITES_REGRESSIONS=11_PASS`. A auditoria real passou pelo Stage41 e falhou precisamente em `tools/exp76-rt-stage42-hotplug-tlb.py:124`:

```text
ValueError: kernel/cpu.c: expected one '\tirq_lock_sparse();\n\n', found 2
```

Essa observação confirma que a correção Stage44 aborda o erro real da Stage43, e não apenas um risco hipotético. O Stage44 ainda depende de seu próprio job Clang21 para provar o port de hotplug. Nenhuma compilação de objetos adicionais foi realizada no Stage43 porque a auditoria interrompeu a preparação. `KERNEL_BUILT=false`; `FLASH_READY=false`.

## Stage45 — limite real de função para todas as alterações RT em CPU hotplug

**Motivo:** Stage44 restringia a inserção de `HOTPLUG_RT_WAIT` ao texto após a assinatura de `takedown_cpu()`, mas o trecho após a assinatura contém também outras funções de `kernel/cpu.c`. Além disso, `STOP_CALL`, `FAIL_ANCHOR` e `SUCCESS_ANCHOR` ainda eram substituídos no arquivo completo. Esse método permitia aplicar acidentalmente um hunk em outra função se as âncoras mudassem durante o port.

**Correção Stage45:** `tools/exp76-rt-stage42-hotplug-tlb.py` exige o início `static int takedown_cpu(unsigned int cpu)` e o limite seguinte da E404 fixada, `static void cpuhp_complete_idle_dead(void *arg)`. Divide a fonte em prefixo, corpo de `takedown_cpu()` e sufixo. Valida e altera `irq_lock_sparse`, `stop_machine_cpuslocked`, o tratamento de erro e a saída normal **somente no corpo da função**. Preserva prefixo e sufixo literalmente, exceto pela declaração global RT inserida de propósito imediatamente antes de `takedown_cpu()`. Quando o protocolo RT já está aplicado, também valida os marcadores de espera, polling, retorno, `-EAGAIN`, limpeza e label no recorte delimitado, sem alterar a fonte original.

Os testes `tests/test_exp76_stage42_hotplug_tlb.py` recebem um `cpuhp_complete_idle_dead()` sintético após o `takedown_cpu()`. Cobrem inserção sob duas chamadas legítimas de `irq_lock_sparse`, integridade do sufixo, protocolo upstream preexistente, âncora duplicada no corpo, uma função posterior com âncoras iguais e o stopper movido indevidamente para outra função. O marcador do teste passa a `EXP76_STAGE45_BOUNDED_HOTPLUG_REGRESSIONS=14_PASS`. A auditoria continua produzindo `stage42-status.json` com `bounded_takedown_function_scope_verified=true`; o workflow de diagnóstico foi rotulado como Stage45.

**Evidência atualizada:** a execução Clang21 `41468167035`, SHA `f3df27a047022edac8873c5f4f624ed514c6f952` (Stage44), terminou com `job_conclusion=success`: auditoria RT aplicada, `3/3` objetos iniciais PASS e `9/9` adicionais PASS, incluindo `kernel/sched/core.o` e `kernel/cpu.o`. O Stage45 adiciona exclusivamente o recorte estrutural de função à integração já compilada; sua própria CI permanece não verificada. Persistem 64 rejeitos RT. Nenhuma validação do kernel inteiro, link, concorrência, CPU offlining ou boot foi executada. `EXP75_PERMANENT=PRESERVED`; `KERNEL_BUILT=false`; `FLASH_READY=false`.

## Stage46 — ampliar o diagnóstico Clang21 do scheduler para RCU, IRQ, locking e workqueue

**Última CI confirmada:** Stage45, execução `41469980009`, SHA `9bd5a317c7099a0c7677b2db912bf48ef515f3b5`, `job_conclusion=success`. A auditoria Stage42 de hotplug está aplicada, os três objetos iniciais foram compilados e todos os nove objetos adicionais Stage30 compilaram. Portanto há **12/12 objetos isolados PASS**, ainda com **64 rejeitos do patch RT**. Isto não é um kernel completo nem prova link ou boot.

Stage46 acrescenta o diagnóstico isolado e obrigatório das seguintes **nove unidades adicionais**: `kernel/sched/wait.o`, `kernel/sched/swait.o`, `kernel/locking/mutex.o`, `kernel/locking/rwsem.o`, `kernel/locking/spinlock.o`, `kernel/rcu/update.o`, `kernel/rcu/tree.o`, `kernel/irq/manage.o` e `kernel/workqueue.o`. Todos os nove arquivos `.c` foram conferidos na árvore E404 fixada em `fed88a6024cd4d46c52eda607a95d97d7371ba81`, incluindo os respectivos Makefiles de locking, RCU e IRQ.

`tools/exp76-stage46-cross-subsystem-coverage.py` aceita somente esses nove alvos literais `.o` e sempre usa o Clang 21 fixado. O novo gate exige `PREEMPT_RT_FULL=y`, `asm-offsets.h`, exatamente 64 rejeitos e **todos** os 12 objetos anteriores realmente compilados, com exit code 0, e relatório Stage30 com os nove nomes esperados (não apenas um contador). Caso o gate anterior falhe, os novos objetos são explicitamente marcados como ignorados. Cada compilação recebe timeout individual de até 150 segundos, arquivo de log separado e diagnóstico limitado a 24 linhas, sem interromper a coleta dos demais erros.

A ferramenta recusa `vmlinux`, `Image`, `Image.gz`, `Image.gz-dtb` e `boot.img` antes e depois de compilar. **Não existe alvo de link em Stage46**. O novo arquivo `exp76-stage46-report/OBJECT_COVERAGE_CROSS_SUBSYSTEM.json` declara `link_performed=false`, `runtime_verified=false`, `kernel_built=false`, `flash_ready=false`. `tests/test_exp76_stage46_cross_subsystem.py` usa um binário fake de `make` restrito a `.o` para testar sucesso 9/9, interrupção pelo gate 12/12, erro proposital em `irq/manage.o`, rejeições ausentes, configuração RT inválida, imagem de kernel indevida, falta de fonte e alvos não permitidos.

A CI executa Stage46 após os diagnósticos Stage30 e antes de publicar resumo e artefatos, adicionando a pasta `exp76-stage46-report/` exclusivamente ao ZIP de diagnóstico. `tools/exp76-stage24-collect-ci-evidence.py` publica apenas a síntese limitada `cross_subsystem_coverage` no branch `exp76-ci-evidence`; o código-fonte e o branch EXP75 permanecem intocados.

**Limite:** os nove objetos extras ainda necessitam da sua própria execução Clang 21. Mesmo que haja 21/21 objetos PASS, serão apenas compilações individuais: ainda faltam a resolução dos 64 rejeitos, a validação completa de ABI e concorrência PREEMPT_RT, o link integral do `vmlinux`, os artefatos do dispositivo e o boot controlado. `EXP76_STAGE46_SOURCE=COMMITTED`; `EXP76_STAGE46_CI=UNVERIFIED`; `KERNEL_BUILT=false`; `FLASH_READY=false`.

## Stage47 — reparar fechamento RCU rejeitado e o lock do worker sob PREEMPT_RT

**Falha comprovada Stage46:** execução Clang21 `41472504082`, commit `cc59515fe4312de6632169bf971c234f230900d9`, job `success`. A auditoria preservou os 64 rejeitos e os 12 objetos anteriores passaram novamente. Dos nove objetos extras, `wait.o`, `swait.o`, `locking/spinlock.o` e `irq/manage.o` compilaram (4/9). Falharam `locking/mutex.o`, `locking/rwsem.o`, `rcu/tree.o`, `rcu/update.o` e `workqueue.o`.

**RCU:** `update.c:255` e `tree_plugin.h:1248` reportaram `unterminated conditional directive`. Os rejeitos oficiais E404/RT contêm exatamente o `+#endif` após `EXPORT_SYMBOL_GPL(rcu_read_lock_bh_held);` em `kernel/rcu/update.c.rej` e `+#endif /* #ifndef CONFIG_PREEMPT_RT_FULL */` após a implementação de `rcu_needs_cpu()` em `kernel/rcu/tree_plugin.h.rej`. Stage47 porta somente esses dois fechamentos. O port é condicionado a um parser de estruturas `#if/#elif/#else/#endif`: cada arquivo precisa ter exatamente um nível de condicional pendente identificável pelo ponto da falha, sem `#else` ou `#endif` órfãos, e **ambos precisam ficar totalmente balanceados** após a alteração. Se não corresponderem ao estado esperado, nenhuma fonte é escrita.

**Workqueue:** a fonte RT parcialmente aplicada utiliza `raw_spinlock_t` em `worker_pool.lock`, mas as linhas de `wq_worker_sleeping()` compiladas no Stage46 ainda chamavam `spin_lock_irq(&pool->lock)` e `spin_unlock_irq(&pool->lock)` (erro `-Werror,-Wincompatible-pointer-types`). `kernel/workqueue.c.rej` fornece o par exato `raw_spin_lock_irq`/`raw_spin_unlock_irq`. Stage47 converte **apenas esse par dentro do caminho `worker->sleeping`**, sem alterar outras ocorrências em `workqueue.c` nem mudar a política geral de locks.

O script `tools/exp76-rt-stage47-rcu-workqueue.py` exige as três fontes originais `.rej`, a contagem exata de 64 rejeitos, a ABI `raw_spinlock_t`, os contextos originais e o balanceamento de pré-processador. `--mode verify` não modifica fonte; `--mode apply` grava somente após todas as validações. Testes `tests/test_exp76_stage47_rcu_workqueue.py` exercitam aplicação, somente-verificação, condicionais inesperadas, rejeito alterado, lock de tipo incompatível, contexto perdido, rejeitos ausentes e segunda aplicação recusada. O manifesto `stage47-status.json` marca explicitamente os runtimes de RCU e workqueue como **não verificados**, bem como `kernel_built=false` e `flash_ready=false`.

**Próximos passos:** confirmar a auditoria real Stage47 e a compilação dos nove objetos cross-subsystem no Clang21. Os erros de `mutex.o` (gramática e `struct mutex.owner`) e `rwsem.o` (`owner`, `wait_list`, `m_count`) permanecem para portas RT específicas; nenhum stub, campo artificial ou redução de gate foi adicionado. Continuam 64 rejeitos RT, sem link de `vmlinux`, boot ou flash.

`EXP76_STAGE47_SOURCE=COMMITTED`; `EXP76_STAGE47_CI=UNVERIFIED`; `EXP75_PERMANENT=PRESERVED`; `KERNEL_BUILT=false`; `FLASH_READY=false`.
