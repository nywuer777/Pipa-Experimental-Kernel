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
