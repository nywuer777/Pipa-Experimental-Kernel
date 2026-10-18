# EXP08 — contradição de identidade do kernel em tempo de execução

## Evidência obtida no Xiaomi Pad 6

Coleta anterior, no mesmo dispositivo informado como `pipa`:

```text
/proc/version:
Linux version 4.19.404R (build-user@build-host)
(Android (14054515, +pgo, +bolt, +lto, +mlgo, based on r563880c) clang version 21.0.0, LLD 21.0.0)
#14 SMP PREEMPT Sun Aug 23 09:16:08 UTC 2026
```

Coleta EXP08 posterior (18/10/2026):

```text
uname -a:
Linux localhost 5.10.404R #14 SMP PREEMPT Sun Aug 23 09:16:08 UTC 2026 aarch64 Toybox

cat /proc/modules:
cat: /proc/modules: No such file or directory

cat /proc/sys/kernel/modules_disabled:
cat: /proc/sys/kernel/modules_disabled: No such file or directory

ls -ld /sys/module:
drwxr-xr-x ... /sys/module
```

Também foi recebida anteriormente `/proc/config.gz`, cujo cabeçalho declara **Linux 4.19.113 / Clang 10.0.6**, apesar de `/proc/version` declarar **4.19.404R/Clang21**.

**Há três identidades de versão diferentes: 5.10.404R, 4.19.404R e 4.19.113.** A versão mostrada por `uname` precisa ser confrontada com `/proc/sys/kernel/osrelease` e com uma nova leitura de `/proc/version`, no **mesmo instante**.

## Conclusões permitidas

- O `uname -a` informado pelo usuário **não corresponde** à versão de `/proc/version` informada antes.
- Os campos idênticos da data e build `#14` tornam a diferença surpreendente, não a explicam.
- Ausência de `/proc/modules` e de `modules_disabled` é compatível com `CONFIG_MODULES=n`, mas não é prova conclusiva; deve ser investigada com outras fontes.
- `/sys/module` existe também para componentes built-in; não comprova que módulos carregáveis estejam habilitados.
- Kernel E404 `4.19.404R` compilado pela EXP06 **não está liberado para flash** quando `uname` indica 5.10.404R. `FLASH_READY=false`.
- Não concluir que o kernel realmente é 5.10 só porque uma consulta do `uname` indicou isso; tampouco afirmar que a linha antiga em `/proc/config.gz` é efetivamente a configuração em uso.

## Instrumentação read-only

Arquivo: `tools/exp08-runtime-identity.ps1`.

Usando ADB do Windows, obtém:
- `uname -r`;
- `/system/bin/toybox uname -r`;
- `cat /proc/sys/kernel/osrelease`;
- `cat /proc/version`;
- `uname -a`;
- `cat /proc/sys/kernel/version`;
- `getprop ro.boot.slot_suffix`;
- `getprop ro.product.device`.

Emite classificação como `RELEASE_SOURCES_AGREE`, `PROC_VERSION_MISMATCH`, `USERSPACE_UNAME_MISMATCH`, `UNAME_VS_PROC_OSRELEASE_MISMATCH`.

Execução (somente leitura, sem arquivo gerado):

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\platform-tools\exp08-runtime-identity.ps1"
```

Como alternativa sem download de script, os comandos diretos:

```powershell
C:\platform-tools\adb.exe shell uname -r
C:\platform-tools\adb.exe shell /system/bin/toybox uname -r
C:\platform-tools\adb.exe shell cat /proc/sys/kernel/osrelease
C:\platform-tools\adb.exe shell cat /proc/version
C:\platform-tools\adb.exe shell getprop ro.boot.slot_suffix
```

Não enviar serial, IMEI, imagens de partição ou logs privados para GitHub.

## CI

Execução EXP08 [#39139671436](https://github.com/nywuer777/Pipa-Experimental-Kernel/actions/runs/39139671436) **success**. Os testes no runner Windows PowerShell 5.1 / PowerShell 7 simulam casos concordantes e discordantes e confirmam que o script não contém comandos de flash. Isso **não substitui** verificação no tablet real.

## Portão

**`FLASH_READY=false`** até esclarecer qual kernel efetivamente roda, qual versão foi compilada na imagem `boot_b.img` e se a base de código-fonte 4.19.404R corresponde à identidade real, sem comprometer root e recuperação.
