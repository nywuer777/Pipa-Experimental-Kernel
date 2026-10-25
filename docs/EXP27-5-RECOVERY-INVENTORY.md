# EXP27.5 — Auditoria independente offline + inventário ADB opcional (SEM BOOT)

## Escopo

Nesta fase não se testa kernel novo no tablet. O objetivo é conferir por um segundo parser independente o candidato Boot V3 EXP27.4 já criado e o ZIP oficial do build, e preparar informação de estado **sem comprometer a sessão Android atual**. Não temos como comprovar por software, nesta etapa, que o operador conseguirá recuperar um aparelho que não inicializa; por isso o gate físico continua pendente.

Entradas verificadas anteriormente no PC do operador:

- Controle: `C:\platform-tools\pipa_preflight\boot_b-stock-compact-control.img`, SHA256 **202aaaf67fe5c0a963965c4e29f67866b509916e0bdff15dde38ef55b3d321e7**, 32206848 bytes.
- Candidato: `C:\platform-tools\EXP27.4-boot-prep\EXP27.4-RTL8153-NOT-FOR-FLASH.candidate.bin`, SHA256 **df9eb41441770035849e95a6e54ccc110357d5c171a06758cc2df60a192a01d7**, 32411648 bytes.
- Relatório: `C:\platform-tools\EXP27.4-boot-prep\EXP27.4-offline-audit.json`, criado no empacotamento EXP27.4 e validado por PowerShell em 11/11 verificações.
- ZIP Actions: `%USERPROFILE%\Downloads\pipa-exp27-r8152-v11011-clang21-3.zip`; `Image` SHA256 **a14b536b471c97db877482afe97bcbeb97daa74ebc48a3a344d90ead57d56967**.

O script `tools/exp27-5-recovery-inventory.py` usa somente biblioteca padrão Python, conferindo SHA de cada entrada, a origem pinada r8152 e gates de link/Novatek. Ele **desmonta independentemente** stock e candidato, verifica estrutura Boot v3, páginas de alinhamento, preservação de TODO o cabeçalho salvo kernel_size, ramdisk byte-idêntico e a presença exata dos bytes da Image do Actions dentro do candidato. Diferente de simplesmente confiar nas flags JSON produzidas no empacotamento.

## Executar no Windows: estágio A, inteiramente offline (padrão)

1. Baixar o pacote de ferramentas EXP27.5 do GitHub Actions quando aprovado, extrair, copiar `tools\exp27-5-recovery-inventory.py` para `C:\platform-tools\exp27-5-recovery-inventory.py`.
2. Manter backup original, candidato EXP27.4, JSON e ZIP EXP27.1 nos mesmos locais já conferidos. **Não reexecutar o empacotador, não excluir pastas e não renomear arquivos.**
3. Abrir PowerShell e executar **somente** o comando:

~~~powershell
py -3 "C:\platform-tools\exp27-5-recovery-inventory.py"
~~~

Se todos os arquivos forem íntegros, surgirão linhas `EXP27.5_OFFLINE_INDEPENDENT_CHECK=PASS`, `BOOT_V3_HEADERS_AND_RAMDISK=PASS`, `CANDIDATE_IMAGE_CI_BYTE_MATCH=PASS` e `EXP27.5_ANDROID_READONLY=NOT_REQUESTED`. O programa não escreve um novo arquivo nem solicita ADB neste modo. Se aparecer `EXP27.5_GATE=BLOCKED`, parar e enviar a mensagem.

## Estágio B: ADB leitura opcional, apenas depois do estágio A

**NÃO é necessário para homologar a integridade offline.** Este modo acessa uma sessão ADB **já conectada e autorizada**. Não executa `adb connect`, `su`, `fastboot`, `reboot`, `adb push`, nem altera sysfs, USB, USB-PD ou partições.

~~~powershell
py -3 "C:\platform-tools\exp27-5-recovery-inventory.py" --observe-android
~~~

Para proteger o tablet, ele aborta ANTES de qualquer `adb shell` se houver múltiplos transportes autorizados. Por exemplo, podem aparecer ADB USB e ADB Wi-Fi simultaneamente; nesse caso, não desconectar nada e não escolher um dispositivo no chute. Registrar o bloqueio e revisar os transportes por procedimento separado. Quando houver só um transporte, valida `pipa`, slot `_b`, boot concluído, lê `/proc/version` e `boot_id` e mostra versão classificada, **sem expor serial, cmdline ou boot_id bruto**.

Não confundir a saída `EXP27.5_ANDROID_READONLY=PASS` com prova de funcionalidade touch, USB-C/PD ou rollback em pane de boot. Não pedir mudança de carregador ou hub para esse teste.

## Segurança

- EXP25A funcional preservada; o E404 persistente tem histórico de falha de touchscreen.
- Os testes anteriores confirmaram 2/6 ciclos de suspensão/retomada antes de interrupção temporária de ADB, e a perda ADB ocorreu sem reboot do kernel.
- Energia/cabo/hub atuais estáveis: não mudar, resetar, rebind, force roles ou elevar corrente USB-C.
- **Jamais rodar fastboot boot, flash, erase, set_active, reboot ou alternar slot nesta fase.**
- O plano de recuperação operacional, presença física, controle alternativo e risco de perder os periféricos pela única porta USB-C precisam de aceitação separada.
- Saídas: `EXP27_5_OFFLINE=PASS|BLOCKED`; `ANDROID_READONLY=NOT_REQUESTED|PASS|BLOCKED`; `PHYSICAL_RECOVERY=PENDING`; `TEMP_BOOT_AUTHORIZED=false`; `FLASH_READY=false`.

O pacote de ferramentas inclui **apenas código, testes e documentação**. Nenhum kernel, boot image nem backup privado deve ser anexado ao pacote.


## Execução CI confirmada e pacote para Windows

A execução GitHub Actions `40156271942` concluiu com **success**. Os **12 testes sintéticos passaram** (incluindo parser de Boot V3, detecção de corrupção no kernel/header/ramdisk, spoofing de JSON, ZIP duplicado, múltiplos transportes ADB e rejeição de serial suspeito). **Nenhuma consulta Android real foi executada** nesse runner; são testes sintéticos.

Pacote de ferramentas produzido: **`pipa-exp27-5-windows-safe-audit-1`**, artifact ID `12584119676`, URL:
https://github.com/nywuer777/Pipa-Experimental-Kernel/actions/runs/40156271942/artifacts/12584119676

Extrair em Downloads (ZIP) e copiar `tools\exp27-5-recovery-inventory.py` para `C:\platform-tools\exp27-5-recovery-inventory.py`. Não alterar arquivos EXP27.4 já validados; executar primeiro o modo **offline padrão** sem `--observe-android`. Após receber a saída do Windows, avaliar se vale coleta ADB opcional, mantendo `FLASH_READY=false`.
