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
