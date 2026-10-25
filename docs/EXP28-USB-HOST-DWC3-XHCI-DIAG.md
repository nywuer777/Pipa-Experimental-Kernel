# EXP28 — USB host do Xiaomi Pad 6 (DWC3/xHCI/PHY/Type-C/PD)

## Decisão de escopo

Com EXP27.7 homologada em tablet real — driver Ethernet `r8152 v1.10.11`, RTL8153 em USB3 5000 Mb/s, `eth0` 1000 Mb/s, IPv4, ICMP 20/20 sem perda e contadores de erros/drops zerados — **congelar a parte Ethernet e focar no subsistema USB do próprio pipa**. Não atribuir à versão r8152 a solução dos eventos históricos de hub/PD; o RTL8153 já havia retornado após trocar a fonte PD no kernel antigo.

Base de fonte relevante: repositório `kvsnr113/xiaomi_sm8250_kernel_e404`, commit pinado `fed88a6024cd4d46c52eda607a95d97d7371ba81`. O novo kernel EXP27 compila essa base com alterações identificadas; para avaliar o controlador ativo observar também o runtime atual.

## Evidência real do Termux EXP27

Drivers da plataforma presentes (nomes registrados, não necessariamente todos vinculados a dispositivos):

```text
dwc3
dwc3-of-simple
dwc3-qcom
msm-dwc3
msm-usb-hsphy
msm-usb-ssphy-qmp
qpnp-pdphy
usbpd-pm
xhci-hcd
```

`/sys/class/typec`: `port0 port0-partner`.

Valores reais coletados:

```text
/sys/class/typec/port0/data_role=[host] device
/sys/class/typec/port0/power_role=source [sink]
/sys/class/power_supply/usb/real_type=USB_PD
/sys/class/power_supply/usb/voltage_now=8260380
```

Significado: `[host]` é o papel de dados ativo e `[sink]` o de energia; funcionamento simultâneo host de dados e sink PD é coerente com hub de periféricos e carregador pass-through. Se a ABI `voltage_now` estiver em microvolts (convenção da power_supply e medições anteriores deste projeto), leitura equivale a **8,26038 V**; é uma amostra instantânea e não mede ripple/transientes nem tensão downstream.

Trecho `dmesg` final fornecido pelo operador mostra rotas físicas dentro do controlador `/devices/platform/soc/a600000.ssusb/a600000.dwc3/xhci-hcd.1.auto/usb1/1-1/`. Há novos registros `input` do teclado `1-1.4` e dongle/mouse `1-1.3` aproximadamente em tempos de uptime **2006, 2058, 2653, 2659 e 2662–2663 s**. Isso sugere múltiplos episódios de **registro/reenumeração HID**, mas linhas `input:` NÃO provam reset da porta/hub/root xHCI, nem evento Type-C/PD: o filtro anterior reuniu apenas as 40 últimas linhas que casavam com nomes e continha muitos registros HID, ocultando mensagens `usb disconnect/new USB device/reset` e linhas anteriores. Não concluir causa física ou defeito do controlador sem correlacionar eventos.

Não atribuir automaticamente cada registro HID a uma desconexão completa do barramento: alguns dispositivos compostos geram múltiplos nós input para um único attach.

## Código E404 identificado (auditoria read-only, sem patch)

- `drivers/usb/dwc3/dwc3-msm.c` (blob `27a810b25c9f0e0c1c2c5f7bb046805c6cf9ce6d`) integra host e gerenciamento de energia. Rotinas `dwc3_otg_start_host` (linha ~4324, inicializa host/regulador VBUS/xHCI), `dwc3_msm_prepare_suspend` (~2301), `dwc3_msm_suspend` (~2522), `dwc3_msm_resume` (~2738) e `dwc3_msm_pm_{suspend,resume}` (~4894,4925). O código já usa bloqueio de mutex para suspend/resume, teste de estado de LPM e callback de host notifier.
- `drivers/usb/dwc3/core.c` (blob `9e18b4ccbda2ffdd1c9f67a6b8e11c64a4e15360`) contém lógica genérica de DWC3 e resets de PHY.
- `drivers/usb/host/xhci-plat.c` (blob `94edbf487430570d382e7f0894911bad22e5df47`) contém glue xHCI platform.
- Vínculos exatos dos objetos sysfs `a600000.ssusb`, `a600000.dwc3` e `xhci-hcd.1.auto` ainda precisam ser confirmados por `readlink -f`, pois listar diretórios de drivers na plataforma não prova qual deles está associado.

**Gate para correção do driver:** capturar evento natural de desconexão/reconexão, diferenciar `usb 1-1*` periféricos, `usb 2-1*` SuperSpeed, hub versus root, `xhci` versus DWC3/PHY e eventos CC/PD. Priorizar alteração mínima no controlador realmente responsável, com testes de compilação/rollback e sem tocar em r8152. Não inventar um patch para PD, VBUS, regulador ou timer ainda sem prova da origem do churn.

## Único comando de coleta dirigido, somente leitura, no Termux

```sh
su -c '
echo "=== DRIVER VINCULADO AO HOST ==="
for d in /sys/devices/platform/soc/a600000.ssusb /sys/devices/platform/soc/a600000.ssusb/a600000.dwc3 /sys/devices/platform/soc/a600000.ssusb/a600000.dwc3/xhci-hcd.1.auto; do
  [ -d "$d" ] || continue
  echo "NODE=$d"
  readlink -f "$d/driver" 2>/dev/null || true
done
echo "=== EVENTOS REAIS USB, SEM LINHAS HID INPUT ==="
dmesg | grep -Ei "usb [12]-|usb usb[12]|xhci|dwc3|hub [12]-|disconnect|reset .*usb|new .*usb device|typec|vbus|over.current|error -71|error -110" | grep -Evi "input:|hid-generic" | tail -n 100
'
```

Não executar os seguintes comandos: `fastboot`, `reboot`, `unbind`, `bind`, `authorized=0`, `power/control` escrita, USB role switch, troca de carregador ou indução de desconexão. `USB_CONTROLLER_ROOT_CAUSE=NOT_CONFIRMED`; `EXP27_ETHERNET_KEEP=PASS`; `FLASH_READY=false`.
