## EXP23.1 — Correção shell e inventário térmico realizado no E404 (18/10/2026)

O usuário executou a versão corrigida do comando PowerShell/ADB, sem `|` no interior do `echo`, e filtrou nomes no Windows com `Select-String`. A saída **sem erros de shell** foi:

```text
gpuss-0-usr=30800
gpuss-1-usr=32400
pm8150_tz=35024
soc=
charger_therm0=29307
batt_therm=288
cpu_therm=32401
battery=28200
```

**Resultado:** `EXP23_SYSFS_SENSOR_DISCOVERY=PASS_REAL`: oito nomes retornados, sete com número e um `soc` sem valor. Unidades **não foram confirmadas por documentação específica do driver**: para `cpu_therm`, `gpuss-0-usr`, `gpuss-1-usr`, `pm8150_tz`, `charger_therm0`, `battery` é plausível a escala de milésimos de grau Celsius (valores aproximadamente 32.401, 30.800, 32.400, 35.024, 29.307 e 28.200 °C respectivamente); para `batt_therm=288` é plausível décimos de grau (28.8 °C). Não comparar diretamente as grandezas sem considerar a escala nem classificar `soc=` como zero; isto último significa leitura vazia/inacessível no momento. A saída foi obtida com kernel E404 original após reversão EXP22.3; não há teste EXP06 repetido nesta fase.

**Controle de desempenho pendente:** valores são instantâneos e não contêm frequência real sob carga, frametimes/FPS, potência, controle de temperatura inicial ou replicatas. Planejar primeira amostra E404 com workload definido e CSV em Windows; nova autorização será necessária para outro `fastboot boot` EXP06. Nenhum ganho FPS/latência/estabilidade pode ser inferido somente dos sensores. A saída anterior de `dumpsys thermalservice` tinha `HAL Ready: false`, por isso sysfs é a fonte operacional de medição neste momento. `FLASH_READY=false`.

## EXP23.1 — Sensores sysfs identificados, mas saída do comando anterior invalidada por shell (18/10/2026)

O usuário executou na sessão **Windows PowerShell 5.1** o comando `adb shell 'for z in ...; ... echo "$z | $t | $v"; done'` sugerido na conversa anterior. Em vez de linhas delimitadas, recebeu dezenas de mensagens `/system/bin/sh: <nome_do_sensor>: inaccessible or not found` e `/system/bin/sh: <valor>: inaccessible or not found`, incluindo `cpu_therm`/`32290`, `gpuss-0-usr`/`30800`, `soc`/`34700`, `battery`/`28200`, `batt_therm`/`290`, `charger_therm0`/`29423`. O `|` inserido no texto echo atravessou a serialização de argumentos entre PowerShell nativo/adb shell sem preservação das aspas pretendidas; o shell remoto o tratou como **operador pipe** e tentou executar nomes de sensores/valores como comandos. **Não** interpretar esses erros como inexistência das thermal zones ou defeito do kernel.

Também foi executado `adb shell cat /sys/class/power_supply/battery/temp`, que retornou `Permission denied` no usuário de shell comum. Não houve tentativa de root, de escrever temperaturas ou de modificar o kernel.

**Resultado:** `EXP23_SYSFS_SENSOR_DISCOVERY=PARTIAL_UNFORMATTED`; a saída informa tipos/valores crus plausíveis, mas **não** é uma coleta formatada confiável; nenhum valor térmico absoluto será homologado até leitura corrigida. Não misturar escalas: muitos sensores usam miligraus Celsius (por exemplo `cpu_therm=32290` pode significar 32,290 °C), enquanto `batt_therm=290` pode usar décimos de grau (29,0 °C). As unidades dependem de cada driver.

**Correção simples e somente leitura:** executar uma iteração sem o caractere `|` dentro do comando remoto e formatar como `echo $z $t $v`, com filtro local `Select-String` no PowerShell, ou fazer `adb shell cat <thermal_zoneN>/type` e `/temp` separadamente. Isso é correção de quoting na invocação anterior do assistente, não mudança no dispositivo. Continuar em E404 original, sem nova tentativa de `fastboot boot` EXP06, sem root para esse diagnóstico e `FLASH_READY=false`.

## EXP23.A — BASELINE CPU/MAX E SERVIÇO TÉRMICO COLETADO NO E404 REAL (18/10/2026)

Após EXP22.3 e retorno ao kernel original, usuário executou em PowerShell:

```text
adb shell cat /sys/devices/system/cpu/cpufreq/policy*/scaling_max_freq
1804800
2419200
2841600

adb shell dumpsys thermalservice
IsStatusOverride: false
ThermalEventListeners:
  callbacks: 6
  killed: false
  broadcasts count: -1
ThermalStatusListeners:
  callbacks: 2
  killed: false
  broadcasts count: -1
Thermal Status: 0
Cached temperatures:
HAL Ready: false
Temperature headroom thresholds:
[0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
```

**Resultado:** `EXP23_E404_MAX_FREQS=PASS_REAL`, três limites de cpufreq `1804800`, `2419200`, `2841600` kHz (aprox. 1.8048, 2.4192, 2.8416 GHz), na ordem em que o glob retornou as políticas. São máximos configurados e **não** frequências efetivamente medidas durante carga. O serviço do Android apresenta `Thermal Status: 0` (enum `THERMAL_STATUS_NONE`) e `IsStatusOverride: false`, mas também `HAL Ready: false` e cache de temperaturas vazio. Portanto **não há leitura de temperatura disponível na saída**, e o estado 0 isoladamente **não é prova** de ausência de throttling ou de camada de mitigação térmica ativa/inativa. Segundo a documentação de Android ADPF, alguns aparelhos retornam `THERMAL_STATUS_NONE` mesmo quando outros sinais de calor indicam restrição, sendo necessário usar sensores/headroom disponíveis e confirmar suporte. Fontes: https://developer.android.com/games/optimize/adpf/thermal ; https://source.android.com/docs/core/power/thermal-mitigation . 

**Próximo gate diagnóstico somente leitura (sem root):** consultar nomes e valores crus dos thermal zones de sysfs, e, separadamente, sensor de bateria se acessível. Não converter escalas de temp automaticamente: algumas interfaces publicam miligraus Celsius, outras décimos e valores não confiáveis. Se leitura/sysfs não disponível ou todos sensores inválidos, marcar `THERMAL_MEASUREMENT=UNAVAILABLE` e concentrar teste A/B em carga, cpufreq e métricas confiáveis de frametime, em vez de presumir temperatura.

**Estado:** `EXP23_THERMALSERVICE_TEMPERATURE=UNAVAILABLE`, `EXP23_SYSFS_SENSOR_DISCOVERY=PASS_REAL`, `EXP23_EXP06_REPEAT_AUTH=PENDING`, `FLASH_READY=false`. Não houve nova inicialização EXP06 nem flash durante esta coleta.

# EXP23 — Teste controlado de desempenho e estabilidade E404 vs EXP06

**Data:** 18/10/2026. **Ponto de partida:** EXP22.3 homologada em dispositivo real: o kernel E404 original `4.19.404R (build-user@build-host) #14 Aug 23 2026` exibe três políticas `schedutil/rate_limit_us=2000`. Um boot temporário experimental exibiu `4.19.404R (runner@runnervm8k3b6) #1 Oct 18 2026` e três políticas `rate_limit_us=1500`, com `pipa`, slot `_b`, ADB operacional. Após reboot normal, voltou ao kernel antigo #14 e `2000/2000/2000`. **Não houve flash. `FLASH_READY=false`.**

## Objetivo

Medir se a alteração de `2000 → 1500 µs` do schedutil produz diferença de fluidez, quedas de FPS, estabilidade ou limitação térmica em **uma carga real e comparável**, não presumindo que reduzir 25% o parâmetro de governador signifique melhorar 25% o desempenho.

## Protocolo mínimo

**A. Baseline E404 (agora, sem operações de boot/flash):**

Registrar kernel, políticas cpufreq e condição térmica antes da carga, com ADB read-only:

```powershell
$adb="C:\platform-tools\adb.exe"
& $adb shell getprop ro.product.device
& $adb shell getprop ro.boot.slot_suffix
& $adb shell cat /proc/version
& $adb shell "cat /sys/devices/system/cpu/cpufreq/policy*/scaling_governor"
& $adb shell "cat /sys/devices/system/cpu/cpufreq/policy*/schedutil/rate_limit_us"
& $adb shell "cat /sys/devices/system/cpu/cpufreq/policy*/scaling_max_freq"
& $adb shell dumpsys thermalservice
```

Escolher **uma mesma carga reproduzível** no Xiaomi Pad 6 (por exemplo jogo com mesma cena, modo de FPS/qualidade/resolução, rede e bateria). Ideal: três rodadas de 5 minutos com pausas até temperatura de início semelhante. Registrar FPS médio, FPS 1% low ou frametime p95/p99 **somente se ferramenta de medição realmente os fornecer**, travamentos e temperatura/térmica nos mesmos momentos. Se não houver ferramenta confiável de FPS, registrar apenas medições que existirem e não inventar métricas. Preferir condições iguais de brilho, taxa de atualização, carregamento, modo de energia, apps em segundo plano e aquecimento.

**B. EXP06 (somente depois de nova autorização para OUTRA tentativa temporária `fastboot boot`; EXP22.3 foi autorização para uma tentativa anterior):**

Revalidar SHA256/tamanho do candidato `30065a39be707d836594da574be11b08c0228018ca91a681e1b122e6f0e6f60c` / `32206848` bytes, Fastboot identidade `pipa` e slot `b`, abrir EXP06 por `fastboot boot` uma única vez, verificar compilação `runner` / `#1` e valores `1500`. Repetir exatamente a carga A e coleta. Usar mesmo procedimento de contingência da EXP22.3. **Não executar sem autorização adicional.**

**C. Retorno ao E404:**

Após o teste temporário EXP06 e verificação de Android funcional, reiniciar normalmente, confirmar ADB `pipa`, slot `_b`, kernel `build-user@build-host #14`, parâmetros `2000`. Repetir a carga somente se útil para remover vieses de ordem (A-B-A). Não declarar ganho de FPS sem números ou confundir efeitos de temperatura, rede, jogo e cache.

## Critério de avaliação

- **Boot estável:** sem bootloop, ausência de regressões severas, ADB e apps funcionam; o único boot EXP06 homologado por enquanto foi um ciclo curto.
- **Desempenho:** contraste de FPS/framedrops/frametimes por rodadas equivalentes; buscar consistência e temperatura de início, não apenas pico.
- **Térmica/frequência:** cruzar `dumpsys thermalservice` e frequências máximas expostas; leitura `scaling_cur_freq` instantânea não mede desempenho real.
- **KernelSU e uso real:** verificar funcionalidade apenas se houver demanda e autorização, sem alterações permanentes.
- **Restauração:** `fastboot boot` temporário e retorno normal foram testados; recuperação após kernel travado/flash falho não foi testada. A/B metadados ou backups não garantem restauração automática.

## Estado

`EXP23_BASELINE_E404=PENDING`, `EXP23_REPEAT_EXP06_AUTH=PENDING`, `EXP23_PERFORMANCE_COMPARISON=PENDING`, `FLASH_READY=false`. O presente documento **não autoriza** nova inicialização experimental nem flash permanente.
