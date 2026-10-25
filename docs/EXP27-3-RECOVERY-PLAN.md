# EXP27.3 — Recuperação antes de qualquer boot experimental (pipa)

**Estado em 24/10/2026 (America/Sao_Paulo):** auditoria estática EXP27.3 PASS; boot EXP27.1 NÃO REALIZADO; recuperação real de emergência NÃO HOMOLOGADA; **FLASH_READY=false**.

## Fontes e artefatos imutáveis

- Tablet: Xiaomi Pad 6, codinome pipa, série Linux 4.19 com identificação personalizada 4.19.404R.
- Base E404: commit fed88a6024cd4d46c52eda607a95d97d7371ba81.
- EXP25A: touchscreen Novatek IRQ resume restaurado; driver Realtek r8152 v1.09.9; imagem kernel SHA-256 **2dac2dd05fe3cab8b167ea10bc632512c1508fa4d26db88d002837d0dc681e08**, run 39190015939.
- EXP27.1: atualização isolada r8152 v1.10.11, fonte Linux 5.4.290 blob 92b51c4c46f57b660f3053804ba74f6df9e71c76; compatibilidade de assinatura de dev_set_mac_address (3 argumentos para 2) ajustada na árvore de build E404; kernel Image SHA-256 **a14b536b471c97db877482afe97bcbeb97daa74ebc48a3a344d90ead57d56967**, run 40152429269.
- EXP27.2: hashes iguais de .config, DTB, DTBO, patch fonte Novatek e fingerprint Clang entre EXP25A e EXP27.1; run 40153757336, PASS.
- EXP27.3: ferramenta tools/exp27-3-release-gate.py compara os dois artefatos com SHA pinado, proveniência, link RTL8153, relatório independente EXP27.2 e ausência de arquivos boot.img / vendor_boot.img / vbmeta.img; run 40154083732, **STATIC_PASS**.

**A imagem de kernel Image não é um boot.img.** O boot-v3 EXP25A antigo, anteriormente auditado no Windows, tem SHA-256 12100d94c8d2cc68ebc6a4424fff0ace659cd4e2299db144cd64f0bb65aa5604. O controle stock compacto validado anteriormente tem SHA-256 202aaaf67fe5c0a963965c4e29f67866b509916e0bdff15dde38ef55b3d321e7. Nenhum deles é um candidato EXP27; a disponibilidade e integridade atuais no PC precisam ser novamente verificadas. **Ainda não foi produzido boot-v3 EXP27.1 neste ciclo.**

## Por que TEMP_BOOT_AUTHORIZED permanece falso?

1. O tablet possui uma porta USB-C; a comunicação fastboot via PC requer separar o hub que carrega mouse, teclado e Ethernet. Após possível boot falho, a reconexão de periféricos de contingência pode não funcionar imediatamente.
2. O kernel persistente original teve histórico de touchscreen inoperante. A EXP25A iniciou temporariamente via fastboot boot e restaurou eventos de toque, mas a homologação multiciclo foi interrompida em 2/6 ciclos aprovados devido à perda transitória de transporte ADB USB. Nenhum reboot do kernel ocorreu no intervalo da perda ADB, segundo boot_id observado.
3. Em 24/10, houve recuperação da Ethernet RTL8153 USB3 após troca de carregador USB-PD, e 12/12 amostras estáveis em SuperSpeed 5000 Mb/s e carrier 1 com a nova fonte. Não confundir isto com uma falha comprovadamente corrigida por r8152 v1.10.11.
4. Igualdade de DTB/.config/touch diff é integridade estática, não prova de estabilidade de suspensão, firmware Novatek, host USB ou negociação PD.
5. Retorno Android–fastboot–Android foi previamente homologado no cenário normal; recuperação de um kernel que não inicia não foi demonstrada. Não presumir que uma passagem normal valida todas as contingências.

## Gates de aceitação antes de um teste temporário futuro

- **INTEGRIDADE (PASS offline):** verificar SHA-256 exato de ambas as Image e igualdade de config/DTB/DTBO/diff touchscreen, com reporte do Actions preservado.
- **EMPACOTAMENTO (PENDING):** candidato EXP27 novo precisa de empacotamento offline Android Boot Header V3 auditado, preservando layout, cmdline, ramdisk e padding; não converter nem renomear Image em boot.img. Não usar a imagem EXP25A com driver antigo.
- **RECUPERAÇÃO (PENDING):** operador presencial com plano para usar Power/Volume Down, cabo USB-C de dados direto no PC, um único dispositivo pipa em fastboot e caminho comprovado para retornar ao Android com controle mesmo se touchscreen estiver inoperante. Avaliar risco do hub único e do kernel persistente; evidência anterior não substitui prova atual.
- **ESTADO ATUAL (PENDING):** sem reiniciar, conferir getprop device/slot/boot_completed, /proc/version (não se basear somente em uname -r devido a mascaramento E404), boot_id, NVT input e condição USB-PD/RTL8153. Comparar boot_id com a referência histórica somente se for a mesma sessão.
- **ENERGIA (PENDING):** permanecer no carregador estável; abortar em caso de queda Ethernet ou renegociação repetida USB-C/PD; NÃO reconectar carregador antigo para induzir falha.
- **DECISÃO POSTERIOR (PENDING):** somente depois das provas física/offline, aprovação específica para boot temporário via fastboot boot, jamais flash. Nenhum workflow ou script deve entrar no bootloader ou alterar o tablet automaticamente.

## Coleta opcional estritamente read-only no Termux, se a sessão estiver estável

Executar manualmente, SEM tocar nas conexões. Não altera interfaces nem partições:

    su -c '
    echo "=== EXP27.3 BASELINE READONLY ==="
    echo "DEVICE=$(getprop ro.product.device)"
    echo "SLOT=$(getprop ro.boot.slot_suffix)"
    echo "BOOT_COMPLETED=$(getprop sys.boot_completed)"
    echo "BOOT_ID=$(cat /proc/sys/kernel/random/boot_id)"
    echo "KERNEL=$(cat /proc/version)"
    echo "NVT=$(grep NVT-ts /proc/interrupts | head -n 1)"
    for d in 1-1.1 2-1.1; do
      p="/sys/bus/usb/devices/$d"
      if [ -d "$p" ]; then
        echo "$d=present speed=$(cat "$p/speed" 2>/dev/null)"
      else
        echo "$d=absent"
      fi
    done
    for f in real_type voltage_now; do
      p="/sys/class/power_supply/usb/$f"
      if [ -r "$p" ]; then echo "$f=$(cat "$p")"; fi
    done
    if [ -d /sys/class/net/eth0 ]; then
      echo "eth0_carrier=$(cat /sys/class/net/eth0/carrier 2>/dev/null)"
      echo "eth0_speed=$(cat /sys/class/net/eth0/speed 2>/dev/null)"
    else
      echo "eth0=absent"
    fi
    echo "EXP27.3_READONLY_DONE; FLASH_READY=false"
    '

## Possível homologação futura, somente após gate físico aprovado

Fases separadas e abortáveis: boot temporário de candidato EXP27 empacotado e auditado; prova de kernel realmente ativo e Android iniciado; validação do touchscreen e firmware Novatek; RTL8153 enumerado a USB 5000 Mb/s e link Ethernet 1000 Mb/s com alimentação comprovadamente estável; tráfego e monitoramento de erros; suspensão/retomada manual com controle físico e ADB alternativo; comparação A/B com EXP25A em condições equivalentes. Não provocar ciclos PD com carregador antigo.

Proibidos nesta fase: reiniciar o pipa, fastboot flash, erase, wipe, set_active, rebind/reset de hubs, escrever atributos USB-C/PD/VBUS, elevar limites elétricos, mudar carregador para reproduzir falha ou causar nova perda da sessão EXP25A.

**Resultado: EXP27_3_STATIC_GATE=STATIC_PASS; PHYSICAL_RECOVERY=PENDING; EXP27_RUNTIME_TEST=NOT_RUN; TEMP_BOOT_AUTHORIZED=false; FLASH_READY=false.**
