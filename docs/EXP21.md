# EXP21 — Pré-validação de política AVB, versão de kernel e condições de recuperação

**Estado:** implementação do portão de evidências de runtime e de política de recuperação. `EXP20=PASS_REAL`; `FLASH_READY=false`. Data 18/10/2026.

## Estado homologado

- EXP12: 4/4 backups de partições do slot ativo `_b` verificados por SHA-256.
- EXP13.2: o `vbmeta_b.img` original apresenta `flags=3` (hashtree e verification disabled). Os descritores AVB de `boot` e `vendor_boot` são `MISMATCH` com os arquivos originais salvos, enquanto `dtbo` corresponde. Não inferir aceitação de qualquer candidato novo apenas a partir da flag sem comprovação do comportamento de boot.
- EXP13.3: `ro.boot.vbmeta.digest` corresponde ao SHA-256 do blob top-level `vbmeta_b.img[0:5184]`.
- EXP17: ferramenta oficial AOSP `mkbootimg` reproduziu os 32.206.848 bytes compactos originais, SHA-256 `202aaaf67fe5c0a963965c4e29f67866b509916e0bdff15dde38ef55b3d321e7`.
- EXP18.2: bootloader confirmou `product=pipa`, `current-slot=b`, `is-userspace=no`, `unlocked=yes`, `slot-count=2`.
- EXP18.3: retorno normal de Fastboot para Android `PASS`, mantendo slot `_b`. `uname -r` pode ser mascarado para UID2000, usar `/proc/version` também.
- EXP19: build offline AOSP do candidato EXP06 `PASS`, SHA-256 da imagem compacta `30065a39be707d836594da574be11b08c0228018ca91a681e1b122e6f0e6f60c`.
- EXP20: auditoria independente com **duas execuções reais idênticas** `PASS`; conferiu SHA256 do candidato, `Image` EXP06, bytes não-kernel sem alteração e digest virtual de partição inteira `c50a7b4d8447426331adbfae9296439a957069c0860a1d36d476b63aae083f00`.

## Objetivo da EXP21

Separar **compatibilidade estática** (EXP20 comprovou) de **política real de inicialização, KernelSU e rollback**. Nenhuma etapa dessa fase escreve no Android ou modifica a imagem candidata.

### 1. Runtime do Android — consultas somente leitura

O usuário pode executar com Android inicializado e ADB autorizado:

```powershell
$adb = "C:\platform-tools\adb.exe"
& $adb devices -l
& $adb shell getprop ro.product.device
& $adb shell getprop ro.boot.slot_suffix
& $adb shell cat /proc/version
& $adb shell getprop ro.boot.verifiedbootstate
& $adb shell getprop ro.boot.vbmeta.device_state
& $adb shell getprop ro.boot.flash.locked
& $adb shell getprop ro.boot.veritymode
& $adb shell getprop ro.boot.vbmeta.digest
```

`/proc/version` é uma observação útil para reduzir ambiguidade de `uname`, mas ainda pode ser modificado por código do kernel. O conjunto de propriedades AVB reporta o **estado anunciado pelo firmware para o Android**, não fornece, isoladamente, a prova de políticas aplicadas no bootloader.

### 2. A/B e rollback — evidências ainda pendentes

Pelas especificações AOSP, alguns bootloaders expõem via `getvar` as variáveis `has-slot:boot`, `slot-successful:b`, `slot-unbootable:b` e `slot-retry-count:b` (o mesmo para `a`). Elas são **somente leitura**, mas requerem bootloader em Fastboot para consulta. Não é necessário entrar em Fastboot novamente para o primeiro passo desta fase. Valores não reconhecidos devem ser apresentados como `UNKNOWN`, nunca como `yes`/`no` presumidos.

Fontes: https://source.android.com/docs/core/ota/ab/ab_implement ; https://source.android.com/docs/core/architecture/bootloader/fastbootd

Não executar `fastboot --set-active`, `fastboot flash`, `fastboot boot` nem comandos OEM de desbloqueio. Teste de ciclo normal não prova retorno de um kernel quebrado: evitar qualquer instalação até plano de recuperação demonstrável.

### 3. KernelSU e árvore de dispositivo

KernelSU é uma integração com a configuração de kernel específica do projeto e não pode ser considerada funcional só porque o Android ADB está operacional. Kernel efetivo E404 4.19 (shell `uname` potencialmente mascarado como 5.10) requer validação específica de KernelSU fora do escopo de verificação estática do boot. Conferir versão/patches KernelSU no código-fonte congelado e a configuração do kernel EXP06, além de DTB do vendor_boot e DTBO já homologados. Fonte de suporte: https://kernelsu.org/guide/faq.html

## Condições de avanço para tentativa de boot

1. Estado do runtime/AVB documentado e ambiguidades reconhecidas.
2. Prova de origem e recuperação: backups + hashes + acesso ao bootloader + driver + slot mapping + estratégia de restauração segura.
3. Determinar se o bootloader suporta **boot temporário** e se é seguro nesse modelo **sem tentar o comando com a imagem experimental**; não presumir suporte ou reversibilidade.
4. Teste planejado para recuperação de softbrick independente da imagem candidata, e **autorização explícita da operação específica** antes de qualquer comando de boot/flash.

**`FLASH_READY=false` permanece.**
