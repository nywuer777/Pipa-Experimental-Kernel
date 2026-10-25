# EXP27.7 — Boot temporário EXP27.4: sucesso Android, RTL8153 aguardando teste físico

## Evidência material (PowerShell do operador)

O operador já havia validado o backup compacto stock e os candidatos EXP25A/EXP27.4 pelo hash. Nesta fase, executou `adb -s 6665d3e6 reboot bootloader` e obteve `fastboot devices` com dispositivo único `6665d3e6`, produto **pipa**, slot **b**, `unlocked=yes`, `is-userspace=no`.

O teste novo foi iniciado a partir do arquivo local previamente auditado:

```text
C:\platform-tools\EXP27.4-boot-prep\EXP27.4-RTL8153-NOT-FOR-FLASH.candidate.bin
SHA256 df9eb41441770035849e95a6e54ccc110357d5c171a06758cc2df60a192a01d7
32.411.648 bytes
```

Comando efetivamente executado: `fastboot -s 6665d3e6 boot <candidato EXP27.4>`. Resultado:

```text
Sending 'boot.img' (31652 KB) OKAY [ 1.383s]
Booting OKAY [ 0.242s]
Finished. Total time: 1.708s
```

O ADB inicialmente não encontrou dispositivo durante a fase fastboot/boot. Depois voltou a exibir:

```text
6665d3e6 device product:pipa model:23043RP34G device:pipa transport_id:3
sys.boot_completed=1
Linux version 4.19.404R (runner@runnervmtai0g) (Android (14054515, +pgo, +bolt, +lto, +mlgo, based on r563880c) Clang 21.0.0, LLD 21.0.0) #1 SMP PREEMPT Sun Oct 25 01:59:48 UTC 2026
boot_id=69d5b0dd-2a6e-4ea7-9eb4-de1644952c81
```

O compilador e a assinatura temporal distinguem a nova compilação EXP27.1 da EXP25A de 19/10 (runner@runnervm8k3b6). **RESULTADO: EXP27_RUNTIME_BOOT=PASS**, Android funcional o suficiente para responder ADB. Não confundir com aprovação de ciclos de suspend, touchscreen ou hardware USB/PD.

## Driver USB e Ethernet: observado, porém não testado em hardware

A leitura `ls /sys/bus/usb/drivers` mostrou explicitamente **r8152** (além de cdc_ncm, cdc_ether e outros). A nova Image EXP27.1 foi auditada anteriormente com v1.10.11 incorporada ao kernel e símbolo driver linkado. Conclusão válida: o driver **r8152 está registrado no kernel EXP27 ativo**.

A leitura de `/sys/class/net` mostrou `dummy0 ip6_vti0 ip6tnl0 ip_vti0 lo p2p0 rmnet_ipa0 sit0 wifi-aware0 wlan0 wlan1`, sem interface eth*/usb*. O teste não mostrou `/sys/bus/usb/devices` nem VID:PID 0bda:8153 ou binding ao `r8152`; por isso **ainda não é possível afirmar que o adaptador esteja conectado ou falhou ao enumerar**. A interface Ethernet não apareceu no instante da leitura. O teste funcional do r8152 v1.10.11 requer conectar o RTL8153 ao hub USB-C em condição estável, conferir enumeração, binding de driver e então verificar link/carrier/rota; não deduzir funcionamento de `r8152` aparecer na lista de drivers.

## Próximo teste sem reiniciar, sem flash

Enquanto ADB USB estiver conectado, coletar somente informações do estado atual:

```powershell
$adb = "C:\platform-tools\adb.exe"
& $adb -s 6665d3e6 shell ls /sys/bus/usb/devices
& $adb -s 6665d3e6 shell ls -l /sys/bus/usb/drivers/r8152
& $adb -s 6665d3e6 shell ls /sys/class/net
```

Se o RTL8153 não estiver fisicamente conectado nessa configuração, é esperado não encontrar `eth0` nem binding. A única porta USB-C pode estar ocupada pela ligação ADB ao PC; **não desconectar cabo, hub, carregador nem alterar alimentação sem outro canal de diagnóstico/controle previamente funcional**. Usar ADB Wi-Fi já validado ou diagnóstico local no próprio Android/Termux somente quando esses meios estiverem realmente disponíveis. Mouse/touch UI funcional não foi confirmado após boot EXP27.4.

**Gates finais deste estágio:** `EXP27_REAL_BOOT=PASS`; `ANDROID_BOOT_COMPLETED=PASS`; `RTL8152_DRIVER_REGISTERED=PASS`; `RTL8153_DEVICE_ENUMERATION=NOT_TESTED`; `RTL8153_DRIVER_BIND=NOT_TESTED`; `ETH_LINK=NOT_TESTED`; `TOUCH_FUNCTIONAL=NOT_TESTED`; `PHYSICAL_RECOVERY=PENDING`; `NO_FLASH_PERFORMED_BY_REPORTED_COMMANDS=true`; `REPEAT_TEMP_BOOT_AUTHORIZED=false`; `FLASH_READY=false`.
