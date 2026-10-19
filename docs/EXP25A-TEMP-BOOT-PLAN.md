# EXP25A — Plano de boot temporário condicionado, SEM FLASH

## Estado concluído

- CI EXP25A #39190015939 success, Image SHA256 2dac2dd05fe3cab8b167ea10bc632512c1508fa4d26db88d002837d0dc681e08.
- Candidato Boot V3 Windows: C:\platform-tools\EXP25A-boot-prep\EXP25A-TOUCH-IRQ-NOT-FOR-FLASH.candidate.bin, 32.477.184 bytes, SHA256 12100d94c8d2cc68ebc6a4424fff0ace659cd4e2299db144cd64f0bb65aa5604; auditoria offline 13/13 PASS.
- Controle stock validado: C:\platform-tools\pipa_preflight\boot_b-stock-compact-control.img, SHA256 202aaaf67fe5c0a963965c4e29f67866b509916e0bdff15dde38ef55b3d321e7.
- Pipa, slot b, boot_completed=1, /proc/version e /proc/sys/kernel/osrelease = 4.19.404R; uname -r reportou 5.10.404R, discrepância registrada.
- O usuário desconectou voluntariamente o hub: ausência de dongle HID na coleta não indica nova falha USB.

## Gate operacional obrigatório

O touchscreen permanece inoperante em EXP24, e o tablet depende de mouse 2.4GHz conectado ao hub. A reconexão do hub/mouse *depois* de um ciclo fastboot ainda não foi comprovada. Antes de reiniciar, operador presencial precisa comprovar que consegue conectar o hub e usar o mouse e que possui cabo USB-C direto para computador e contingência com botões físicos caso boot falhe. ADB Wi-Fi não funciona no bootloader. Não automatizar reconexão/reset de USB nem retirar controle funcional sem contingência. Se a prova física falhar, não reiniciar.

Apenas após cumprir esses gates, pode-se considerar fastboot boot <arquivo candidato> como teste temporário em RAM; é vedado fastboot flash, set_active, erase, wipe e qualquer escrita nas partições. Em fastboot exija um único dispositivo Windows, product=pipa, current-slot=b, unlocked=yes e is-userspace=no; abortar em qualquer diferença.

## Contingência

No bootloader com fastboot funcionando no PC, fastboot reboot reinicia a imagem persistente. Xiaomi publica reinício forçado por Power 10–15 s e pipa aceita Power + Volume Down para acessar fastboot quando desligado. Isso não comprova recuperação em todo cenário de travamento. Não entrar em recovery para apagar dados.

Fontes: https://www.mi.com/global/support/faq/details/KA-557238/ e https://github.com/AxionAOSP/official_devices/blob/main/Wiki/pipa.md.

## Coleta pós-boot preparada

EXP25A-postboot-diagnostico.ps1, SHA256 8edc95b553c834a2f422a174c812eac49d0b87669e59a5f1e9044d2107f411a2, arquivado como anexo na conversa. Somente ADB Wi-Fi read-only; valida pipa, slot b, boot e NVT event8; coleta IRQ do NVT antes/depois de 12 segundos de toque físico e após transição de tela por botão Power efetuada manualmente, e filtra últimas 180 linhas NVT/firmware. Revisão estática OK; PowerShell Windows ainda não executado. Preserva USB/hub e partições.

STATUS: OFFLINE_BUILD_AND_REPACK=PASS; READONLY_WIFI_PREFLIGHT=PASS; MOUSE_RECOVERY_GATE=PENDING; TEMP_BOOT=NOT_RUN; TOUCH_FIXED=UNPROVEN; FLASH_READY=false.
