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

**Estado:** `EXP23_THERMALSERVICE_TEMPERATURE=UNAVAILABLE`, `EXP23_SYSFS_SENSOR_DISCOVERY=PENDING`, `EXP23_EXP06_REPEAT_AUTH=PENDING`, `FLASH_READY=false`. Não houve nova inicialização EXP06 nem flash durante esta coleta.

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
