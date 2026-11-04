# EXP76 — PREEMPT_RT e consistência de uname (em desenvolvimento)

## Baseline imutável

- Hardware: Xiaomi Pad 6 (pipa), Android crDroid 16, slot B.
- EXP75 conhecido bom: branch `exp75-pie-restore-ci`, commit `9af9740d3534dbe2e87675866f114244cdd6a3e9`.
- EXP75 instalado permanentemente em `boot_b`: `fastboot flash boot_b` OKAY, boot Android `sys.boot_completed=1`, `/proc/version` com `runner@runnervm48cm3` e `4.19.404R`.
- Touch Novatek e RTL8153 comprovados no boot temporário; validação funcional após flash permanente ainda por completar.
- A imagem EXP75 usa `LDFLAGS_vmlinux += -pie`. A variante `-no-pie` não inicializou; **não alterar esse linker sem ensaio isolado**.
- Backup original `boot_b` preservado no computador do proprietário, nunca no GitHub.
- `FLASH_READY=false` para qualquer EXP76.

## Metas separadas

### RT — compatibilidade antes de integração

A última série oficial PREEMPT_RT publicada para Linux 4.19 é `patch-4.19.325-rt140.patch.xz`:
`https://cdn.kernel.org/pub/linux/kernel/projects/rt/4.19/patch-4.19.325-rt140.patch.xz`

SHA-256 do índice assinado do kernel.org:
`c79d3efb5daccc5a3f58d502189eadc7dd31a962215ca0a16fa8c3eb98cd88ce`.

Ela **não corresponde** exatamente à base E404 `4.19.404R` fixada em
`fed88a6024cd4d46c52eda607a95d97d7371ba81`. O audit CI obtém a fonte fixada, confere hash do arquivo oficial, verifica aplicação textual no E404 e em uma reconstrução parcial dos overlays EXP (EXP01/24/25A) e publica arquivos .rej. `git apply --check` / `--reject` não equivale a revisão semântica nem a build.

Antes de declarar RT integrado: resolver conflitos em sched/locking/irq/rcu/arm64/drivers, conferir KernelSU e overlays inline do workflow EXP75, aplicar `CONFIG_PREEMPT_RT_FULL=y`, compilar com o Clang21 fixado, verificar config final e executar testes de hardware reversíveis. Não reutilizar a imagem de baseline como se fosse RT.

### UnAME — discrepância por contexto

Depois do flash EXP75:
- `/proc/version` = Linux `4.19.404R` (`runner@runnervm48cm3`).
- `adb shell /system/bin/toybox uname -r` = `5.10.404R`.
- `adb shell su -c '/system/bin/toybox uname -r'` = `4.19.404R`.
- `adb shell su -c 'cat /proc/sys/kernel/osrelease'` = `4.19.404R`.

A origem do valor `5.10.404R` **não foi estabelecida**. Pode envolver namespaces ou interceptação condicional, mas não há evidência suficiente para atribuir a KernelSU/SUSFS. Não substituir `UTS_RELEASE` nem adulterar a ABI do kernel para esconder a divergência. O diagnóstico read-only `tools/exp76-uname-probe.ps1` compara os contextos e suas namespaces; só então propor correção independente e testável.

## Referência de latência EXP75

Sem PREEMPT_RT: `CONFIG_PREEMPT=y`, `CONFIG_HZ=250`, `CONFIG_HIGH_RES_TIMERS=y`.
Tracer `wakeup_rt`: máximo observado `4552 us`.
Ftrace sem overflow (`18467/18467` eventos):
`InputDispatcher`: média `12.3 us`, máximo `4478 us`, 8 eventos >=1 ms em 4446 pareados.
`kgsl-events`: média `6.1 us`, máximo `1110 us`, 1 evento >=1 ms em 4776 pareados.
Isso mede wakeup até execução sob instrumentação, não latência físico-toque ou pior caso absoluto. Meta de `100 us` é experimental e não garantida.

## Gates para promover EXP76

1. Port RT completo na árvore e compilação Clang21, sem regressão de DTB/DTBO e `-pie`.
2. Validação do `uname` root/não root, preservando as informações verdadeiras do kernel.
3. Build com `CONFIG_PREEMPT_RT_FULL=y` comprovado na `.config` final.
4. Candidato somente para `fastboot boot` após revisão de backup e recuperação.
5. Boot Android, Novatek/multitouch, suspend/resume, RTL8153+IPv4+ping e medição RT. Gravação permanente exigirá decisão nova, sem herdar autorização do EXP75.

**Situação desta primeira etapa: AUDIT_ONLY; RT_NOT_INTEGRATED; UNAME_NOT_FIXED; FLASH_READY=false.**
