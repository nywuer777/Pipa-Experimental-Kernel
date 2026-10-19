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

## Investigação da divergência CONFIG_USB_RTL8152=y versus ausência de r8152 no sysfs

Nova evidência ADB com KernelSU root (`uid=0`, contexto `u:r:ksu:s0`):
- `adb shell "su -c 'ls -ld /sys/bus/usb/drivers/r8152'"` retornou `No such file or directory`.
- `adb shell "su -c 'ls -ld /sys/module/r8152'"` retornou `No such file or directory`. Essa segunda ausência, isoladamente, não comprova que um driver builtin inexista.
- `adb shell "su -c 'cat /proc/sys/kernel/osrelease'"` retornou **`4.19.404R`**; contrastar com `uname -r = 5.10.404R` e `/proc/version = Linux version 4.19.404R`. Uma discrepância de observáveis exige investigar mascaramento/customização de `uname`; não afirmar manipulação como fato até prova.
- Leitura anterior do `/proc/config.gz` via root declarou `CONFIG_USB_RTL8152=y`, `CONFIG_MODULES=y`, `CONFIG_LOCALVERSION="-perf"`. A coexistência de config=y com diretório USB `r8152` ausente é contraditória com registro normal esperado, mas **não prova** ausência do código, falha de init, motivo da desconexão USB nem correção EXP24.

Conferência da fonte E404 fixa (`fed88a6024cd4d46c52eda607a95d97d7371ba81`): `drivers/net/usb/Makefile` contém `obj-$(CONFIG_USB_RTL8152) += r8152.o`; `drivers/net/usb/r8152.c` define `MODULENAME "r8152"` e registra o driver USB via `module_usb_driver(rtl8152_driver)`. Portanto, `/sys/bus/usb/drivers/r8152` é caminho esperado quando o driver está registrado no barramento da revisão citada. A configuração de compilação por si só não demonstra que esse caminho exista em runtime.

Próximo gate sem alteração: enumerar `/sys/bus/usb/drivers` com root; consultar `/proc/modules` se houver modulo carregado, e opcionalmente procurar `r8152`/`rtl8152` nos símbolos do kernel (`/proc/kallsyms`, sujeito a permissões e restrições de segurança). Obter `CONFIG_IKCONFIG` e opções relacionadas de `/proc/config.gz`, e verificar `/proc/sys/kernel/osrelease` novamente. Se o adaptador `2-1` surgir, capturar binding de interfaces e `VID:PID`. Não forçar bind/probe, não alterar SELinux, não flashear.

CI EXP24 continua aprovado quanto a build e flags; capacidade de reparar RTL8153 intermitente não demonstrada. **FLASH_READY=false**, inclusive pela divergência da configuração da árvore usada versus kernel vivo.

## E404: enumeração dos drivers USB e procfs indisponível (20:30)

Saída fornecida pelo usuário em 18/10/2026 às ~20:30 (ADB via Wi-Fi; KernelSU root):
```text
cdc_ether
cdc_ncm
cdc_subset
hub
snd-usb-audio
uas
usb
usb-storage
usbfs
usbhid
xpad
cat: /proc/modules: No such file or directory
cat: /proc/kallsyms: No such file or directory
```

**Fato confirmado:** na visão atual de `/sys/bus/usb/drivers`, `r8152` NÃO está registrado (há `cdc_ether`, `cdc_ncm` e `cdc_subset`). Sob condições normais, `CONFIG_USB_RTL8152=y` e registro bem-sucedido via `module_usb_driver(rtl8152_driver)` deveriam tornar `r8152` visível nesse barramento. A ausência do registro não identifica ainda a causa. Os arquivos procfs `/proc/modules` e `/proc/kallsyms` não existem nessa visão nem com root; não concluir que os conteúdos reais seriam vazios, nem instalar/fazer insmod.

**Nova hipótese de auditoria:** há implementações de módulos KernelSU/SUSFS que oferecem *spoofing* de `uname`, ocultação de símbolos/módulos e redirecionamento de caminhos. Isto poderia explicar algumas discrepâncias (`uname 5.10.404R` versus `/proc/sys/kernel/osrelease` e `/proc/version` 4.19.404R; arquivos procfs indisponíveis), porém a presença de SUSFS **não foi confirmada** nem demonstraria, sozinha, a ausência de `r8152`. Referências públicas de contexto: https://github.com/sidex15/susfs4ksu-module (documentação de spoof de uname) e https://github.com/ahmed-alnassif/ReSuSFS (uname.txt, open_redirect.txt); não alterar flags nem módulos durante diagnóstico.

**Próximo procedimento somente leitura:**
1. Verificar indicação de SUSFS na configuração disponível: `adb shell "su -c 'zcat /proc/config.gz'" | Select-String -Pattern 'CONFIG_KSU_SUSFS|CONFIG_SUSFS|CONFIG_IKCONFIG|CONFIG_USB_RTL8152|CONFIG_MODULES'`. Não esperar que a ausência dessa opção exclua módulo userspace.
2. Enumerar somente nomes de módulos para suspeita de spoof: `adb shell "su -c 'ls -1 /data/adb/modules'" | Select-String -Pattern 'susfs|resusfs|uname|hide|root'`. Não ler segredos, não editar arquivos.
3. `adb shell "su -c 'ls -l /proc/modules /proc/kallsyms /proc/config.gz'"` e `adb shell "su -c 'ls -1 /sys/bus/usb/drivers'"` para confirmar a visão procfs/sysfs.
4. Coletar estado USB 0BDA:8153 durante enumeração com root, interfaces e binding, e, se possível, eventos do Android `dumpsys usb`, antes de uma proposta de patch específico.

**Não classificar CI da EXP24 como conserto comprovado.** O driver está previsto em build, mas a origem da configuração E404, da ausência do registro e da intermitência USB continuam sem demonstração causal. Boot v3/compatibilidade não liberado: **FLASH_READY=false**.

## Kernel E404 observado: IKCONFIG ativo, módulos procfs ausentes, sem evidência positiva SUSFS

**Evidência da coleta PowerShell do usuário em 18/10/2026:**
```text
CONFIG_IKCONFIG=y
CONFIG_IKCONFIG_PROC=y
CONFIG_MODULES_USE_ELF_RELA=y
CONFIG_MODULES=y
CONFIG_MODULES_TREE_LOOKUP=y
CONFIG_USB_RTL8152=y
ls: /proc/modules: No such file or directory
ls: /proc/kallsyms: No such file or directory
-r--r--r-- 1 root root 44819 ... /proc/config.gz
```
O filtro de configuração pesquisou `CONFIG_KSU_SUSFS|CONFIG_SUSFS|CONFIG_IKCONFIG|CONFIG_USB_RTL8152|CONFIG_MODULES` e não retornou opção SUSFS; busca por nomes `susfs|resusfs|uname|hide|root` em `/data/adb/modules` não retornou correspondências. **Não há evidência positiva de SUSFS nesta coleta.** Ausência desses termos também não prova que não haja outras customizações, nomes diferentes, ou hooks.

**Avaliação:** a configuração publicada via `IKCONFIG_PROC` indica explicitamente `CONFIG_USB_RTL8152=y` e `CONFIG_MODULES=y`. Apesar disso, o driver `r8152` não está registrado em `/sys/bus/usb/drivers`, e `/proc/modules` não existe na visão do shell root. Isso impede concluir se a configuração descreve fielmente o binário em execução e exige investigar visibilidade do procfs/sysfs, falha de registro initcall, e proveniência do kernel. `/proc/kallsyms` pode depender da opção CONFIG_KALLSYMS e de outras restrições; sua ausência sozinha não basta para inferir ocultação deliberada.

**Próximo diagnóstico limitado e read-only, executável em PowerShell:**
```powershell
.\adb.exe shell "su -c 'zcat /proc/config.gz'" | Select-String -Pattern 'CONFIG_KALLSYMS|CONFIG_PROC_FS|CONFIG_UTS_NS|CONFIG_USB_NET_DRIVERS|CONFIG_USB_RTL8152|CONFIG_LOCALVERSION|CONFIG_MODULES'
.\adb.exe shell "su -c 'cat /proc/1/mountinfo'" | Select-String -Pattern ' /proc |/proc/modules|/proc/kallsyms'
.\adb.exe shell "su -c 'ls -l /sys/bus/usb/drivers /sys/module'" | Select-String -Pattern 'r8152|cdc_ether|cdc_ncm|usbnet'
.\adb.exe shell "su -c 'cat /proc/sys/kernel/osrelease'"
```
Interpretar resultados como observações em um namespace/visão; não alterar flags de segurança, mountpoints ou serviços para testar. Até prova adicional, **nenhum novo experimento de boot/flash na EXP24** (`FLASH_READY=false`).

## E404: procfs hidepid=2 não explica sozinho a ausência de módulos/kallsyms

**Evidência recebida em 18/10/2026:**
```text
CONFIG_LOCALVERSION="-perf"
CONFIG_LOCALVERSION_AUTO=y
CONFIG_UTS_NS=y
CONFIG_KALLSYMS=y
CONFIG_KALLSYMS_ALL=y
CONFIG_KALLSYMS_BASE_RELATIVE=y
CONFIG_MODULES_USE_ELF_RELA=y
CONFIG_MODULES=y
CONFIG_MODULES_TREE_LOOKUP=y
CONFIG_USB_NET_DRIVERS=y
CONFIG_USB_RTL8152=y
CONFIG_PROC_FS=y
37 34 0:5 / /proc rw,noatime shared:4 - proc proc rw,gid=3009,hidepid=2
```

O filtro read-only do `dmesg` por `r8152|rtl8152|usbcore|registered new interface driver` não retornou linhas na janela consultada. O resultado vazio não prova que nunca houve registro nem descreve integralmente a inicialização do kernel; os eventos podem não constar no buffer atual.

**Interpretação verificada:** a opção procfs `hidepid=2` controla visibilidade/acesso aos diretórios `/proc/<pid>` de outros processos, e por si só **não deveria ocultar arquivos globais** `/proc/modules` e `/proc/kallsyms`. Referência: https://www.kernel.org/doc/html/latest/filesystems/proc.html#mount-options . As opções `CONFIG_KALLSYMS=y`, `CONFIG_MODULES=y`, `CONFIG_PROC_FS=y` declaradas em `/proc/config.gz` contrastam com os arquivos globais ausentes; possível customização/hide do ambiente ou divergência entre configuração e runtime, ainda não demonstrada. Não inferir SUSFS apenas destes dados.

**Estado técnico:** identificação `0BDA:8153` confirmada pelo histórico Android; o driver `r8152` não consta em `/sys/bus/usb/drivers`, mesmo que `/proc/config.gz` declare `CONFIG_USB_RTL8152=y`. Os drivers `cdc_ether`, `cdc_ncm`, `cdc_subset` estão registrados, mas não houve associação à interface `2-1:2.0`/`2-1:2.1` nas coletas. Kernel: `/proc/version` e `/proc/sys/kernel/osrelease` informam `4.19.404R`; `uname -r` informa `5.10.404R`; identidade/compatibilidade de boot NÃO RESOLVIDA.

**Gate seguinte sem escrita no tablet:** obter um snapshot atômico enquanto `2-1` reaparecer, incluindo leitura root de `idVendor/idProduct`, bInterfaceClass/subclass/protocol e symlinks dos drivers; se viável, registrar `dumpsys usb` host history num relatório e contexto de versão. Separar falha de enumeração, falha de bind e ausência de registro. Reavaliar apenas após evidência material se construir uma variante de diagnóstico; CI EXP24 bem-sucedido não prova correção em hardware. **FLASH_READY=false**.

## Identificação em tempo real de 0BDA:8153 sem binding de interface

Em coleta PowerShell via ADB com KernelSU root, o usuário executou 30 sondagens com intervalo de 800 ms e obteve:
```text
Dispositivo USB detectado: 0bda:8153
ls: /sys/bus/usb/devices/2-1:2.0/driver: No such file or directory
ls: /sys/bus/usb/devices/2-1:2.1/driver: No such file or directory
```

**Evidência agora direta (não apenas histórico de dumpsys):** o endereço temporário USB `2-1` era de fato o adaptador Realtek `0bda:8153` no instante da captura, e a sondagem subsequente não encontrou links `driver` em nenhuma de suas duas interfaces. Isso é uma falha de binding observada em hardware; como as leituras ocorreram em chamadas ADB sucessivas, preservar a possibilidade de o dispositivo desconectar entre as duas chamadas. O driver `r8152` estava ausente da enumeração independente de `/sys/bus/usb/drivers`, fortalecendo a interpretação, mas não estabelecendo sua causa.

**Verificação precisa no código E404 fixado:** `drivers/net/usb/r8152.c` contém a macro `REALTEK_USB_DEVICE(vend, prod)` com matching de VID:PID+classe `USB_CLASS_VENDOR_SPEC` ou VID:PID+classe `USB_CLASS_COMM`, subclasse `USB_CDC_SUBCLASS_ETHERNET`, protocolo `USB_CDC_PROTO_NONE`; tabela inclui `REALTEK_USB_DEVICE(VENDOR_ID_REALTEK, 0x8153)`. A enumeração apresentou interfaces `2-1:2.0`/`2-1:2.1`, mas ainda não coletamos `bInterfaceClass`, `bInterfaceSubClass`, `bInterfaceProtocol`, `bConfigurationValue` para separar modos e comportamentos USB.

**Próxima coleta de leitura e nenhuma escrita no dispositivo:** enquanto 2-1 estiver presente ler `bConfigurationValue`, `bNumConfigurations`, `speed`, `bInterfaceClass`, `bInterfaceSubClass`, `bInterfaceProtocol` para `2-1:2.0` e `2-1:2.1`. Revalidar os links de `driver` na mesma janela; se possível capturar sysfs em uma única chamada ADB para diminuir race. Interpretar valores hexadecimais: `ff` = vendor-specific; `02:06:00` = CDC Ethernet control; `0a` = CDC data interface (somente exemplo, não afirmar valor não observado).

**Prioridade de engenharia:** não diagnosticar 'driver ausente do código' apenas pelo sysfs porque `/proc/config.gz` informou `CONFIG_USB_RTL8152=y` e o código-fonte do EXP24 possui o driver. Investigar razão do driver não aparecer registrado na base E404 atual e a identidade discrepante `uname 5.10.404R` versus `/proc/sys/kernel/osrelease` e `/proc/version` 4.19.404R. Resultados de EXP24 CI continuam restritos a compilação e config gates; sem boot físico/flash. **FLASH_READY=false**.

## Falha na coleta de nove atributos: resultado inconclusivo

O usuário executou o script PowerShell que fazia 30 tentativas de coletar nove atributos sysfs USB em `2-1`, `2-1:2.0` e `2-1:2.1`. O script terminou com `Adaptador nao capturado nas 30 tentativas.`.

**NÃO interpretar como 30 amostras de ausência do adaptador.** A condição de sucesso anterior era `LASTEXITCODE=0` **e** exatamente nove linhas na saída do `cat` de nove arquivos. Qualquer arquivo ausente, permissão, transição de configuração USB ou desconexão no meio da leitura faz a tentativa inteira ser descartada, mesmo se VID:PID tenha sido lido. A contagem não diferencia falta de enumeração de atributos indisponíveis.

Próximo protocolo correto é amostrar somente `ls /sys/bus/usb/devices` para identificar a presença de `2-1` em cada ciclo; quando presente, ler VID, PID e nove atributos individualmente, preservar captura parcial e registrar symlinks de driver. Gerar no PC um arquivo de evidência, sem alterações no dispositivo. Não forçar binding, não mexer em SELinux, não instalar módulo e não flashear.

**Estado do experimento:** identificação `0BDA:8153` confirmada em tentativa anterior; driver `r8152` não registrado na lista de `/sys/bus/usb/drivers`, duas interfaces sem symlink em captura anterior; enumeração intermitente. O resultado da coleta rígida não altera essas conclusões. **FLASH_READY=false**.

## Diagnóstico da captura CDC ECM Realtek e blacklist explícita no E404

**Amostra física E404 às 20:53 (PowerShell exp24-rtl8153-observe.ps1):**
```text
Attempt 9/40 : USB 2-1 present
  VID=0bda PID=8153 Configuration=2
  Interface_2.0_Class=02 Subclass=06 Protocol=00
  Interface_2.1_Class=[unavailable, missing or disconnected]
  Driver_2-1:2.0=[no driver symlink or device disappeared]
Attempt 23/40 : USB 2-1 present
  VID=0bda PID=8153 Configuration=2
  Interface_2.0_Class=02 Subclass=06 Protocol=00
  Interface_2.1_Class=0a Subclass=00 Protocol=00
  Driver_2-1:2.0=[no driver symlink or device disappeared]
  Driver_2-1:2.1=[no driver symlink or device disappeared]
USB 2-1 observed in 2/40 scans. Complete capture: True
```

**Precisão da contagem:** o script v1 contém `if ($successCount -eq $fields.Count) { $complete = $true; break }` e a segunda captura completa ocorreu na tentativa **23**. Portanto, foram **2 aparições dentre 23 sondagens realmente executadas**, embora o log apresente denominador 40 (limite programado). Não tratar 2/40 como taxa experimental, nem presumir independência de observações. Como cada atributo era uma chamada ADB diferente, o desaparecimento entre leituras continua possível, especialmente na tentativa 9.

**Nova descoberta causal verificável diretamente na fonte E404 fixada** (repositório `kvsnr113/xiaomi_sm8250_kernel_e404` commit `fed88a6024cd4d46c52eda607a95d97d7371ba81`):
- Em `drivers/net/usb/cdc_ether.c`, a tabela `products[]` inclui, na seção BLACKLIST, `USB_DEVICE_AND_INTERFACE_INFO(REALTEK_VENDOR_ID, 0x8153, USB_CLASS_COMM, USB_CDC_SUBCLASS_ETHERNET, USB_CDC_PROTO_NONE)` com `.driver_info=0` (linhas ~757-762). Isso corresponde exatamente ao VID:PID `0BDA:8153` e classe/subclasse/protocolo `02/06/00` capturados na interface `2-1:2.0`.
- Em `drivers/net/usb/usbnet.c`, `usbnet_probe()` interpreta `prod->driver_info == 0` como blacklist, emite `blacklisted by %s` em nível debug e retorna `-ENODEV` (linhas ~1686-1690). Assim, **o cdc_ether presente NÃO é um substituto viável para o r8152 para esse dispositivo, na árvore de código conferida**.
- Em `drivers/net/usb/r8152.c`, `REALTEK_USB_DEVICE(VENDOR_ID_REALTEK, 0x8153)` contempla tanto interface vendor-specific quanto `CDC 02/06/00` e o `rtl8152_driver` teria nome `r8152` via `module_usb_driver()`. A CONFIG_USB_RTL8152=y do build EXP24 deveria incluir a implementação conforme gates da CI, mas não existe evidência ainda de boot/registro físico.

**Interpretação cautelosa:** a combinação da rejeição explícita pelo `cdc_ether` (código-fonte) + ausência de `r8152` em `/sys/bus/usb/drivers` (tablet) + adaptador 0BDA:8153 CDC config 2 (tablet) explica a **ausência de binding nessas capturas se a árvore E404 em execução seguir o código-fonte fixado**. Ainda não sabemos por que o driver dedicado não aparece registrado, pois `/proc/config.gz` do tablet declara `CONFIG_USB_RTL8152=y`, nem por que o dispositivo some da enumeração; a divergência `uname 5.10.404R` vs `/proc/version` e `/proc/sys/kernel/osrelease` 4.19.404R ainda demanda investigação da proveniência.

**Política técnica:** não remover a entrada da blacklist CDC às cegas — ela existe para encaminhar estes dispositivos ao driver adequado; forçar generic CDC pode falhar. A solução prioritária é garantir registro operacional do `r8152` na versão de kernel efetivamente compatível e medir USB host/energia/reenumeração separadamente. Não modificar kernel/USB/SELinux no tablet; **FLASH_READY=false**, artefato EXP24 somente compilado e não flashável.

**Fonte direta auditada:** https://github.com/kvsnr113/xiaomi_sm8250_kernel_e404/blob/fed88a6024cd4d46c52eda607a95d97d7371ba81/drivers/net/usb/cdc_ether.c#L749-L763 ; https://github.com/kvsnr113/xiaomi_sm8250_kernel_e404/blob/fed88a6024cd4d46c52eda607a95d97d7371ba81/drivers/net/usb/usbnet.c#L1686-L1690 ; https://github.com/kvsnr113/xiaomi_sm8250_kernel_e404/blob/fed88a6024cd4d46c52eda607a95d97d7371ba81/drivers/net/usb/r8152.c#L5310-L5357 .

## EXP24 — prova adicional de compilação Realtek e auditoria de ligação CI

Em 18/10/2026 foi auditado o log integral do job GitHub Actions da EXP24 **#39172615397**, job 117808656784, concluído com sucesso. Entradas diretas do log:
```text
CC      drivers/net/usb/r8152.o
LTO     vmlinux.o
MODPOST vmlinux.o
LD      vmlinux
SYSMAP  System.map
```
Também foram confirmados `CONFIG_USB_RTL8152=y` no resolved `.config`, o gate Kconfig 21 opções builtin e o SHA256 da `Image` EXP24 `773b37133766cb6877937bc53c84b2d5ad0a94985ca754d88a685e7c00648da0`.

**Intervenção de CI somente no repositório, sem dispositivo:** workflow `.github/workflows/exp24-ethernet-clang21-build.yml` atualizado em commit **`4d23c847da5f96b79ed5a09b77265d635d838a89`**. Novo step *Prove RTL8153 presence in final linked vmlinux* exige os arquivos `r8152.o`, `vmlinux` e `System.map` do build, linhas CC/LTO/LD/SYSMAP do log, linha de suporte a `0BDA:8153` e macro de registro do driver na fonte, e evidência dos símbolos `rtl8152_driver` e `rtl8152_probe` no `System.map` final. Publica `exp24-rtl8153-linked-symbols.txt` e `exp24-rtl8153-link-gate.txt`; inclui `FLASH_READY=false`, `RUNTIME_DRIVER_REGISTRATION=NOT_TESTED`. Condição fail-closed: se nomes forem otimizados/renomeados pelo LTO, falhar e revisar antes de afrouxar a prova.

**Status honesto:** step recém-integrado ainda sem resultado do novo CI verificado nesta sessão. O build anterior já comprovou compilação de `r8152.o` e link de `vmlinux`, mas ainda não disponibilizou o mapa de símbolos como prova. Não declarar `RTL8153_LINK_PASS` até novo CI confirmar. Em nenhum caso o gate de link equivale a prova de registro físico do driver.

**Correção de ferramenta local:** observador PowerShell v2 elimina encerramento antecipado na tentativa 23, registra `Scan_attempts_executed` e cada scan ausente, reporta presença sobre scans realmente executados e salva arquivo `exp24-rtl8153-v2-*` no PC. Nova versão existe como artefato local; não alegar que foi instalada ou executada no Windows. Comparação do E404: 2 presenças nas 23 sondagens efetivamente executadas da versão anterior, com sucesso de leitura dos nove atributos em uma janela; não taxa estatística definitiva.

**Bloqueios:** versão `uname=5.10.404R` vs `/proc/version` e `/proc/sys/kernel/osrelease` `4.19.404R`, config vivo `CONFIG_MODULES=y` vs fonte EXP24 `CONFIG_MODULES=n`, e enumeração/registro runtime ainda por esclarecer. **FLASH_READY=false**, sem imagem de boot gerada.

## EXP24 run #39179600330 - prova pos-link aprovada

Auditoria GitHub Actions da execucao #39179600330, job #117829321751: workflow concluido com `success` em todas as etapas, incluindo `Prove RTL8153 presence in final linked vmlinux (read-only; no boot)`.

Evidencias verificadas no log do job:
```text
CC      drivers/net/usb/r8152.o
LTO     vmlinux.o
LD      vmlinux
SYSMAP  System.map
rtl8152_probe
rtl8152_driver_init
rtl8152_driver_exit
__initcall__kmod_r8152__220_5357_rtl8152_driver_init6
rtl8152_driver
EXP24_RTL8153_LINK_PASS
RUNTIME_DRIVER_REGISTRATION=NOT_TESTED
PHYSICAL_ETHERNET_FUNCTIONALITY=NOT_TESTED
FLASH_READY=false
```

Image ARM64 nova SHA256 `da39d6a9bf983d76f42d788543644c4cba9a4f345ced2b517a8a75d6e8df75d2`, 30 MB aproximados. System.map SHA256 `b03da4fe392c374e954ad4fe23c1e897c4c1e2b0d8919a9d83010ff684e80a24`; objeto r8152.o SHA256 `ea3fbe36b27c2fa6316d1a0b28c48220b21604cbfa36f403e3e181caa5ec0f3f`.

Artefato publicado `pipa-exp24-ethernet-clang21-4` ID 12155857590; ainda nao e boot.img. Este gate prova compilacao, ligacao e presenca de initcall no ELF offline, NAO sua execucao/registro em hardware.

Coleta E404 observador V2: 36 de 40 sondagens com RTL8153 `0bda:8153` presente; 34 capturas completas dos descritores; nenhuma vinculacao de driver constatada. Presenca entre amostras correlacionadas nao equivale a confiabilidade em 40 reconexoes.

Identidade/proveniencia e compatibilidade permanecem pendentes (`uname -r=5.10.404R`, `/proc/version` e `/proc/sys/kernel/osrelease=4.19.404R`, E404 `CONFIG_MODULES=y` versus EXP24 `CONFIG_MODULES=n`). `FLASH_READY=false`.

## Auditoria de compatibilidade boot no slot b

Coleta ADB read-only no Xiaomi Pad 6 (E404, Android 16 crDroid):

- `ro.boot.slot_suffix` -> `_b` (slot atual).
- `ro.boot.bootdevice` -> `1d84000.ufshc`.
- `/dev/block/by-name/boot_a` -> `/dev/block/sde12`.
- `/dev/block/by-name/boot_b` -> `/dev/block/sde37`.
- `/dev/block/by-name/vendor_boot_a` -> `/dev/block/sde25`.
- `/dev/block/by-name/vendor_boot_b` -> `/dev/block/sde49`.
- `/proc/cmdline` reporta `androidboot.verifiedbootstate=orange`, `androidboot.hwversion=4.19.0`, `androidboot.slot_suffix=_b`, `androidboot.bootdevice=1d84000.ufshc`, `androidboot.usbcontroller=a600000.dwc3`, `androidboot.dtbo_idx=0`, `androidboot.dtb_idx=0`, `androidboot.force_normal_boot=1`.

**Privacidade:** o `cmdline` original inclui um identificador de serie do dispositivo; nao replicar o valor em relatorios ou artefatos publicos.

**Interpretacao:** o firmware atualmente usa slot `_b`; as particoes boot/vendor_boot em ambos slots sao acessiveis via symlinks. A presenca de vendor_boot nao prova por si so header version 3 ou 4. `androidboot.hwversion=4.19.0` e metadado de hardware, nao identificacao confiavel da release Linux. O estado `orange` nao basta para atestar flash seguro.

**Proximo gate (somente leitura):** obter os primeiros 64 bytes de `boot_b` e `vendor_boot_b`, decodificar assinaturas `ANDROID!` e `VNDRBOOT` e versoes de cabecalho. Para boot header v3/v4 `header_version` esta no offset 40 little endian; para vendor_boot v3/v4 esta no offset 8. Esses offsets seguem o codigo oficial AOSP `bootimg.h`; validar valor e layout antes de usar ferramentas de empacotamento. Verificar dimensoes das particoes com `blockdev --getsize64` sem gravacao.

Referencias tecnicas: https://source.android.com/docs/core/architecture/bootloader/boot-image-header e https://android.googlesource.com/platform/system/tools/mkbootimg/+/refs/heads/android16-qpr2-release/include/bootimg/bootimg.h

A EXP24 run #39179600330 passou no gate `EXP24_RTL8153_LINK_PASS` e preserva `FLASH_READY=false`; artefato atual contem kernel `Image`, nao boot.img. Nao iniciar `fastboot boot` nem gravar particoes antes de auditoria de header, proveniencia/config e reconstrucao verificavel.

## Reuso do boot compacto EXP19/EXP06 validado em hardware

Histórico técnico recuperado da validação anterior do projeto (18/10/2026): NÃO exigir ao usuário repetir o preflight de Android Boot V3 ou um teste prévio de `fastboot boot` do EXP06.

**Original E404 compacto controlado:** `C:\platform-tools\pipa_preflight\boot_b-stock-compact-control.img`, 32,206,848 bytes, SHA256 `202aaaf67fe5c0a963965c4e29f67866b509916e0bdff15dde38ef55b3d321e7`. Executou `fastboot boot` temporário e iniciou Android (`OKAY`).

**Ciclo EXP19:** a ferramenta oficial AOSP `mkbootimg` reproduziu o boot compacto original com comparação `MATCH` antes de alterar o kernel; esta foi a prova de round-trip. Candidato `Downloads\EXP19-output\EXP19-EXP06-NOT-FOR-FLASH.candidate.bin`, 32,206,848 bytes, SHA256 compacto `30065a39be707d836594da574be11b08c0228018ca91a681e1b122e6f0e6f60c`; SHA256 da partição virtual completa `c50a7b4d8447426331adbfae9296439a957069c0860a1d36d476b63aae083f00`. `EXP15_match=True`.

**Teste físico EXP06:** `fastboot boot` temporário aprovou inicialização em `pipa` slot `_b`; `proc/version` identificou kernel `4.19.404R`, compilação `runner@runnervm8k3b6` Clang21 em 18/10/2026; três políticas `schedutil/rate_limit_us=1500`. Reboot normal retornou persistentemente ao E404 original (`build-user@build-host`, #14, 23/08/2026) com `rate_limit_us=2000/2000/2000`. Não confundir `fastboot boot` temporário com flash.

**Estrutura V3 validada e re-observada:** `boot_b` magic `ANDROID!`, header version 3, kernel 30,349,336 bytes a partir do offset 4096, ramdisk 1,849,345 bytes a partir do offset 30,355,456, header_size 1580 e alinhamento 4096. Fim compacto calculado: `4096 + align(30349336,4096) + align(1849345,4096) = 32206848` bytes, idêntico ao tamanho do controle EXP19. `vendor_boot_b` magic `VNDRBOOT`, header 3, page size 4096. `boot_b` partição tem 201326592 bytes; `vendor_boot_b` 100663296 bytes. Slot ativo `_b` confirmado. `androidboot.hwversion=4.19.0` não é uma medida direta da versão do kernel.

**Ponto atual EXP24:** build #39179600330 confirmou `EXP24_RTL8153_LINK_PASS` e initcall real no `System.map`, Image SHA256 `da39d6a9bf983d76f42d788543644c4cba9a4f345ced2b517a8a75d6e8df75d2`. Candidato EXP24 ainda NAO EMPACOTADO nem testado. O procedimento deve **reutilizar integralmente o pipeline EXP19 de mkbootimg AOSP**, conferir igualdade de round-trip do controle original, substituir somente kernel preservando ramdisk, cmdline, os_version/header, dtb em vendor_boot, e validar hashes/offsets/tamanhos e persistência offline. Não gravar partições; candidato só para auditoria e potencial boot temporário posteriormente se gates passarem.

**Decisão:** preflight de formato V3, `fastboot boot` original e EXP06 são PROVAS PREVIAS REUTILIZADAS; não repetir comandos de medição de header ou slot sem motivo concreto. Eles não demonstram compatibilidade da nova Image EXP24. `FLASH_READY=false`.

## EXP24 — empacotador offline fail-closed para reutilizar EXP17/EXP19

Em 18/10/2026 foi preparado um pacote local de scripts para Windows (disponibilizado na conversa, NAO executado com o backup privado nem enviado como fonte ao GitHub): `EXP24-offline-repack-package.zip` SHA256 `d56b79a97c4701e841c295fa095689b637bfa2d04824b707ffdc329fe691b2a6`. Inclui `EXP24-build-offline.py`, `EXP24-run-windows.ps1`, `test_exp24_offline.py` e README.

**Processo offline:** valida controle EXP17/EXP19 `boot_b-stock-compact-control.img` SHA256 `202aaaf67fe5c0a963965c4e29f67866b509916e0bdff15dde38ef55b3d321e7`; valida o ZIP do Actions #39179600330 e a Image SHA256 `da39d6a9bf983d76f42d788543644c4cba9a4f345ced2b517a8a75d6e8df75d2`, `.config`, link gate e symbols. Utiliza `mkbootimg.py` do AOSP: reaplica o kernel original e exige byte-igualdade `MATCH` contra o controle antes de construir o candidato EXP24. Nova imagem exige ramdisk, os_version, os_patch_level e cmdline preservados e recalcula offsets v3 por alinhamento de 4096 bytes. Impede sobrescrever outputs; audita sha256 e limites de particao. Saidas: `EXP24-output/EXP24-RTL8153-NOT-FOR-FLASH.candidate.bin` e `EXP24-RTL8153-offline-audit.json`.

Opcional `-FetchAosp` busca script oficial numa revisao Git fixa com verificacao de hash de blob, ou `-Mkbootimg` aponta para a copia local ja usada EXP17/EXP19. O processo nao utiliza adb, fastboot, grava particoes nem publica dados privados. Testes sinteticos com boot v3 reduzido (nao equivalem ao boot real) passaram incluindo offsets, round-trip, preservacao ramdisk e rejeicao de entrada corrupta, prova de simbolos ausente, imagem alterada e sobrescrita. `python -m py_compile` aprovado.

**Estado honesto:** o ZIP/script foi criado materialmente no ambiente da conversa e disponibilizado para execucao na maquina Windows; o candidato real ainda NAO FOI CRIADO, pois os arquivos privados `boot_b-stock-compact-control.img` e artefato local baixado nao estao disponiveis no ambiente de execucao do assistente. A validacao da Image do EXP24 contra o boot_b privado depende da execucao no Windows. FLASH_READY=false. O pacote offline deve permanecer distinto da instalacao do kernel.

## EXP24 V3 offline candidate verified by Windows output

User Windows execution returned `EXP24 AOSP_STOCK_ROUNDTRIP=MATCH`, `EXP24_CANDIDATE=OFFLINE_CREATED_UNTESTED`, `RAMDISK_IDENTICAL=True`, and `FLASH_READY=false`.

Candidate reported size: **32,477,184 bytes**. SHA256: `ee8bae62c49166211f374768ab5ab76d2fba54c2565d69477c3e8aa49fe395c3`.

Independent calculation from the original EXP24 Actions artifact: `Image` 30,619,672 bytes with verified SHA256 `da39d6a9bf983d76f42d788543644c4cba9a4f345ced2b517a8a75d6e8df75d2`; Android V3 layout `4096 + align(kernel,4096) + align(stock_ramdisk=1849345,4096)` gives exactly **32,477,184 bytes**. Original compact control was 32,206,848 bytes.

Candidate image and JSON audit are stored locally on user's Windows device. The assistant has not read the newly created candidate bytes or JSON file directly. Next gate: independent hash of the local candidate and consistency review of the JSON audit. No boot/flash was executed; `FLASH_READY=false`.

## EXP24 — gate de auditoria independente: 14 de 14 PASS

Em 18/10/2026, verificacao independente via PowerShell Windows do candidato EXP24 terminou com **14/14 PASS** (output do proprio usuario). Resultado observado:
```text
SHA256: PASS
AuditHash: PASS
Size: PASS
AuditSize: PASS
Roundtrip: PASS
Ramdisk: PASS
Cmdline: PASS
OSMetadata: PASS
KernelHash: PASS
KernelOffset: PASS
RamdiskOffset: PASS
VendorBootPreserved: PASS
NoPartitionWrites: PASS
FlashBlocked: PASS
```

Hash independente do arquivo candidato: `ee8bae62c49166211f374768ab5ab76d2fba54c2565d69477c3e8aa49fe395c3`; tamanho 32,477,184 bytes. Compara com os campos JSON do empacotador. `aosp_stock_roundtrip=MATCH`, `ramdisk_identical=true`, `cmdline_identical=true`, `os_word_identical=true`, novo kernel SHA256 `da39d6a9bf983d76f42d788543644c4cba9a4f345ced2b517a8a75d6e8df75d2`, offsets kernel 4096 e ramdisk 30625792. As condicoes de preservacao de `vendor_boot` e ausencia de escritas reportadas no JSON foram confirmadas como consistentes, nao como auditoria externa do firmware.

**Decisao:** gate de empacotamento e consistencia offline aprovado. Nao equivale a boot real ou funcionamento do RTL8153. Precedente EXP19/EXP06 validou `fastboot boot` temporario sem flash no mesmo modelo `pipa`, slot b, bootloader unlocked, fastboot nao-userspace, rollback por reboot normal para E404. Qualquer primeiro teste EXP24 deve ser **isolado via `fastboot boot`**, com cabo de rede USB-C desligado e guardas de identidade/caminho/hash, nunca comandos `fastboot flash`. Em caso de FAILED ou boot sem Android, nao repetir blindamente; usar reboot de recuperacao. O candidato nao e flashavel e permanece `FLASH_READY=false`.

## EXP24 — teste em hardware: boot temporario e registro do r8152 aprovados

**Resultado fisico informado pelo usuario:** no Xiaomi Pad 6 `pipa`, slot `b`, bootloader `unlocked:yes`, `is-userspace:no`, candidato EXP24 offline com SHA-256 `ee8bae62c49166211f374768ab5ab76d2fba54c2565d69477c3e8aa49fe395c3` inicializou temporariamente via `fastboot boot` com `Sending boot.img OKAY` e `Booting OKAY`. O Android voltou a responder ao ADB.

Leituras POS-BOOT (transcritas):
```text
Linux version 4.19.404R (runner@runnervm8k3b6) (Android (14054515, +pgo, +bolt, +lto, +mlgo, based on r563880c) Clang 21.0.0, LLD 21.0.0) #1 SMP PREEMPT Mon Oct 19 00:15:52 UTC 2026
drwxr-xr-x 2 root root ... /sys/bus/usb/drivers/r8152
1500
1500
1500
```

**Conclusao comprovada:** o novo kernel compilado via CI #39179600330 inicializou em hardware, registrou o driver USB `r8152` no sysfs (ausente na coleta anterior do E404) e preservou a alteracao EXP06 de `schedutil/rate_limit_us=1500` em tres politicas. O resultado do `fastboot boot` nao e uma gravacao de particao; a instalacao persistente E404 deve ser preservada.

**Ainda nao testado:** vinculacao de `0bda:8153` ao `r8152` (`2-1:2.0/driver` ou `2-1:2.1/driver`), criacao de interface `eth*` / `enx*`, Ethernet service, DHCP, ping e estabilidade em 40 sondagens. O adaptador USB-C estava desconectado durante o teste de boot; nao declarar Ethernet funcional.

**Proxima etapa segura:** habilitar ADB sem fio e validar acesso antes de remover cabo USB do PC; conectar RTL8153 a USB-C do tablet e capturar sem alterar sistema, usando `tools/exp24-usb-ethernet-evidence.ps1 -Stage EXP24 -Serial <adb-wireless-serial>` em PowerShell. O script registra sysfs dos dispositivos, driver associado, interfaces de rede e dumpsys ethernet. Confirmar se `readlink driver` resolve `r8152`, e checar estado de link e IP; nao depender somente de `ls -ld /sys/bus/usb/drivers/r8152` que atesta registro mas nao binding. Evitar confundir falha OTG de enumeração com falta de driver. Reboot normal retorna ao E404 anterior; ainda nao demonstrado nesta execucao.

**Status atualizado:** `TEMP_BOOT_PASS=true`, `R8152_REGISTERED=true`, `SUGOV_1500_TRIPLE_PASS=true`, `USB_ETHERNET_LINK_TEST=NOT_YET`, `FLASH_READY=false`.

## EXP24 — primeira coleta RTL8153 pelo ADB Wi-Fi: permissões impedem conclusão

Após `fastboot boot` temporário bem-sucedido, o ADB Wi-Fi voltou a responder e foi confirmado novamente kernel `4.19.404R` de runner/Clang21 com o caminho `/sys/bus/usb/drivers/r8152` presente. `dumpsys ethernet` mostra EthernetTracker habilitado, filtro de nomes `(usb|eth)\d+`, **nenhuma interface rastreada** em EthernetNetworkFactory.

Leituras do shell ADB **sem root** de `/sys/bus/usb/devices/2-1/idVendor` e `idProduct` retornaram `Permission denied`. As tentativas `ls -l /sys/bus/usb/devices/2-1:2.0/driver` e `...2.1/driver` retornaram `No such file or directory`. `ip link show` sem root retornou `request send failed: Permission denied`; `ip -4 address show` mostrou somente `lo` e `wlan0`, com IPv4 em `wlan0`. Esses erros isolados NAO demonstram falha de probe; dispositivo pode desaparecer entre chamadas.

**Decisao:** nao afirmar que `r8152` falhou ao bind nem que a rede Ethernet existe. Fazer a proxima coleta com `su -c`, enumeracao dinamica USB (nao supor endereco sempre `2-1`), consultar interface device/driver e `/sys/bus/usb/drivers/r8152` por root, coletar `ip link` root, Ethernet dumpsys e log `dmesg` filtrado. Ao investigar interface rede, se o nome for outro que `usb[0-9]+` ou `eth[0-9]+`, Android EthernetTracker nao ira rastrea-la automaticamente (filtro observado).

Diagnostico Windows somente leitura fornecido como arquivo da conversa `EXP24-rtl8153-root-binding-diagnostic.ps1`, SHA256 `fb43ce1bce8f23b3da16c86d0605f645f0f8db5bb0300b13ff73a35b45463a61` (arquivo NAO inserido na arvore do repositorio). Exige serial ADB Wi-Fi explicitamente, comprova Clang21 e root, amostra 3 vezes IDs Realtek via sysfs, separa existencia das interfaces e driver, registra rede e logs filtrados. Nao faz bind/unbind, escrita sysfs, reboot, fastboot ou flash.

**Estado:** EXP24_TEMP_BOOT=PASS, R8152_DRIVER_REGISTERED=PASS, RTL8153_ENUMERATION_WITH_ROOT=PENDING, RTL8153_BINDING=PENDING, ETHERNET_IP=PENDING, FLASH_READY=false.

## EXP24 runtime root diagnostic: NIC absent from USB enumeration

User ran `EXP24-rtl8153-root-binding-diagnostic.ps1` with ADB over Wi-Fi and `su -c` successfully, on temporary EXP24 kernel Clang 21, root `uid=0`.

Observed hardware and results in three samples:
- USB device `1-1` vendor `05e3`, `2-1` vendor `05e3` (USB hub); `1-1.3` vendor `32c2` (dmesg labels the downstream receiver 2.4G Wireless).
- **No `0bda:8153` enumerated in 3/3 samples**, nor any other enumerated Realtek NIC. The address `2-1` now names hub 05e3, NOT RTL8153. USB paths are not stable identities.
- Registered `/sys/bus/usb/drivers/r8152` contains bind/new_id/remove_id/uevent/unbind but NO bound interface entry; `dmesg` unequivocally contains `usbcore: registered new interface driver r8152`.
- Root `ip link` and `/sys/class/net`: no Ethernet interface. `dumpsys ethernet`: tracker enabled, interface regex `(usb|eth)\d+`, no tracking interfaces. Wi-Fi `wlan0` has IPv4.

**Boundary of conclusion:** `R8152_RUNTIME_REGISTERED=PASS`; `REALTEK_0BDA8153_USB_ENUMERATION=NOT_OBSERVED`; `RTL8153_DRIVER_BINDING=NOT_TESTABLE_YET`; `ETHERNET_INTERFACE=ABSENT`. This is NOT evidence that Realtek probe failed, because probe cannot occur until NIC is enumerated. Does not establish whether dongle was physically connected, whether USB hub has an unpowered/disconnected port, OTG USB-C negotiation issues, or an intermittent link.

Next safe experiment: leave temporary kernel and Wi-Fi ADB running; ensure the RTL8153 dongle with RJ45 connector is actually connected and powered, preferably directly into tablet USB-C without intermediary hub where feasible. Capture VID and PID dynamically via root across multiple samples, not from hard-coded `2-1`; only after observing `0bda:8153` examine `driver` symlinks and `dmesg` for Realtek errors. No sysfs writes/bind/unbind, no kernel rebuild/flash. `FLASH_READY=false`.

## EXP24 — coleta root: RTL8153 ausente no barramento, nao houve tentativa de probe

Coleta via ADB Wi-Fi e `su -c` no Xiaomi Pad 6 usando o kernel EXP24 temporário, hora local de coleta `2026-10-18T22:26:32-03:00`. Evidência dos dois textos apresentados pelo usuário (conteúdo coincidente).

**Provas positivas de kernel e root:** `/proc/version` mostra compilação `runner@runnervm8k3b6`, Clang21 / Linux `4.19.404R`. `su -c id` retornou `uid=0(root)`, contexto KernelSU. `dmesg` confirma `usbcore: registered new interface driver r8152` durante inicialização. `/sys/bus/usb/drivers/r8152` contém os atributos `bind`, `unbind`, `new_id`, `remove_id`, `uevent`, mas **nenhum dispositivo ou interface associada** naquele instante.

**Topologia observada nas três amostras:** USB paths `1-1`, `1-1.3`, `2-1`, interfaces `1-1:1.0`, `1-1.3:1.0`, `1-1.3:1.1`, `2-1:1.0`. Os idVendor lidos foram `1-1=05e3`, `2-1=05e3` (possíveis hubs em buses USB 2/3) e `1-1.3=32c2` (periférico sem fio, conforme mensagens do kernel `2.4G Wireless`). **Nenhum `0bda`** foi visto, logo o Realtek RTL8153 (`0bda:8153`) não estava enumerado no período. O caminho `2-1` anteriormente ocupado pelo RTL8153 pode ter sido reutilizado pelo hub; nunca identificar hardware somente por caminho sysfs.

**Redes:** `/sys/class/net` e `ip link` root mostram loopback, `wlan0`, interfaces Wi-Fi e interfaces virtuais; nenhuma Ethernet física `eth*` ou `usb*`. `ip -4 addr` mostra IPv4 somente no `wlan0`. `dumpsys ethernet`: serviço enabled, filtro `(usb|eth)\d+`, `Tracking interfaces` vazio.

**Decisão causal:** o resultado NÃO prova falha de `rtl8152_probe`, nem regressão do driver; o VID/PID alvo simplesmente não foi capturado (0 de 3 amostras). `dmesg` traz o registro bem-sucedido do r8152, mas nenhuma linha de hotplug `0bda:8153` nesta coleta. Proximo gate: confirmar fisicamente o dongle RTL8153 conectado (um cabo RJ45 isolado nao substitui adaptador USB conectado), coletar `idVendor/idProduct/product` de TODOS os USB paths via root por vários instantes, localizando o alvo dinamicamente. Caso `0bda:8153` apareça: capturar interfaces e links `driver`, `ip link` com root e logs completos proximos da inserção. Se permanecer ausente, investigar topologia/conexão, cabo/OTG, alimentação, enumeração e hub, e nao mexer no `r8152`.

**Segurança:** nenhuma escrita sysfs, bind/unbind, reinit USB, reboot, fastboot ou flash; `FLASH_READY=false`. Não copiar identificador serial presente em trechos extensos de kernel cmdline para a documentação pública.

## EXP24 — touchscreen sem resposta: hub USB e mouse sao necessarios

O usuário confirmou que o touchscreen do Xiaomi Pad 6 pipa **não está funcionando** nesta sessão e que utiliza um hub USB por necessidade, para conectar mouse/periféricos e operar o aparelho. Problemas semelhantes já ocorreram em outras ocasiões; não há atribuição causal comprovada ao EXP24, slot b, E404 ou crDroid. Não exigir a remoção do hub como pré-condição para diagnósticos.

Na última coleta root foram encontrados os dispositivos USB `05e3` (dois caminhos de hub) e `32c2` (periférico 2.4 GHz), mas **nenhum `0bda:8153`**; logo essa captura não serviu para avaliar o probe do driver `r8152`. Confirmar presença física do dongle Realtek e enumeração quando puder ser conectado ao hub. Não confundir ausência física com falha do driver.

**Gate prioritário touchscreen, somente leitura, preservando EXP24 temporária e controle por mouse:** via ADB Wi-Fi coletar `/proc/bus/input/devices`, `getevent -pl`, mensagens dmesg filtradas por touch/input/I2C/panel/firmware e `/proc/interrupts` relevante. Após identificar um dispositivo touchscreen correto, realizar leitura controlada de eventos `getevent -lt /dev/input/eventN` enquanto o usuário toca a tela (e somente se o caminho for comprovadamente touchscreen). Se não há dispositivo de input, suspeitar da inicialização/firmware/DT; se existe mas não produz eventos, investigar hardware/IRQ/controlador; se produz EV_ABS, investigar Android input/overlays. Nenhuma dessas hipóteses está ainda demonstrada.

**A/B:** slot `b` não é por si só causa demonstrada. Não trocar slot/ROM, não escrever nodes sysfs, não forçar bind/unbind, não reiniciar sem necessidade, pois `fastboot boot` EXP24 é temporário. Se posteriormente desejar isolar kernel, comparar com boot persistente E404 apenas após salvar logs e aceitar perder a sessão EXP24 temporária. FLASH_READY=false.

## EXP24 — RTL8153 reconhecido, vinculado ao r8152 e Ethernet operacional no Android

Coleta real no Xiaomi Pad 6 pipa com o kernel EXP24 em `fastboot boot` temporario, ADB Wi-Fi com KernelSU root; `2026-10-18T22:33` horario local, arquivo de evidencia do Windows `EXP24-rtl8153-root-binding-20261018-223315.txt` (logs privados, nao comitar sua integralidade porque dmesg inclui serial/MAC/endereco).

### Gate USB + driver + Android: PASS

- VID/PID **`0bda:8153`** presente no sysfs em **3/3 amostras**, em `2-1.1` atras de hub USB `05e3` na porta `2-1`; outras interfaces no hub sao perifero 2.4GHz `32c2`, utilizado para operar o dispositivo sem touchscreen funcional.
- Configuracao USB ativa `1`, authorized `1`, speed `5000` Mb/s = USB SuperSpeed negociado, NAO throughput Ethernet medido. Interface correta **`2-1.1:1.0`**, e NAO as interfaces `:2.0/:2.1` do adaptador antes de passar pela selecao atual de configuracao. `modalias=usb:v0BDAp8153d31FDdc00dsc00dp00icFFiscFFip00in00`.
- Symlink da interface `2-1.1:1.0/driver` aponta diretamente para `/sys/bus/usb/drivers/r8152`; a pasta do driver contem entrada de dispositivo `2-1.1:1.0`. **Probe e bind bem-sucedidos.**
- `/sys/class/net` contem `eth0`; `ip link` root: `eth0 <BROADCAST,MULTICAST,UP,LOWER_UP>`, state `UP`, MTU 1500. IPv4 `192.168.1.106/24` em `eth0` via configuracao Android; WLAN `192.168.1.109/24` separada.
- Android `dumpsys ethernet` registra `eth0` em EthernetNetworkFactory, `EthernetPort(eth0, ifindex=21)`, `up:true`, agente de rede e IpClient, IPv4, DNS e rota padrao via `192.168.1.254`. Isso confirma integracao da interface ao EthernetTracker e configuracao IP. Nao publicar MAC especifico.
- Dmesg confirma `usbcore: registered new interface driver r8152`, `r8152 2-1.1:1.0 eth0: v1.09.9`, terminando com `r8152 2-1.1:1.0 eth0: carrier on`.

**Limite de escopo:** nao houve teste de ping por eth0 com interface forcada, perda de pacotes, throughput, durabilidade ou recuperacao sob carga. `USB_ENUMERATION=PASS`; `R8152_BIND=PASS`; `ANDROID_ETHERNET_IP=PASS`; `LINK_CARRIER=ON`; `TRAFFIC_TEST=PENDING`; `LONG_TERM_STABILITY=PENDING`.

### Issue aberta: erros de protocolo USB

Dmesg registra diversas ocorrencias `r8152 2-1.1:1.0 eth0: Stop submitting intr, status -71` seguidas por novas mensagens `eth0: v1.09.9`; isso indica periodos transitorios de falha/interrupcao da transferencia URB USB e reinitializacao/reprobe aparente. `-71` e `-EPROTO` Linux; pode ser hub/energia/cabo/sinal/controlador, mas a causa nao foi isolada. **Nao rotular este evento como driver r8152 corrigido, nem exigir remocao do hub**, pois o hub e necesssario para mouse enquanto touchscreen nao responde. Sem alteracoes no kernel por tentativa e erro.

**Proximo gate read-only e isolado:** amostrar contadores `eth0` (`rx_packets`, `tx_packets`, `rx_errors`, `tx_errors`, `carrier_changes`, se presentes), `ip route`, latencia/perda por `ping -I eth0` ao gateway local (nao usar rota Wi-Fi inadvertidamente), e dmesg filtrado depois. Manter kernel EXP24 temporario sem reboot, coletar touchscreen separadamente como issue independente. Nao fazer flash; `FLASH_READY=false`.

## EXP24 — instabilidade de hotplug RTL8153 apesar de funcionamento em outro dispositivo

Usuário confirmou o adaptador RTL8153 estável em outro equipamento, inclusive em retiradas/inserções repetidas, mas no Xiaomi Pad 6 `pipa` com hub USB usado para mouse (touchscreen não funcional), reconhecimento é INTERMITENTE: em um momento 0/3 amostras de `0bda:8153`, em outra coleta 3/3 amostras reconhecidas, `r8152` vinculado e `eth0` com DHCP. Dmesg no sucesso registrou múltiplos `r8152 ... Stop submitting intr, status -71` e tentativas subsequentes até `carrier on`.

**Investigação de fonte original:** `drivers/usb/core/quirks.c` na base exata `kvsnr113/xiaomi_sm8250_kernel_e404@fed88a6024cd4d46c52eda607a95d97d7371ba81` **já inclui** `{ USB_DEVICE(0x0bda, 0x8153), .driver_info = USB_QUIRK_NO_LPM }`. Há entradas para hubs `05e3:0612` e `05e3:0616` com NO_LPM, mas ainda NÃO se conhece o PID do hub deste usuário. Portanto não propor um patch genérico 'adicionar NO_LPM ao RTL8153' que duplicaria a quirk existente. Conferir LPM em runtime (somente leitura) e `idProduct` dos hubs antes de decidir mudança experimental. `-71` é `EPROTO`, erro de transação/protocolo USB e pode indicar não resposta, sinalização, hub, timeout, cabo/porta ou controlador; não prova defeito do adaptador (que funciona em outro equipamento) nem prova bug de software.

**Novo instrumento de diagnóstico local (não instalado no tablet):** `EXP24-rtl8153-hotplug-timeline.ps1`, hash SHA256 `b75308f33d71dab6107857db0653e21acb99acd11db4d09b52cb03fb5ec51427`, disponibilizado na conversa, **não há prova de execução no hardware ainda**. Por ADB Wi-Fi e root KernelSU, valida pipa+Clang21, faz amostragem temporal de presença real por VID:PID, interfaces associadas a `r8152`, `eth0/carrier`, velocidade e nós LPM quando existem, coleta PID dos hubs e eventos `dmesg`. Preserva hub e mouse; não escreve em sysfs, altera energia, faz reboot, flash nem outro comando destrutivo. A cada evento classificar USB ausente vs presente sem bind vs bind sem carrier vs bind/carrier ON. Somente após isso discutir EXP25 e hipótese de power/Type-C/host/hub/PHY, sem aplicar patches às cegas.

**Estado:** Ethernet comprovadamente opera na EXP24, mas HOTPLUG_RELIABILITY=FAIL/UNPROVEN, EPROTO=-71_OBSERVED, RTL8153_NO_LPM_QUIRK=ALREADY_IN_SOURCE, FLASH_READY=false.

## EXP24 — Hotplug timeline V2: PowerShell parser e variavel PID corrigidos

Em teste no Windows PowerShell 5.1, a versao inicial do observador `EXP24-rtl8153-hotplug-timeline.ps1` nao chegou a executar: erro de parse na linha 83, `Write-Host "Sample $i/$Samples: ..."`, porque `:` apos `$Samples` e ambiguo para o parser PowerShell.

Auditoria estatica revelou uma segunda falha que impediria a deteccao de Realtek mesmo se o parse fosse corrigido: tentativa de escrever `$pid`, nome reservado `PID` (automatic variable read-only case-insensitive) para guardar objeto de resultado `idProduct`.

**V2 disponibilizada:** `EXP24-rtl8153-hotplug-timeline-v2.ps1`, 7.062 bytes, SHA-256 `523a79df4e9f2f5eaa78aebc336d0daf3d999fa1cf74e783f86bd17c413ab9b0`. Corrige interpolacao para `"Sample ${i}/${Samples}: ..."`, substitui `$pid` por `$productIdResult` e delimita interpolacao das chaves de log `${p}` e `${lpm}`. Diff revisado; varredura local de sintaxe suspeita e uso de `$pid=` passou; **nao houve parser real PowerShell/Windows nem teste ADB real da V2 neste ambiente**, pois PowerShell nao instalado. Usuario deve validar parse com `[System.Management.Automation.Language.Parser]::ParseFile` antes da execucao; coleta deve permanecer read-only.

A V1 nao gerou relatorio, pois falhou ANTES da execucao; isso nao e evidência de falha no kernel, driver nem USB. `FLASH_READY=false`.

## EXP24 — HOTPLUG V2 no hardware: 0/18 amostras sem RTL8153

Usuario executou no Windows a versao V2 `EXP24-rtl8153-hotplug-timeline-v2.ps1` para o mesmo `pipa` em boot temporario EXP24 via ADB TLS Wi-Fi, `-Samples 18 -IntervalSeconds 2`, com parser PowerShell validado (`EXP24 V2 PARSER: PASS`) e hash V2 confirmado contra `523a79df4e9f2f5eaa78aebc336d0daf3d999fa1cf74e783f86bd17c413ab9b0`.

**Resultado observado na consola:** 18/18 linhas `0BDA:8153=False, r8152=False, eth0_carrier=missing`; resumo `RTL8153 present 0 samples, r8152 bound 0, link 0`. Saida Windows: `C:\platform-tools\exp24-usb-ethernet-evidence\EXP24-rtl8153-hotplug-timeline-20261018-225259.txt`. Script declarou `No device configuration or partition was modified.` Nao ha indício no console de interrupcao ADB nem falha root. O conteudo do relatorio detalhado (VID/PID dos hubs, trechos filtrados de dmesg) **ainda nao foi enviado** ao assistente.

**Interpretacao limitada:** dados **compatíveis com ausencia de enumeracao** do dispositivo alvo durante o intervalo; nao comprova se o dongle RTL8153 estava fisicamente conectado em cada amostra nem isola problemas de alimentação, hub, porta ou host. No monitor V2, quando `REALTEK=ABSENT` registra os caminhos USB existentes, mas nao os VID/PID de todos os caminhos por amostra (apenas VID/PID dos hubs no inicio), de modo que precisamos do arquivo gerado e de uma coleta independente para excluir falsos negativos. Antes houve EXP24 USB 3.0 5000 Mb/s, binding `r8152`, `eth0`, IP, DHCP/Android Ethernet e eventos USB -71. Logo, a capacidade do driver esta demonstrada, a fiabilidade de reconexões ainda nao.

**Proximo gate read-only:** receber relatorio `.txt` e inspecionar `dmesg` e os IDs dos hubs `05e3` (incluindo product IDs, se existirem). Durante adaptador fisicamente inserido, comparar `ls -1 /sys/bus/usb/devices` root e leitura independente de idVendor/idProduct por caminho, sem bind/unbind nem reinit USB. Se ausente inclusive em sysfs, investigar power/Type-C/hub/xHCI e host; se VID/PID presente mas script False, corrigir instrumento antes de alterar o kernel. Preservar hub e mouse devido à falha touchscreen; nenhuma troca de slot/boot ou flash. `FLASH_READY=false`.

## EXP24 — pista nova: instabilidade USB-C durante carregamento em kernels anteriores

**Novo relato do usuário, pré-existente à EXP24:** alguns carregadores com perfis de maior tensão/potência ou múltiplas tensões disponíveis provocam ciclos de conexão/desconexão no Xiaomi Pad 6 pipa. O usuário esclarece que isso **não começou com o kernel experimental**. A descrição de 'muitas voltagem' é informal, e não há medição de VBUS, contrato PD, corrente, fonte exata, cabo ou logs PMIC, nem confirmação de que a tensão máxima tenha sido aplicada.

**Correlação com Ethernet intermitente:** o dongle Realtek USB `0bda:8153` funciona de modo repetível em outro dispositivo, mas na tablet por hub `05e3` passa de 0/18 leituras presentes à detecção com SuperSpeed 5000, driver r8152, eth0 e DHCP, com logs `-71/EPROTO` e repetidas recuperações até carrier on. Falha do touchscreen exige preservar hub+mouse na coleta. A sobreposição de intermitência de carga e USB de dados sugere investigar **subsystema da porta USB-C** antes de atribuir falha ao NIC: detecção CC, controlador Type-C/PD, VBUS, OTG/host, reguladores, estados suspend/resume do xHCI/DWC3, PHY/SuperSpeed, hub e qualidade da conexão. Pode haver causas diferentes; associação não prova causa comum.

**Precauções:** não afirmar que carregador de maior wattagem aplica sua maior tensão automaticamente (negociação USB-PD). Não prescrever tensão/corrente experimental, carga com fonte instável, troca de slot/ROM, desabilitação de proteções térmicas/PMIC/PD ou escritas sysfs. Preferir carregador/cabo conhecido estável; caso haja aquecimento excessivo, cheiro, danos físicos ou reinícios repetidos, interromper o teste de carregamento e procurar assistência especializada.

**Próximos dados somente-leitura:** manter EXP24 em boot temporário e hub/mouse; coletar relatório completo `EXP24-rtl8153-hotplug-timeline-20261018-225259.txt` (ainda não anexado), enumerar IDs dos hubs/Realtek por root quando presente/ausente, correlacionar eventos cronológicos `dmesg` de `typec|pd|power_supply|vbus|dwc3|xhci|usb|charger` no intervalo. Quando seguro, consultar somente leitura `/sys/class/power_supply/*/{type,online,voltage_now,current_now,usb_type}` se os atributos existirem; esses campos podem não representar diretamente VBUS negociado. Teste A/B com carregador/cabo conhecido estável, sem forçar uma fonte instável; NENHUMA alteração persistente ou force-reset de controlador. Manter `FLASH_READY=false`.
