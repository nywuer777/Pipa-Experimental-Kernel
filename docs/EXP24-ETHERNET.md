# EXP24 — Ethernet USB integrado ao EXP06 (variante experimental; SEM FLASH)

**Data:** 18/10/2026 | Xiaomi Pad 6 pipa, Android 16/crDroid 16.0, E404 kernel 4.19.404R | `FLASH_READY=false`.

## Objetivo e evidência de entrada

O usuário forneceu o arquivo `ethernet.config`, SHA256 **`bb561eac2eaeb15157b396f7807c30793348b65e14cb4b0821e4a66d8ecc11b0`** (909 bytes), e pediu integrar suporte ao adaptador Ethernet USB-C intermitente ao nosso kernel EXP06 para teste real. **Arquivo fornecido é um fragmento de Kconfig**, não contém um driver-fonte novo. Cobre 22 opções declaradas `=y`.

Fonte kernel experimental:
- E404 `kvsnr113/xiaomi_sm8250_kernel_e404` commit fixado `fed88a6024cd4d46c52eda607a95d97d7371ba81`.
- Patch original EXP06 schedutil `2000→1500 µs`, Clang21 AOSP pin `b54cd2c8e9e0bb057aef3804d42d39c5ac4674c7`.
- O EXP06 **já foi iniciado temporariamente** e expôs `rate_limit_us=1500` em três políticas cpufreq, depois reboot normal retornou E404 a `2000`; não modificar essa base aprovada.
- `CONFIG_MODULES=n` na configuração pinada, por isso **drivers adicionais somente como integrados `=y`**, não módulos `.ko`.

## Comparação da entrada com a fonte real

Foi inspecionado o `arch/arm64/configs/vendor/pipa_defconfig`, `drivers/net/usb/Kconfig` e `drivers/net/usb/Makefile` no **commit E404 fixado**, via conexão GitHub.

Dos 22 símbolos: **21 reconhecidos/aplicáveis**; seis já `=y` no defconfig: `MII`, `USB_NET_DRIVERS`, `USB_USBNET`, `USB_NET_CDCETHER`, `USB_NET_CDC_NCM`, `USB_NET_CDC_SUBSET`. Os 15 restantes serão ativados e rigorosamente validados:

```text
CONFIG_VLAN_8021Q=y
CONFIG_USB_NET_CDC_EEM=y
CONFIG_USB_NET_RNDIS_HOST=y
CONFIG_USB_NET_AX8817X=y
CONFIG_USB_NET_AX88179_178A=y
CONFIG_USB_RTL8150=y
CONFIG_USB_RTL8152=y
CONFIG_USB_LAN78XX=y
CONFIG_USB_NET_SMSC75XX=y
CONFIG_USB_NET_SMSC95XX=y
CONFIG_USB_NET_DM9601=y
CONFIG_USB_NET_SR9700=y
CONFIG_USB_NET_MCS7830=y
CONFIG_USB_PEGASUS=y
CONFIG_USB_KAWETH=y
```

**Exceção explícita:** `CONFIG_USB_NET_AQC111` não é declarado em `drivers/net/usb/Kconfig` nem tem objeto/target em `drivers/net/usb/Makefile` na revisão fixada. Não é possível habilitar AQC111 por `=y` sem portar código-fonte apropriado e suas dependências. O processo EXP24 **não declara suporte AQC111** e **não aceita silenciosamente descarte de configurações**.

A base já possui infraestrutura USB host `CONFIG_USB=y`, `CONFIG_USB_DWC3=y`, rede USB (`USB_USBNET=y`) e PHYLIB. Isso não garante OTG, energia USB-C, DHCP/Android Ethernet HAL nem compatibilidade VID:PID com adaptador específico.

## Implementação material no repositório privado

- `configs/ethernet.config`: **anexo original preservado** com SHA256 fixado.
- `tools/exp24-apply-ethernet.py`: exige hash original do arquivo de entrada, permite 21 símbolos reconhecidos pelo Kconfig original; altera `pipa_defconfig` após preparação EXP06 e `out/.config` se já existente. Verificação pós-build **fail-closed**: cada um dos 21 símbolos `=y`, `CONFIG_MODULES=n`, `CONFIG_PIPA_EXP_SUGOV=y` e `CONFIG_PIPA_EXP_SUGOV_RATE_LIMIT_US=1500`. Se olddefconfig/kernel ignorar qualquer símbolo, job falha.
- `tests/test_exp24_ethernet.py`: autoteste de input pinned, aplicação idempotente, `=m` rejeitado, símbolo ausente e alteração do anexo detectados.
- `.github/workflows/exp24-ethernet-clang21-build.yml`: variante isolada baseada no workflow EXP06 original (mesmo fonte e compilador fixados), injeta Kconfig após prepare, compila ARM64 Image/dtb/dtbo.img, publica `Image`, `.config`, logs, checksums; **proíbe boot.img/vendor_boot.img** no job. EXP06 original preservado.

**Testes de implementação executados localmente pelo assistente:** leitura e SHA256 do anexo, inspeção direta da árvore E404 Kconfig/Makefile/defconfig via GitHub, `python -m py_compile`, testes sintéticos `EXP24 SYNTHETIC KCONFIG APPLY/VERIFY TESTS: PASS`. Isso comprova **integração de código e testes de configuração**, **não** compilação de todo kernel.

## CI atual (não mascarar falha)

GitHub Actions disparou automaticamente: [run #39171851569](https://github.com/nywuer777/Pipa-Experimental-Kernel/actions/runs/39171851569), `run_attempt=1` e `run_attempt=2`, ambas **failure** sem steps disponíveis no payload do job. Job original e rerun apresentaram `steps=0` e logs de job indisponíveis. **Isso não permite atribuir o erro a fonte, compilador, driver ou config; a hipótese provável é falha de provisionamento antes do build, mas a causa exata ainda não é comprovada**. Não declarar EXP24 `Image` gerado, artifact publicado ou `CONFIG_GATE=PASS_REAL` até Actions executar suas etapas e concluir. Workflow pode ser reexecutado no GitHub Actions quando runners disponíveis.

## Próximo gate: kernel compilado e candidato temporário

1. GitHub Actions aprovar compilação, `CONFIG_GATE=PASS` **com `.config` real**, `CONFIG_KSU=y`, schedutil 1500, 21 Ethernet `=y`; guardar `Image` SHA256 + tamanho + logs, artefato imutável.
2. Construir **novo boot compacto Android v3** do slot `_b` com `mkbootimg` AOSP offline (aumento do tamanho do Image muda offsets da ramdisk). Preservar header/cmdline/ramdisk do E404, validar por auditor independente e comparar com backups originais. **Não** substituir bytes cegamente no compacto EXP06.
3. Obter identidade física do adaptador USB-C (USB VID:PID) e driver correspondente, observando `/sys/bus/usb/devices` e `/sys/class/net` no E404 baseline. Isso evita atribuir falha à falta de driver quando a causa é cabo, OTG, energia USB, DHCP ou adaptador defeituoso.
4. Solicitar **nova autorização específica para uma única inicialização temporária da variante Ethernet**. A autorização anterior foi só para um EXP06 sem suporte Ethernet novo.
5. **Prova de driver carregado** após boot: `/proc/config.gz` (se disponível) com `CONFIG_USB_RTL8152=y` etc., identificação `VID:PID`, vínculo a driver em `/sys/bus/usb/drivers`, aparecimento de interface de rede `eth*` ou `usb*`, interface `UP`, aquisição IP/rota e tráfego reproduzível. Boot `/proc/version` identifica compilação, não prova periférico conectado. Apenas 'internet funcionou' **não é prova isolada** de execução do nosso kernel porque o E404 já tem suporte CDC parcial.
6. Reboot para retornar ao kernel E404 persistente e registrar reversibilidade. Não afirmar suporte 100% universal: a prova é específica do adaptador (VID/PID) e condições do teste.

## Estado

`EXP24_SOURCE_INTEGRATION=COMMITTED`; `EXP24_LOCAL_SYNTHETIC_TEST=PASS`; `EXP24_REAL_CI_BUILD=NOT_COMPLETED`; `EXP24_DEVICE_BOOT=NOT_TESTED`; `EXP24_USB_ADAPTER_BOUND=NOT_TESTED`; **`FLASH_READY=false`**. Nenhum flash, boot experimental EXP24 ou alteração no tablet foi realizado.

## Atualização: revisão do workflow e captura A/B (18/10/2026)

- EXP24 run inicial [#39171851569](https://github.com/nywuer777/Pipa-Experimental-Kernel/actions/runs/39171851569) falhou antes de executar steps (runner_id=0, steps=[]), e a tentativa 2 também. Outra execução EXP18 na mesma data falhou com o mesmo padrão. Sem evidência de falha do compilador ou dos drivers nessa execução.
- Workflow corrigido no commit `e2831a7b1b3cd6e539a7700032bfb1b3256af84b`: versão do Clang 21 era procurada incorretamente em `out/.config`; validação agora usa `exp06-clang-version.txt` produzido no próprio job.
- Nova execução [#39172615397](https://github.com/nywuer777/Pipa-Experimental-Kernel/actions/runs/39172615397) recebeu runner e confirmou: checkout PASS, testes sintéticos Ethernet PASS, verificação EXP01 PASS e instalação das dependências PASS. Última observação: aquisição Clang21 em execução; **não** atribuir aprovação de build ainda.
- Criado `tools/exp24-usb-ethernet-evidence.ps1` (PowerShell Windows; procedimento read-only; hardware não testado nesta sessão). Captura `VID:PID`, vinculação dos drivers em interfaces USB, interfaces de rede, endereço e rota IPv4, `/proc/version` e opções de configuração expostas.
- Protocolo de teste: executar primeiro no **E404 persistente**, com o adaptador conectado; em teste autorizado posterior, repetir no **EXP24 inicializado temporariamente** sob as mesmas condições; comparar VID:PID, driver vinculado e conectividade estável. Apenas conectividade, sozinha, não comprova driver novo nem kernel novo.
- Estado continua **`FLASH_READY=false`** até build real, .config resolvido, auditoria boot Android v3 e autorização específica.

## EXP24 build homologado em CI (18/10/2026, 22:43 UTC)

- GitHub Actions [#39172615397](https://github.com/nywuer777/Pipa-Experimental-Kernel/actions/runs/39172615397), workflow `exp24-ethernet-clang21-build.yml`: **SUCCESS** em todos os passos, com Clang Android 21.0.0 fixado, E404 commit fixado e KernelSU preservado.
- Log do build confirma: `EXP24 final resolved kernel .config: ALL 21 SUPPORTED CONFIG SYMBOLS = y; EXP06 SUGOV 1500 PRESERVED; MODULES DISABLED`; `EXP24 CONFIG_GATE=PASS`.
- `Image` SHA256 **`773b37133766cb6877937bc53c84b2d5ad0a94985ca754d88a685e7c00648da0`**.
- Artifact `pipa-exp24-ethernet-clang21-2` (ID 12152679061), 12.385.469 bytes ZIP, digest **`sha256:01b25af08fec6573258464ecae0bb6181794e35999d4358213980d66e97c2038`**, expira em 01/11/2026. O artifact contém evidências e a Image NÃO INSTALÁVEL diretamente.
- `tools/exp24-usb-ethernet-evidence.ps1` recebeu correção adicional em `854071e6239dab5e2ffcd22bb0b4ce7e2ecc45bb`: o Android nega leitura a `/proc/sys/kernel/osrelease` sob ADB shell; antes isso provocava `NativeCommandError` em Windows PowerShell. Agora o campo é opcional e seções de diagnóstico não interrompem a coleta por stderr. Requer baixar novamente o script para o Windows.
- **Não alterar o critério de segurança:** `FLASH_READY=false`. Próximo passo é coletar a referência E404 e auditar empacotamento Android boot v3 com backups para eventual inicialização temporária autorizada. O A/B do USB Ethernet no hardware ainda não foi realizado.

## Referência física E404 de 19:45:47 (18/10/2026)

Registro de exp24-usb-E404-20261018-194548.txt (coleta ADB Wi-Fi com USB-C ocupado):
- Interfaces USB 2-1:2.0 e 2-1:2.1 enumeradas sem symlinks de driver exibidos; isso não comprova qual adaptador é 2-1 antes do VID:PID.
- Nenhuma interface Ethernet em /sys/class/net; lo e wlan0 apareceram no ip; wlan0=192.168.1.105/24. A rota local mostrada usa wlan0.
- A identificação VID:PID saiu vazia; a identidade kernel falhou por sintaxe de shell. Logo, modelo do adaptador e razão da não vinculação ainda estão pendentes.
- ip reportou uma mensagem Permission denied, mas mostrou endereços; isso não comprova falha de kernel.

Correção no repositório: tools/exp24-usb-ethernet-evidence.ps1 v3, commit 312147c4bbbfaa1a5cf11a3b28a0fa1f436fa35b. Substitui comandos remotos com parênteses/regex/for por comandos ADB simples, enumeração dos nomes USB no PowerShell, leitura individual de VID:PID, classes de interface, symlinks de driver e dados de rede. Pendente reexecução no Windows; não declarada validação no hardware desta versão.

Próximo gate: capturar /sys/bus/usb/devices/2-1/{idVendor,idProduct} e descritores de interface, cruzar com drivers EXP24 presentes. Somente após auditoria do boot Android v3 considerar autorização de teste temporário. FLASH_READY=false.

## Premissa obrigatória: reconhecimento intermitente no E404

Observação direta informada pelo usuário (18/10/2026): **o E404 reconhece o adaptador Ethernet USB-C de forma INTERMITENTE**. Algumas conexões funcionam; em outras, não há sequer reconhecimento de dispositivo. Portanto, um teste isolado com adaptador não detectado NÃO comprova ausência de driver, nem um teste isolado com adaptador detectado na EXP24 comprova que os drivers novos causaram a melhora.

Protocolo A/B para comparação válida (somente após boot EXP24 temporário autorizado e auditado):
1. Identificar antes o adaptador pelo USB VID:PID/descritores quando for enumerado; registrar quando não houver enumeração. Não presumir que '2-1' identifica o adaptador em todas as tentativas.
2. Usar mesmo cabo, adaptador, hub, alimentação, porta, rede e condições semelhantes no E404 e na EXP24. Manter ADB Wi-Fi independente do Ethernet.
3. Repetir pelo menos 10 ciclos de desconectar/reconectar no E404, e 10 na EXP24, registrando a duração até enumerar e o resultado de cada tentativa; testes consecutivos podem ter dependências e não bastam para confiança estatística.
4. Classificar cada ciclo: A) sem evento/enumeração USB; B) USB enumerado com VID:PID, sem driver vinculado; C) driver vinculado e interface eth*/usb* criada; D) IP, rota e tráfego via interface Ethernet funcional; E) operação sustentada e recupera após reconexão.
5. Separar problema OTG/USB-C, energia, cabo/hub e enumeração USB da seleção do driver (binding), e esta da camada Android Ethernet/DHCP/roteamento. Drivers adicionais somente podem atuar quando o dispositivo enumera adequadamente; não garantem consertar uma falha física de enumeração.
6. Comparar taxas por fase e logs do kernel em cada sistema, junto de identidade da Image/EXP24 no boot. Só atribuir melhora ao novo kernel mediante diferença reproduzível e evidência técnica coerente, não pela conexão eventual.
7. Antes de qualquer teste EXP24, cumprir auditoria de boot v3, confirmar reversibilidade e obter autorização de inicialização temporária. FLASH_READY=false.

Registro original: o relatório E404 de 19:45 mostrou interfaces USB 2-1:2.0/2-1:2.1 sem driver, mas VID:PID ausente e nenhum Ethernet na rede; a intermitência impede afirmar que o resultado represente todas as tentativas.

## Evidência E404 V3 — 20:01:41 e bloqueio de identidade de kernel

Arquivo recebido: `exp24-usb-E404-20261018-200142.txt`, SHA256 `295c3c3fc8a26deb9ced03cb07ba9706a4dbe0d1ec37fd0616976aa2d519b2ed` (128 linhas; ADB Wi-Fi; device=pipa).

**USB:** `/sys/bus/usb/devices` listou apenas `usb1`, `usb2`, `1-0:1.0` e `2-0:1.0` (hubs-raiz). Nenhum dispositivo USB externo presente no instante da coleta. O caminho `2-1` que havia aparecido às 19:45 desapareceu; consultas posteriores de `/sys/bus/usb/devices/2-1/idVendor` e `idProduct` retornaram ENOENT. Sem VID:PID não se pode afirmar ainda que `2-1` era o adaptador Ethernet, mas há evidência objetiva de enumeração variável.

**Rede:** `/sys/class/net` não tinha `eth*`/`usb*`. `wlan0` tinha IPv4 `192.168.1.105/24` e a rota local registrada foi `192.168.1.0/24 dev wlan0`. `ip link show` falhou com `request send failed: Permission denied` (limitação de permissão, não diagnóstico de hardware). `dumpsys ethernet`: `Ethernet State: enabled`; filtro `(usb|eth)\d+`; `Tracking interfaces` vazio. O serviço Android está ativo, mas sem interface Ethernet registrada.

**Inconsistência de identidade CRÍTICA, não resolver por inferência:** `uname -r` devolveu **5.10.404R**, enquanto `/proc/version` reportou `Linux version 4.19.404R` e Clang 21, build #14 Sun Aug 23 2026. O kernel EXP24 foi construído com fonte E404 que se apresenta como 4.19.404R. Não confundir sucesso de CI com compatibilidade de boot. A divergência deve ser investigada antes de qualquer imagem de boot ou teste temporário. Não declarar qual das versões é verdadeira sem prova adicional independente; investigar alteração/mascaramento de versão, userspace e informações do kernel e sua configuração.

**Próximo teste:** repetir coleta v3 no instante em que o adaptador voltar a ser enumerado, capturando VID:PID e drivers. Coletar separadamente `/system/bin/toybox uname -r`, `uname -r`, `cat /proc/version`, `getprop ro.product.device` e, se possível em modo read-only, configuração `CONFIG_LOCALVERSION`/identidade do kernel. Manter relatórios A/B e 10 ciclos de conexão iguais em ambos. `FLASH_READY=false` até resolver compatibilidade, empacotamento v3 e autorização.

## E404: reenumeração USB observada após 20:01

Nova saída ADB Wi-Fi fornecida pelo usuário após relatório V3: lista `/sys/bus/usb/devices` voltou a conter `2-1`, `2-1:2.0` e `2-1:2.1` junto aos hubs-raiz. Nenhuma interface Ethernet foi listada em `/sys/class/net` (wlan0, wlan1 etc.; sem eth*/usb*). Portanto, o caminho 2-1 reapareceu sem reboot/atualização reportada, mas não há confirmação de que 2-1 seja o adaptador antes de capturar VID:PID; intermitência coerente com relato anterior.

`uname -r` => `5.10.404R` e `/system/bin/toybox uname -r` => `5.10.404R`; `/proc/version` => `Linux version 4.19.404R` usando Android Clang 21. Os dois comandos uname consultam essencialmente a mesma interface `uname(2)` e **não** constituem prova independente da versão 5.10. A divergência persiste e bloqueia qualquer inferência de compatibilidade do artefato EXP24 4.19 com o kernel/partições atualmente executados.

Próxima captura é imediata enquanto 2-1 existe: `adb shell cat /sys/bus/usb/devices/2-1/idVendor`, `/idProduct`, `/manufacturer`, `/product`; verificar links `/sys/bus/usb/devices/2-1:2.0/driver` e `2-1:2.1/driver`. Em paralelo, obter `zcat /proc/config.gz` e CONFIG_LOCALVERSION se legível. Continuar sem flash: `FLASH_READY=false`.

## E404: 2-1 enumerado, sysfs VID:PID protegido e interfaces sem driver

Nova coleta manual no PowerShell pelo usuário com `/sys/bus/usb/devices/2-1` presente: `cat` em `idVendor`, `idProduct`, `manufacturer` e `product` retorna **Permission denied** (EACCES), não `No such file or directory`. Logo, não é legítimo concluir ausência do adaptador nem driver específico com base nesta leitura bloqueada.

`ls -l /sys/bus/usb/devices/2-1:2.0/driver` e `.../2-1:2.1/driver` retornam **No such file or directory**: symlinks de driver não apresentados nas duas interfaces no momento da coleta. Isto é evidência de interface enumerada sem driver vinculado identificado, não confirmação de causa ou de compatibilidade do EXP24.

Próximo teste somente leitura e sem alterar SELinux/permissões: tentar `adb shell dumpsys usb` para identificar VID:PID via USB host manager; se insuficiente e root Magisk já autorizado, confirmar `adb shell su -c id` = uid=0 e então ler explicitamente `idVendor/idProduct` com `adb shell "su -c 'cat /sys/bus/usb/devices/2-1/idVendor'"` e análogo idProduct. O caminho 2-1 é efêmero: recapturar após reenumeração. Evitar `chmod`, `setenforce 0`, rebinding de drivers, flash ou alterações no tablet.

Comparar VID:PID com tabelas USB dos drivers habilitados (`rtl8152`, `ax88179_178a`, `cdc_ether`, `cdc_ncm` etc.) antes de atribuir a falha à configuração. Divergência uname=5.10.404R vs /proc/version=4.19.404R permanece bloqueio de compatibilidade; FLASH_READY=false.

## E404: KernelSU root confirmado; evento USB product=33107

Nova sessão PowerShell no Xiaomi Pad 6: `adb shell su -c id` retornou `uid=0(root) gid=0(root) context=u:r:ksu:s0`, comprovando que root KernelSU está disponível para consultas read-only.

`adb shell dumpsys usb | Select-String` mostrou repetidamente `product=33107` no `USB Event Log=UsbDeviceManager activity`, além de entradas `vendor_id=-1`, `product_id=-1` e `product_name=null` em outra parte da saída. **33107 decimal = 0x8153**; esse PID é característico do Realtek RTL8153, **mas ainda não está associado ao dispositivo conectado** porque o filtro removeu o contexto e não foi obtido VID.

A fonte E404 fixada `kvsnr113/xiaomi_sm8250_kernel_e404` commit `fed88a6024cd4d46c52eda607a95d97d7371ba81`, `drivers/net/usb/r8152.c`, contém `VENDOR_ID_REALTEK 0x0bda` e a entrada `REALTEK_USB_DEVICE(VENDOR_ID_REALTEK, 0x8153)`. Logo, caso o dispositivo seja `0bda:8153`, o driver habilitado na EXP24 `CONFIG_USB_RTL8152=y` é candidato coerente. Não declarar driver vinculado nem funcionalidade comprovada até teste em hardware.

Logo após a confirmação de root, as leituras privilegiadas `/sys/bus/usb/devices/2-1/idVendor`, `idProduct` e `product` retornaram `No such file or directory`, e não `Permission denied`: o USB `2-1` havia desaparecido mais uma vez entre comandos. Esse resultado não deve ser tratado como bloqueio SELinux. A intermitência já foi observada independentemente de root.

Próximos comandos de leitura: (a) `adb shell dumpsys usb | Select-String -Pattern 'product=33107' -Context 8,5` para verificar vendor e contexto; (b) `adb shell "su -c 'dmesg'" | Select-String -Pattern 'idVendor|idProduct|usb 2-1|r8152|rtl8153|usbnet' | Select-Object -Last 80` para eventos persistentes USB; (c) `adb shell "su -c 'zcat /proc/config.gz'"` filtrado no host para opções relacionadas e versão, se disponível. Não alterar sysfs, SELinux, boot ou driver binding.

Estado segue `FLASH_READY=false`, já que `uname -r=5.10.404R` difere de `/proc/version=4.19.404R`; solucionar identidade/compatibilidade antes de boot experimental.

## Identificação definitiva do adaptador: 0BDA:8153

**Evidência fornecida pelo usuário (18/10/2026):** `adb shell dumpsys usb | Select-String -Pattern 'product=33107' -Context 8,5` retornou diversas entradas de `host_manager.connections` com `device_address=/dev/bus/usb/002/002`, `/004`, `/005`, `/008`, `/009`, etc., `mode=0`, `manufacturer=3034`, `product=33107`; histórico com `num_connects=24` e entradas `mode=-1` intercaladas. O campo `manufacturer` no formato dumpsys USB AOSP é **o vendor ID numérico**, vindo de `UsbDeviceDescriptor.getVendorID()`; `product` vem de `getProductID()` (fonte oficial: https://android.googlesource.com/platform/frameworks/base/+/master/services/usb/java/com/android/server/usb/UsbHostManager.java).

Conversão verificável: `3034` decimal = `0x0BDA` (Realtek), `33107` = `0x8153` (Realtek RTL8153 Gigabit USB Ethernet). Portanto, o histórico USB identifica o adaptador (ao nível VID:PID), mesmo quando ele já desapareceu do sysfs. Observação: o histórico prova presença anterior em conexões; não comprova conexão atual, binding de driver, interface de rede ou estabilidade.

Conferência com o E404 fixado `fed88a6024cd4d46c52eda607a95d97d7371ba81`: `drivers/net/usb/r8152.c` define `VENDOR_ID_REALTEK 0x0bda` e contém `REALTEK_USB_DEVICE(VENDOR_ID_REALTEK, 0x8153)` na tabela `rtl8152_table`. O defconfig E404 tinha `# CONFIG_USB_RTL8152 is not set`; a imagem EXP24 gerada e verificada por CI contém `CONFIG_USB_RTL8152=y` integrado. **Agora existe correspondência exata entre VID:PID e driver incluído; o funcionamento em hardware segue NÃO TESTADO.**

Nova chamada `adb shell "su -c 'dmesg'" | Select-String -Pattern 'idVendor|idProduct|usb 2-1|r8152|rtl8153|usbnet|disconnect'` exibiu apenas duas mensagens `cnss-daemon` disconnect e duas `android_work ... USB_STATE=DISCONNECTED`; **não mostrou** eventos de driver USB Ethernet. Isso não apaga o histórico USB mostrado pelo Android: dmesg filtrado pode não ter logs relevantes; `USB_STATE` se refere ao estado USB do dispositivo e pode não refletir diretamente OTG host.

**Próximo gate:** capturar baseline do kernel E404 (`adb shell "su -c 'zcat /proc/config.gz'" | Select-String -Pattern 'CONFIG_USB_RTL8152|CONFIG_USB_NET_CDCETHER|CONFIG_USB_NET_CDC_NCM|CONFIG_MODULES|CONFIG_LOCALVERSION'`); confirmar binding de `/sys/bus/usb/devices/2-1:2.0/driver` e interface Ethernet nas janelas em que USB 0BDA:8153 reaparece. Permanecem 10 ciclos A/B, auditoria de boot v3, identidade divergente uname=5.10 / proc=4.19 e autorização específica para teste temporário. FLASH_READY=false.

## Correção de hipótese: configuração real do kernel E404 contém RTL8152=y

**Evidência direta de leitura privilegiada no tablet (18/10/2026):** `adb shell "su -c 'zcat /proc/config.gz'" | Select-String ...` retornou:

```text
CONFIG_LOCALVERSION="-perf"
CONFIG_LOCALVERSION_AUTO=y
CONFIG_MODULES_USE_ELF_RELA=y
CONFIG_MODULES=y
CONFIG_MODULES_TREE_LOOKUP=y
CONFIG_USB_RTL8152=y
CONFIG_USB_USBNET=y
CONFIG_USB_NET_CDCETHER=y
CONFIG_USB_NET_CDC_NCM=y
```

**CORREÇÃO OBRIGATÓRIA DA HIPÓTESE ANTERIOR:** para a configuração apresentada pelo kernel atualmente em execução, não é correto supor que falta `CONFIG_USB_RTL8152`. O suporte de compilação já consta como `=y`. Logo, a adição dessa opção na EXP24 **não é, por si só, uma correção demonstrada** para o adaptador `0BDA:8153`. Uma `=y` indica compilação na configuração reportada, mas não garante driver registrado, que fez probe bem-sucedido, vinculação, interface criada, DHCP ou estabilidade.

**INCOMPATIBILIDADE EXTRA IMPORTANTE:** o defconfig do E404 fixado no EXP24 informava `# CONFIG_MODULES is not set` e `# CONFIG_USB_RTL8152 is not set`, diferente do `/proc/config.gz` atual (`CONFIG_MODULES=y`, `CONFIG_USB_RTL8152=y`), além da divergência já conhecida entre `uname -r=5.10.404R` e `/proc/version=4.19.404R`. Não presumir que a árvore-fonte do EXP24 reproduz o kernel rodando no dispositivo, nem qual identidade é verdadeira sem auditar proveniência. Antes de qualquer `boot.img` ou `fastboot boot`, validar versão e compatibilidade real; **FLASH_READY=false**.

**Novo gate read-only no E404 (sem mexer em SELinux/driver/flash):**
1. `adb shell "su -c 'ls -ld /sys/bus/usb/drivers/r8152'"` para verificar registro do driver, e `adb shell "su -c 'ls -ld /sys/module/r8152'"` para investigar presença no sistema (ausência isolada desse segundo caminho não equivale a ausência de código).
2. `adb shell "su -c 'cat /proc/sys/kernel/osrelease'"` e `adb shell "su -c 'zcat /proc/config.gz'" | Select-String -Pattern 'CONFIG_IKCONFIG|CONFIG_LOCALVERSION|CONFIG_USB_RTL8152|CONFIG_MODULES'` para documentar identidade/configuração, reconhecendo que os artefatos podem ter diferenças por patch/mascaramento.
3. Quando `2-1` aparecer, capturar VID:PID root e symlinks `/sys/bus/usb/devices/2-1:2.0/driver`, `2-1:2.1/driver`; distinguir enumeração, bind e Ethernet funcional.
4. Comparar em 10 ciclos controlados após estabelecer kernel/boot compatível. Não atribuir melhora à habilitação do RTL8152 sem diferenças comprovadas.

**Estado:** CI EXP24 SUCCESS, hardware EXP24 NOT TESTED, runtime baseline possui RTL8152=y segundo /proc/config.gz, compatibilidade boot UNKNOWN, FLASH_READY=false.
