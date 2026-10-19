# EXP25A — empacotamento offline Android Boot V3 (pré-boot, sem flash)

## Evidências do usuário (Windows)

- ZIP original do CI: `$env:USERPROFILE\Downloads\pipa-exp25a-touch-irq-clang21-1.zip`.
- `Image` extraída e verificada com SHA-256: `2dac2dd05fe3cab8b167ea10bc632512c1508fa4d26db88d002837d0dc681e08`, resultado `EXP25A IMAGE INTEGRITY: PASS`.
- Controle compacto preexistente: `C:\platform-tools\pipa_preflight\boot_b-stock-compact-control.img`, SHA-256 `202aaaf67fe5c0a963965c4e29f67866b509916e0bdff15dde38ef55b3d321e7`, resultado `BOOT ORIGINAL: PASS`.
- Compilação CI #39190015939 anteriormente aprovada; não confundir compilação com boot/teste do touchscreen.

## Pacote offline entregue na conversa

Arquivo `EXP25A-offline-boot-v3-scripts.zip` (11.044 bytes, SHA-256 `fd56cf4db1c51ab48b40535becc69143f73855e1f9e555c97cd3c6f6bf9566c9`). Contém:

| Arquivo | SHA-256 |
| --- | --- |
| `EXP25A-build-offline.py` | `1b65305f2b65703e8bb791af33a88c9dab2ac2442407b18a31ac798a792b68f9` |
| `EXP25A-run-windows.ps1` | `a10803295af96001379bf3b138b8494add739d9cf548fa5163c38ddd3eedac24` |
| `test_exp25a_offline.py` | `b0f62a8af6f744e25fcf84dbc5ce82aaf727158d08732b2232a5af6176912542` |
| `LEIA-ME-EXP25A.txt` | `087d680b128c4d7eb04fbb31dc48efa94613be04c5848d90fe767c9cb712193c` |

Adaptado do pacote EXP24/EXP19 com header Boot V3 e ferramenta AOSP `mkbootimg.py` revision fixada `f59f25d67f55ea6ee879678cfa1bfdd0be5f4019`, com validação do Git blob. Diferente da EXP24, verifica especificamente no ZIP CI as provas `exp25-touch-tests.log`, `exp25-touch-apply.log`, `exp25-touch-final-gate.log` e `exp25-touch-code.diff`. Os arquivos herdados de Ethernet mantêm exatamente os nomes `exp24-rtl8153-link-gate.txt`, `exp24-rtl8153-linked-symbols.txt` e `exp24-Image.sha256` no artefato da EXP25A. Falha fechada quando não encontra os nomes ou conteúdos esperados.

**Testes realizados no ambiente de preparação:** `python3 -m py_compile` para scripts Python; `test_exp25a_offline.py` testou cabeçalho Boot V3 sintético, alinhamento, preservação do ramdisk, controle byte-idêntico (`MATCH`), rejeição de SHA de controle ou `Image` incorretos, ausência de prova do `r8152`, entrada ZIP duplicada, ausência de saída do `mkbootimg` e proteção contra sobrescrita. Resultado `EXP25A OFFLINE SYNTHETIC: PASS`. **Não foi possível testar o boot original real no ambiente de preparação**, pois seus bytes privados estão apenas no computador do usuário; isto deve ser medido pelo script no Windows. O wrapper PowerShell não foi executado neste ambiente (sem `pwsh`).

## Próxima execução offline no Windows

1. Extrair ZIP de scripts em `C:\platform-tools\EXP25A-scripts`.
2. Manter o ZIP original de artefato em Downloads (não usar apenas `Image` extraída).
3. Executar:

```powershell
cd C:\platform-tools\EXP25A-scripts
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\EXP25A-run-windows.ps1 -FetchAosp
```

Se a ferramenta `mkbootimg.py` da EXP19 já estiver no disco, usar `-Mkbootimg 'C:\CAMINHO\mkbootimg.py'` em vez de `-FetchAosp`; opção HTTPS apenas consulta AOSP e valida SHA de origem. 

Saídas propostas: `C:\platform-tools\EXP25A-boot-prep\EXP25A-TOUCH-IRQ-NOT-FOR-FLASH.candidate.bin` e `EXP25A-TOUCH-IRQ-offline-audit.json`. Não repetir após sucesso sem conferir, pois o script recusa sobrescrever.

**Gates pendentes:** hash do candidato, round-trip original real em Windows, auditoria JSON, preparo do boot temporário separado, detecção física da IRQ após resume, firmware CSOT, Ethernet USB-C. A rotina de firmware CSOT da EXP25A permanece inalterada; IRQ corrigida somente em código. Preservar USB hub e mouse, sem troca de slot e **`FLASH_READY=false`**.

## 2026-10-18 — Empacotamento real no Windows: PASS

O usuário executou no Windows PowerShell 5.1 `EXP25A-run-windows.ps1 -FetchAosp` após verificar SHA-256 do ZIP de scripts `fd56cf4db1c51ab48b40535becc69143f73855e1f9e555c97cd3c6f6bf9566c9` e confirmar `EXP25A SCRIPT PARSER: PASS`. Python 3.12.10.

Saída literal dos gates:

```text
EXP25A AOSP_STOCK_ROUNDTRIP=MATCH
EXP25A_CANDIDATE=OFFLINE_CREATED_UNTESTED
EXP25A_CANDIDATE_SHA256=12100d94c8d2cc68ebc6a4424fff0ace659cd4e2299db144cd64f0bb65aa5604
EXP25A_CANDIDATE_BYTES=32477184
EXP25A_TOUCH_IRQ_CI_GATE=PASS
NOVATEK_FW_RECOVERY=UNCHANGED
RAMDISK_IDENTICAL=True
FLASH_READY=false
CANDIDATE=C:\platform-tools\EXP25A-boot-prep\EXP25A-TOUCH-IRQ-NOT-FOR-FLASH.candidate.bin
AUDIT=C:\platform-tools\EXP25A-boot-prep\EXP25A-TOUCH-IRQ-offline-audit.json
EXP25A OFFLINE GATE: PASS. NOT A TESTED BOOT IMAGE. FLASH_READY=false
```

**Interpretação:** o script de reempacotamento com AOSP oficial reproduziu o controle original byte a byte; gerou candidato de 32.477.184 bytes; nova Image SHA-256 já verificada separadamente contra o CI; preservou bytes do ramdisk. Tudo foi executado sem acessar dispositivo. O SHA-256 do candidato acima é reportado pelo processo; checagem independente pós-escrita pelo PowerShell ainda está pendente, bem como inspeção do JSON completo. Nenhum boot foi realizado na EXP25A. Testes touchscreen IRQ 521, firmware CSOT e Realtek pendentes. `FLASH_READY=false`.

**Gate seguinte:** reler candidato do disco e confirmar SHA+bytes, inspecionar JSON `result=OFFLINE_CANDIDATE_CREATED_UNTESTED`, `aosp_stock_roundtrip=MATCH`, `candidate_sha256`, `ramdisk_identical`, `cmdline_identical`, `os_word_identical`, `touch_irq_ci_gate=PASS`, `device_partitions_modified=false`, `FLASH_READY=false`. Não anexar backups privados. Qualquer boot experimental é somente via `fastboot boot <candidato>` depois de preflight do bootloader e disponibilidade operacional do hub/mouse. Nunca usar `flash`, `set_active`, `erase` ou `reboot` sem ter preparado a contingência.

## Gate Windows independente — 13/13 PASS

Em verificação independente posterior, o usuário confirmou no PowerShell com leitura de disco e JSON: `EXP25A CANDIDATE INTEGRITY: PASS`, 13/13 campos auditados `True`, `EXP25A BOOT V3 AUDIT: PASS`, `READY_FOR_TEMP_BOOT_REVIEW=PASS` e `FLASH_READY=false`.

Conferidos: candidato SHA-256 `12100d94c8d2cc68ebc6a4424fff0ace659cd4e2299db144cd64f0bb65aa5604`, 32.477.184 bytes, `candidate_kernel_sha256` igual ao SHA do CI, `result=OFFLINE_CANDIDATE_CREATED_UNTESTED`, `aosp_stock_roundtrip=MATCH`, `touch_irq_ci_gate=PASS`, `stock_header_version=3`, `ramdisk_identical=true`, `cmdline_identical=true`, `os_word_identical=true`, `vendor_boot_modified=false`, `device_partitions_modified=false`, `FLASH_READY=false`.

**Atenção ao campo `FLASH_READY: True` impresso no loop:** esse `True` apenas significa que o teste `($audit.FLASH_READY -eq $false)` retornou verdadeiro, e portanto o JSON continua registrando `FLASH_READY=false`. O resultado permite **revisar** um possível boot temporário, NÃO aprova flash nem atesta a segurança operacional da transição a fastboot.

**Pendente:** pré-condições operacionais do uso do tablet (mouse USB via hub como único acesso porque touch não funciona; confirmar Wi-Fi ADB ativo, identidade `pipa`, slot `_b`, recuperação viável) e inspeção física de troca do hub/USB antes de qualquer reboot; manter tudo conectado até haver plano seguro. Testes de boot, touch, CSOT, energia USB/RTL8153 não foram executados para EXP25A.

`FLASH_READY=false`.

## EXP25A — Preflight Wi-Fi ADB no pipa: PASS

O usuario executou no Windows, usando `C:\platform-tools\adb.exe` e serial TLS Wi-Fi `adb-6665d3e6-i745L2._adb-tls-connect._tcp`, os comandos somente leitura `get-state`, `getprop ro.product.device`, `getprop ro.boot.slot_suffix`, `getprop sys.boot_completed`, `uname -r`.

Resultados reportados: ADB= `device`; `DEVICE=pipa`; `SLOT=_b`; `BOOT_COMPLETED=1`; `KERNEL=5.10.404R`; `EXP25A PREFLIGHT READ-ONLY: PASS`; `FLASH_READY=false`.

Esta validacao confirma Android operacional e identidade declarada, **nao** prova que a EXP25A esta instalada/rodando. A diferenca `uname -r 5.10.404R` versus `/proc/version 4.19.404R` e conhecida de reportes anteriores, devendo permanecer documentada sem inferir troca de fonte, ate nova coleta read-only.

**Gate operacional ainda pendente:** o tablet esta com touchscreen sem resposta e o controle funcional depende exclusivamente de mouse receptor 2.4GHz via hub USB. Mudar a porta para fastboot por PC potencialmente interrompe o mouse e o ADB Wi-Fi; exigir contingencia de controle/recuperacao sem usar USB hub ou reboots ao vivo antes de autorizar ensaio `fastboot boot`. Recomendam-se apenas verificacoes read-only de `/proc/version`, status da bateria e topologia do receptor do mouse; nenhum `adb reboot bootloader`, `fastboot boot` ou flash nesta etapa.

`FLASH_READY=false`.

## ADB read-only: versao, bateria, receptor e fastboot do Windows

Nova coleta feita no dispositivo operacional por ADB Wi-Fi: `/proc/version` retornou `Linux version 4.19.404R (runner@runnervm8k3b6) (Android (14054515, ... Clang 21.0.0, LLD 21.0.0) #1 SMP PREEMPT Mon Oct 19 00:15:52 UTC 2026`. Isso corresponde à identificação de compilação/teste anterior EXP24; **não** à EXP25A recém-gerada, que ainda não foi inicializada.

`cat /proc/sys/kernel/osrelease` sem root retornou `Permission denied`. O `uname -r` da coleta precedente foi `5.10.404R`. A discrepância de apresentação versus `/proc/version` permanece; não inferir versão da árvore por apenas um deles.

`dumpsys battery`: AC=false, USB powered=true, wireless=false, dock=false, status=2 (carregando), level=56%, capacity level=3. O comando `su -c 'cat /proc/bus/input/devices' | Select-String Mouse|Receiver|32c2` retornou **nenhuma linha**; isso não prova que o dongle não esteja conectado, pois nome pode ser genérico, receptor HID aparecer como teclado ou haver falha de leitura. `fastboot --version` no Windows: `37.0.1-15733141`.

**Decisão:** parar antes de reboot/fastboot. Coletar passivamente nomes/handlers de todos os input devices e listagem USB (sem mudar hub) e exigir caminho de recuperação comprovado antes do teste físico. Preservar mouse 2,4GHz via hub. **`FLASH_READY=false`**.

## Nova coleta: osrelease root confirmado e mouse USB ausente da listagem de input

O usuário executou leituras somente leitura por ADB Wi-Fi no tablet pipa, slot `_b`, ainda no kernel experimental EXP24. Resultado de `su -c 'cat /proc/sys/kernel/osrelease'` = **`4.19.404R`**, concordando com `/proc/version` e divergindo do retorno anterior de `uname -r` = `5.10.404R`. A causa da divergência permanece não determinada; não inferir adulteração sem evidência.

Listagem filtrada de `su -c 'cat /proc/bus/input/devices'` exibiu: `xiaomi-touch event0`, `qpnp_pon event1`, `gpio-keys event2`, `xiaomi keyboard WakeUp event7`, `NVTCapacitiveTouchScreen event8`, `NVTCapacitivePen event9`, dispositivos `kona-mtp-snd-card` event3/4/5. Nenhum nome de `Mouse`, `Receiver` ou dispositivo adicional do receptor USB 2.4GHz apareceu. `dumpsys usb` filtrado por `32c2|0066|Mouse|Receiver|HID` só revelou `usb_charging=true` e `com.android.mtp.ReceiverActivity` (último pertence ao MTP, não ao receptor HID); **não houve prova de detecção do mouse USB no instante da coleta**.

O sinal `usb_charging=true` não prova que o host OTG esteja ativo, nem identifica o hub. Possibilidades incluem receptor temporariamente ausente, USB host desativado, perda de enumeração ou formato de relatório incompleto. Não afirmar causa sem dados adicionais.

**HARD GATE para qualquer boot:** confirmar se mouse 2.4GHz realmente está funcionando agora, e documentar capacidade de recuperação/controle do tablet caso ele não volte a funcionar depois de conectar o PC para entrar em fastboot. Mesmo sem aparecer nas listas de input, o usuário pode estar operando via outro mecanismo; não presumir falha física. Coletar somente leituras passivas de sysfs/dumpsys e não resetar controladores ou desligar host. Nenhuma autorização para `adb reboot bootloader`, `fastboot boot`, `fastboot flash`, mudança de slot ou energia USB. `FLASH_READY=false`.
