# EXP27.6 — Inventário passivo de touchscreen, mouse e IRQ (sem reinicialização)

## Razão do ciclo

A EXP27.5 terminou com o candidato EXP27.4 **íntegro** no Windows, ADB USB **um único dispositivo** `6665d3e6`, identidade EXP25A reconhecida, slot `_b` e Android inicializado. Na sequência foi perguntado se touchscreen e mouse USB respondem fisicamente; **o operador ainda não informou o resultado**. A existência dos dispositivos de entrada no kernel, ou o valor de uma IRQ, não comprova que o cursor e o toque funcionem na interface.

O novo programa `tools/exp27-6-input-readonly.py` faz somente inventário com ADB já autorizado. Não usa `fastboot`, `adb reboot`, `adb connect`, `getevent`, `input tap`, `su`, `dumpsys`, escrita em sysfs, desligamento de tela, root ou alterações USB-C/PD. Não grava arquivos na máquina local. Utiliza apenas comandos ADB com whitelist: `adb devices -l`, `getprop ro.product.device`, `getprop ro.boot.slot_suffix`, `getprop sys.boot_completed`, leitura de `/proc/version`, `/proc/sys/kernel/random/boot_id`, `/proc/bus/input/devices` e `/proc/interrupts`.

**Não usar este script como teste funcional.** Ele consulta nomes de dispositivos e handlers, e o contador acumulado da IRQ NVT (snapshot). Não mede geração de eventos durante toques; não comprova se o ponteiro se move na tela, mouse responde, firmware CSOT recupera após resume, nem estabilidade elétrica. Se faltar uma IRQ NVT ou mouse, o programa informa ausente na enumeração, sem concluir que o periférico está quebrado. Se houver mais de um dispositivo ADB autorizado, não envia `adb shell`: interrompe para evitar consultar o errado. Valida pipa, slot `_b`, Android iniciado, fingerprint EXP25A, e o boot_id no início e no fim; mostra só um digest curto, sem identificadores sensíveis.

## Execução simples no Windows

1. Baixar o ZIP do pacote oficial EXP27.6 quando o pipeline concluir PASS e extrair com **Extrair Tudo**.
2. Copiar o arquivo `tools\exp27-6-input-readonly.py` da pasta extraída para `C:\platform-tools\exp27-6-input-readonly.py`.
3. Deixar USB-C, carregador, mouse, teclado, hub, Ethernet e tablet **como já estão**, sem desconectar ou reiniciar.
4. No PowerShell, executar:

~~~powershell
py -3 "C:\platform-tools\exp27-6-input-readonly.py" --serial 6665d3e6
~~~

Retornar a saída de terminal sem editar. Se houver `EXP27_6_GATE=BLOCKED`, não repetir alterando slots, dispositivo, cabo ou hub. O comando não exige ZIP do kernel, nem acessa o candidato EXP27.4.

Interpretação:
- `EXP27_6_RESULT=READONLY_COLLECTION_PASS` é **coleta aprovada**; não é touch/mouse funcional confirmado.
- `NVT_OR_TOUCH_LABEL_PRESENT=True` indica um *nome heurístico* na lista de dispositivos, não eventos de toque.
- `MOUSE_HANDLER_PRESENT=True` indica `mouseN` no kernel, não que haja periférico acessível nem movimento de cursor.
- `NVT_IRQ_TOTAL` é contador **acumulado**, não delta medido e não é prova de toque.
- `SAME_BOOT_AS_EXP27_5=YES` indica digest de boot_id igual ao observado na EXP27.5. Se diferente, não assumir que o kernel ou USB reiniciou durante esta coleta; pode ser outra sessão histórica.
- `TOUCH_FUNCTIONAL=NOT_TESTED`, `MOUSE_FUNCTIONAL=NOT_TESTED`, `USB_PD_STABLE=NOT_TESTED` e `PHYSICAL_RECOVERY=PENDING` são saídas intencionais.

## Gate físico continua pendente

Para a EXP27.7, a **observação do operador** precisa confirmar separadamente se toque e movimento do mouse realmente respondem, e se existe caminho de controle após desconectar a **única porta USB-C**, que hoje é usada por hub/ADB e periféricos. Não induzir a situação arriscada só para comprovar esta fase. A prova histórica `fastboot boot` EXP25A não garante recuperação de um kernel que falhe antes do ADB nem que periféricos funcionem após trocar cabo.

**EXP27_5_OFFLINE=PASS; EXP27_5_ADB_USB_READONLY=PASS; EXP27_6_CI_SYNTHETIC=PENDING; EXP27_6_REAL_INPUT_INVENTORY=PENDING; PHYSICAL_RECOVERY=PENDING; TEMP_BOOT_AUTHORIZED=false; FLASH_READY=false.**


## Certificação CI e pacote Windows

O workflow [EXP27.6 run 40157077359](https://github.com/nywuer777/Pipa-Experimental-Kernel/actions/runs/40157077359) terminou com **success**: **12/12 testes sintéticos PASS**, compilação da sintaxe Python PASS, whitelist de leitura ADB PASS e `EXP27_6_DEVICE_COMMANDS_EXECUTED=NONE` no CI. Os testes usaram fixtures e mocks; **nenhuma consulta ao tablet real ocorreu durante a execução de Actions**.

Pacote para executar no computador do operador: `pipa-exp27-6-input-readonly-tools-1`, artifact ID **12585006817**. URL de download (GitHub autenticado):
https://github.com/nywuer777/Pipa-Experimental-Kernel/actions/runs/40157077359/artifacts/12585006817

Extrair ZIP, copiar `tools/exp27-6-input-readonly.py` para `C:\platform-tools\exp27-6-input-readonly.py` e executar comando de leitura na seção anterior. Logs/artefato contêm somente código, testes e instruções; **nenhum boot.img, backup ou dado privado do tablet**.

**Estado:** `EXP27_6_CI_SYNTHETIC=PASS`; `EXP27_6_REAL_INPUT_INVENTORY=PENDING_WINDOWS`; `TOUCHSCREEN_FUNCTIONAL=NOT_TESTED`; `MOUSE_FUNCTIONAL=NOT_TESTED`; `PHYSICAL_RECOVERY=PENDING`; `TEMP_BOOT_AUTHORIZED=false`; `FLASH_READY=false`.
