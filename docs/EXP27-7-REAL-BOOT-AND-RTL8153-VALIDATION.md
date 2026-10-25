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


## Hardware real no Termux — RTL8153 detectado, vinculado e link 1 Gbps

**Evidência do operador no Termux, kernel EXP27 ativo (Sun Oct 25 01:59:48 UTC 2026, Clang 21, runner@runnervmtai0g).** Foi executado comando `su -c` de consulta ao sysfs e `/proc/version`. Embora a colagem do comando no terminal tenha exibido fragmentos truncados na linha de entrada, a **saída efetiva** apresentou as seções esperadas e os dados abaixo:

```text
R8152_REGISTRADO=SIM
RTL8153_ENCONTRADO=SIM
USB_DEVICE=2-1
VID_PID=0bda:8153
USB_SPEED=5000
CONFIG=1
INTERFACE=2-1:1.0 DRIVER=r8152

INTERFACE=eth0
CARRIER=1
LINK_SPEED=1000
DRIVER=r8152
```

O painel também enumerou outras interfaces: `wlan0 CARRIER=0`, `dummy0 CARRIER=1` e interfaces de rede virtuais. A **evidência determinante** para USB Ethernet foi `eth0` associada a `r8152`, não os dados de interfaces virtuais.

**Interpretação comprovada em hardware:**
- `USB_SPEED=5000`: enumeração SuperSpeed USB 3.x, velocidade negociada do barramento USB (em Mb/s).
- `VID_PID=0bda:8153` com interface `2-1:1.0 DRIVER=r8152`: dispositivo Realtek RTL8153 está presente e bound ao driver correto.
- `eth0 CARRIER=1`, `LINK_SPEED=1000`: camada física Ethernet detecta portadora e negociação de link a 1000 Mb/s. Não é benchmark de banda IP.
- `CONFIG=1`: configuração USB ativa nesta sessão; em provas antigas E404 surgia config 2, mas não se atribui diferença a bug/fix sem estudo da enumeração.

**Resultado atual:** `EXP27_REAL_BOOT=PASS`; `RTL8153_ENUMERATION=PASS`; `RTL8153_DRIVER_BIND=PASS`; `ETH_INTERFACE=eth0`; `ETH_CARRIER=PASS`; `ETH_NEGOTIATED_LINK_1000MBPS=PASS`.

**Ainda não verificado:** DHCP/IP em `eth0`, rota de saída via Ethernet, tráfego real, desempenho, link após suspensão/retomada, estabilidade longa, comportamento USB-C/PD e touchscreen/mouse funcional nesta sessão. Em evidência histórica, EXP25A já apresentou Ethernet estável após troca de carregador, portanto o sucesso atual **não prova sozinho que v1.10.11 resolveu falha de alimentação ou superou v1.09.9**.

**Próximo teste seguro pelo Termux:** consulta somente leitura a `ip -4 addr show dev eth0`, `ip route` e counters de `/sys/class/net/eth0/statistics/rx_bytes` / `tx_bytes` em dois instantes sem gerar tráfego. Não trocar cabo/hub, carregador, fazer reset USB nem boot. `ETH_IP_VALIDATED=PENDING`; `ETH_TRAFFIC_VALIDATED=PENDING`; `SUSPEND_STABILITY=PENDING`; `TEMP_BOOT_REPEAT_AUTHORIZED=false`; `FLASH_READY=false`.


## Termux real — eth0 com IPv4, link ativo e contadores de tráfego

O operador executou no Termux, em EXP27.1 com driver r8152 associado ao Realtek RTL8153, a leitura `su -c '/system/bin/ip -4 addr show dev eth0; /system/bin/ip -4 route show; cat /sys/class/net/eth0/statistics/rx_bytes; cat /sys/class/net/eth0/statistics/tx_bytes'`. Saída registrada:

```text
13: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc fq_codel state UP group default qlen 1000
    inet 192.168.1.102/24 brd 192.168.1.255 scope global eth0
       valid_lft forever preferred_lft forever
192.168.1.0/24 dev eth0 proto kernel scope link src 192.168.1.102
8686471
2182563
```

**Confirmações de hardware/rede:** interface Ethernet administrativamente ativa, camada física LOWER_UP, IPv4 `192.168.1.102/24` atribuída, rota local `192.168.1.0/24` disponível, contadores acumulados RX=8.686.471 bytes e TX=2.182.563 bytes. O mecanismo de atribuição do IPv4 (DHCP versus estático) não foi verificado; não afirmar que é DHCP. Não afirmar benchmark nem tráfego em tempo real apenas por valores acumulados.

**Limite do roteamento:** `ip -4 route show` não mostrou rota default na tabela principal; Android pode empregar regras/tabelas de roteamento personalizadas. Não concluir falta de internet sem `ip -4 route show table all` e `ip -4 rule show`, mais tentativa explícita de tráfego vinculada a `eth0`. Teste de conectividade IPv4 real permanece pendente; ping pode ser filtrado na rede. Não usar Wi-Fi móvel como evidência de tráfego Ethernet.

**Estado atualizado:** `RTL8153_USB3=PASS`; `RTL8153_BIND_R8152=PASS`; `ETH_LINK_1000=PASS`; `ETH_IPV4=PASS`; `ETH_RX_TX_COUNTERS_NONZERO=PASS`; `ETH_INTERNET_REACHABILITY=NOT_TESTED`; `ETH_STABILITY_LONG_RUN=NOT_TESTED`; `FLASH_READY=false`.


## EXP27.7 — Conectividade IPv4 externa real via eth0: PASS

**Evidência direta do operador via Termux/root na sessão EXP27 inicializada**, sem alteração de hub ou driver. Comando read-only `ip -4 route show table all`, `ip -4 rule show` e teste ICMP delimitado `ping -I eth0 -c 4 -W 2 1.1.1.1`.

### Roteamento efetivo do Android

```text
default via 192.168.1.254 dev eth0 table eth0 proto static
192.168.1.0/24 dev eth0 table eth0 proto static scope link
192.168.1.0/24 dev eth0 proto kernel scope link src 192.168.1.102
```

A consulta completa mostrou regras de policy routing Android (`fwmark`, UID e tabela `eth0`) e também uma rota `default dev dummy0 table dummy0`. A rota default de `eth0` existe **na tabela nomeada eth0**, apesar de não aparecer em consulta anterior restrita à tabela principal. Não confundir policy routes com perda de gateway. O resultado do ICMP explicitamente limitado a `eth0` confirma o caminho de saída.

### ICMP real externo, com interface Ethernet forçada

```text
PING 1.1.1.1 (1.1.1.1) from 192.168.1.102 eth0: 56(84) bytes of data.
64 bytes from 1.1.1.1: icmp_seq=1 ttl=57 time=2.98 ms
64 bytes from 1.1.1.1: icmp_seq=2 ttl=57 time=3.03 ms
64 bytes from 1.1.1.1: icmp_seq=3 ttl=57 time=3.24 ms
64 bytes from 1.1.1.1: icmp_seq=4 ttl=57 time=3.19 ms

4 packets transmitted, 4 received, 0% packet loss
rtt min/avg/max/mdev = 2.981/3.110/3.240/0.121 ms
```

**Resultado:** `RTL8153_EXTERNAL_IPV4_REACHABILITY=PASS`, `ETH0_POLICY_DEFAULT_ROUTE=PASS`, `ICMP_PACKET_LOSS=0% (4/4)`, latência média 3.110ms. Trata-se de quatro pacotes ICMP em ~3 segundos, **não** medição de throughput ou prova de estabilidade longitudinal. A velocidade Ethernet 1000 Mb/s reportada anteriormente é negociação física de link. O driver r8152 v1.10.11 está funcional na amostra, mas não há experimento A/B controlado separando a melhoria de driver da mudança de carregador USB-C/PD registrada historicamente.

**Próxima fase mínima:** teste curto de continuidade da ligação com pings baixos via eth0 e contadores de rede antes/depois, sem reiniciar, trocar alimentação, forçar suspend ou alterar sysfs. `EXP27_BOOT=PASS`; `RTL8153_USB_BIND=PASS`; `ETH0_GIGABIT_LINK=PASS`; `ETH0_IPV4=PASS`; `ETH0_EXTERNAL_ICMP=PASS`; `USB_PD_LONG_TERM_STABILITY=PENDING`; `EXP27_BENCHMARK=PENDING`; `FLASH_READY=false`.


## EXP27.7 — Teste contínuo curto (20 ICMP + contadores de erros): PASS

O operador executou no Termux root, com EXP27 ativo e `eth0` vinculada ao Realtek RTL8153 via `r8152`:

```sh
for f in rx_errors tx_errors rx_dropped tx_dropped; do
  cat /sys/class/net/eth0/statistics/$f
done
ping -I eth0 -c 20 -i 1 -W 2 1.1.1.1
for f in rx_errors tx_errors rx_dropped tx_dropped; do
  cat /sys/class/net/eth0/statistics/$f
done
```

**Evidência fornecida pelo operador:**

```text
ERROS ANTES:
rx_errors=0
tx_errors=0
rx_dropped=0
tx_dropped=0

PING 1.1.1.1 from 192.168.1.102 eth0:
20 packets transmitted, 20 received, 0% packet loss, time 19020ms
rtt min/avg/max/mdev = 2.846/3.362/4.235/0.332 ms

ERROS DEPOIS:
rx_errors=0
tx_errors=0
rx_dropped=0
tx_dropped=0
```

A saída individual trouxe todos os `icmp_seq=1..20`, nenhum ausente. Conclusão: **`ETH0_SHORT_CONTINUITY_20_PINGS=PASS`**, **`ETH0_RX_TX_ERRORS_DROPS_DELTA_ZERO=PASS`**. Resultado limitado a ~19 s, sem eventos de suspensão/retomada, troca de USB/PD ou desligamento. Contadores de erros zero antes/depois não demonstram desempenho de 1 Gbps nem estabilidade por dias, apenas ausência de erros visíveis nestes contadores ao longo da amostra.

**Marco atingido: funcionalidade básica EXP27.1 + RTL8153 / r8152 v1.10.11 HOMOLOGADA EM HARDWARE**, incluindo boot temporário Android, USB3 5000 Mb/s, driver bind, `eth0` 1000 Mb/s, IPv4, política de rota, internet ICMP 4/4 e teste de continuidade 20/20 sem perdas ou erros/drops.

**Pendentes (independentes deste marco):** throughput LAN medido com endpoint dedicado, estabilidade longa, controle/touch após suspend, confiabilidade USB-C/PD/reconexão, A/B driver antigo/novo controlado e recuperação operacional. Não gravar em partição e não induzir falhas agora. `FLASH_READY=false`.
