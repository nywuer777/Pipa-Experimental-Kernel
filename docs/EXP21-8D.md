# EXP21.8D — Preservação binária do slot A no Windows, sem gravar no tablet

**Data:** 2026-10-18 | **Fase anterior:** `EXP21.8C_HEADER_MAGIC=PASS_REAL`; quatro cabeçalhos reconhecidos, hashes reais A medidos por KernelSU em EXP21.8B, Android no slot `_b`. **`FLASH_READY=false`.**

## Objetivo e limite

Preservar **uma cópia Windows binariamente idêntica** de `boot_a`, `vendor_boot_a`, `dtbo_a` e `vbmeta_a`, sem flash, reboot, montagem RW ou mudança de slot. A leitura total planejada soma **335.675.392 bytes** e exige acesso temporário root via KernelSU (já confirmado em EXP21.7); os dados transitam via `adb exec-out` e são escritos no **disco do Windows**, não nas partições do tablet. Essa operação de backup é **opcional** e deve ser executada voluntariamente pelo usuário. O software não assume que o A é inicializável.

Em Windows PowerShell 5.1, NÃO usar redirecionamento `>` para saída binária do ADB; o shell pode converter bytes. A implementação usa `subprocess.Popen(..., stdout=PIPE)` do Python em modo binário, com verificação de comprimento/identidade/offset dos primeiros bytes e SHA-256 integral após streaming. As imagens são escritas em arquivos temporários locais e só publicadas após todas as verificações da imagem correspondente. Cada imagem previamente existente é verificada e nunca sobrescrita; falhas param a execução e removem o arquivo parcial da partição corrente.

**Portões antes da cópia:** `adb shell getprop ro.product.device=pipa`; `ro.boot.slot_suffix=_b`; `adb shell su -c id` com `uid=0(root)`; pré-leitura de 64 bytes e comparação EXATA com EXP21.8C. O script não contém comandos de mudança de slot, fastboot, reboot, `dd`/escrita no Android ou acesso a userdata.

## Artefato gerado e testes locais

`PipaExperimental-EXP21-8D-slot-a-backup.zip` — SHA256 **`ccd7da94d4d96203ac66fff139c95518d5364b21c66da314f51722d57c89fbb8`**.

| Arquivo dentro do ZIP | SHA-256 |
| --- | --- |
| `EXP21-8D/EXP21-8D-slot-a-backup.py` | `b79446e46a49dd780ceeab32a0251dc2b3a288798e72df13b250fbc0b8bfc67e` |
| `EXP21-8D/EXP21-8D-LEIA-ME.txt` | `e27a6a8711fe1f338554a58625abf8672802aca968140c22ced5c4d4050087eb` |

**Testado localmente pelo assistente:** Python `py_compile` PASS, autoteste sintético de dados binários/hashing PASS, conferência de ZIP e hashes PASS. **Não testado:** comunicação `adb exec-out` com o tablet real, streaming integral de blocos A, checagem independente das imagens recebidas no Windows. Não afirmar `BACKUP_A=PASS` até receber saída do dispositivo real.

## Execução opcional pelo usuário — Windows PowerShell

```powershell
Expand-Archive `
  -LiteralPath "$env:USERPROFILE\Downloads\PipaExperimental-EXP21-8D-slot-a-backup.zip" `
  -DestinationPath "$env:USERPROFILE\Downloads" `
  -Force

python "$env:USERPROFILE\Downloads\EXP21-8D\EXP21-8D-slot-a-backup.py" --self-test

python "$env:USERPROFILE\Downloads\EXP21-8D\EXP21-8D-slot-a-backup.py" `
  --out "C:\platform-tools\pipa_backup_a"
```

Reservar pelo menos **400 MiB livres** no Windows. Confirmar permissão KernelSU se solicitada; se negar, o script interrompe sem leitura integral. Se houver `STREAM` falho, `HEADER_PROBE` diferente ou SHA256/tamanho divergente, interromper e auditar antes de prosseguir.

### Hashes do slot A homologados em EXP21.8B

| Partição A | Tamanho esperado | SHA256 esperado |
| --- | ---: | --- |
| `boot_a` | 201326592 | `5c4f51f70132ca01b183da2a3fb27446bfacdfcc035385d83d8b3c4339b2ad97` |
| `vendor_boot_a` | 100663296 | `267e0445174c9c53d7154677644fe82947053daaac2f855aa3fa54968e803346` |
| `dtbo_a` | 33554432 | `0ec73d9af213f02675f9b11201b890874baa51f7ec2bb554dd57d2be037ada27` |
| `vbmeta_a` | 131072 | `b2a60ea8249203b392db63a88ac1b39b5156d796ed3a6b5757dd5e787fb6948a` |

**Pós-preservação (gate futuro):** examinar offline as imagens A efetivamente copiadas, validar formato AVB (incluindo `flags`, descritores, assinatura e chave reconhecida), comparar DTB/DTBO e componentes de boot, pesquisar compatibilidade com firmware/partições lógicas de A e confirmar estratégia de restauração de `_b`. Mesmo cópias A verificadas não são prova de um boot de emergência bem-sucedido.

`EXP21.8D_BACKUP_SLOT_A=NOT_EXECUTED_ON_DEVICE`; `SLOT_A_RECOVERY=UNPROVEN`; **`FLASH_READY=false`**.
