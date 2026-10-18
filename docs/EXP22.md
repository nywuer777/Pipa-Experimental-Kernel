## EXP22 — HOMOLOGAÇÃO REAL DOS ARQUIVOS E FASTBOOT (18/10/2026)

O usuário executou no Windows a auditoria de tamanho/SHA-256 dos dois arquivos relevantes com resultado:

```text
PASS: boot_b.img tamanho=201326592 SHA256=31F57CDED5FA4B37426B4387B58C1C7330703A1C1A8A5AA584B348FCBB78C2F4
PASS: EXP19-EXP06-NOT-FOR-FLASH.candidate.bin tamanho=32206848 SHA256=30065A39BE707D836594DA574BE11B08C0228018CA91A681E1B122E6F0E6F60C
EXP22 LOCAL FILES: PASS
```

Posteriormente, o usuário executou `adb reboot bootloader`, comprovou comunicação com `fastboot devices -l` e obteve todos os `getvar` com `EXIT_CODE=0`:

```text
product: pipa
current-slot: b
is-userspace: no
unlocked: yes
partition-size:boot_b: 0xC000000
partition-type:boot_b: raw
max-download-size: 805306368
fastboot reboot: Rebooting OKAY
```

**Decodificação verificada:** `0xC000000=201326592` bytes (192 MiB), **exatamente** o tamanho do `boot_b.img` de backup. `max-download-size=805306368` bytes (768 MiB); backup B de 192 MiB e candidato EXP06 compacto de 32.206.848 bytes estão abaixo desse limite nominal. Essa correspondência **não** demonstra que gravar 192 MiB na partição seja seguro nem que boot temporário seja suportado. `partition-type:boot_b=raw` refere-se à apresentação da partição pelo bootloader.

**Resultado real:** `EXP22_ORIGINAL_AND_CANDIDATE_FILES=PASS_REAL`, `EXP22_FASTBOOT_IDENTITY_AND_TARGET=PASS_REAL`, `EXP22_FASTBOOT_REBOOT_COMMAND=OKAY`. **Ainda não existe saída `adb devices -l` posterior ao `fastboot reboot` desta rodada**, então registrar retorno total ao Android como `NOT_CONFIRMED_THIS_RUN` (embora EXP18.3 e EXP21.3 já o tenham provado previamente).

**Limites:** suporte real de `fastboot boot <imagem>` continua `UNKNOWN`; sinais AVB Android `green/locked` divergem do Fastboot `unlocked=yes`, cinco descritores HASH do VBMeta A/B divergem das imagens atuais e o rollback por escrita após boot falho não foi testado. **Nenhum flash, boot de imagem, troca de slot ou alteração de partição foi realizado.** Estratégia recomendada: preferir teste temporário com controle original **somente após confirmar riscos e suporte da implementação específica**, sob aprovação explícita; não converter PASS read-only em autorização de flash.

**Portão seguinte estritamente sem flash:** confirmar retorno ao Android `_b` e documentar as condições materiais de emergência (acesso por teclas ao bootloader se Android não inicia, cabos/portas, disponibilidade dos arquivos de backup e Windows), bem como consultar compatibilidade do modelo com boot temporário a partir de fontes confiáveis. Se não houver suporte comprovado, escolher em conjunto se risco de primeira escrita experimental pode ser aceito; `FLASH_READY=false` até essa decisão.

# EXP22 — Portão de recuperação e decisão do primeiro boot EXP06

**Data:** 18/10/2026. **Escopo:** preparação estritamente *pré-experimento*. **NENHUM FLASH, BOOT DE IMAGEM, ALTERAÇÃO DE SLOT OU DESBLOQUEIO AUTORIZADO NESTA ETAPA.** `FLASH_READY=false`.

## Evidências consolidadas

- EXP06: kernel Clang21 `Image` 30.349.336 bytes SHA256 `7b3c971a6bd92e8e609e4c56fb6e33df78a7668463e9bcfc342aa1cdee9a0033`, modificação schedutil controlada.
- EXP19/20: candidato EXP06 compacto AOSP 32.206.848 bytes, SHA256 `30065a39be707d836594da574be11b08c0228018ca91a681e1b122e6f0e6f60c`, correspondência byte-a-byte das partes não-kernel e digest virtual da partição inteira `c50a7b4d8447426331adbfae9296439a957069c0860a1d36d476b63aae083f00`.
- EXP12: imagem original `boot_b.img` 201.326.592 bytes SHA256 `31f57cded5fa4b37426b4387b58c1c7330703a1c1a8a5aa584b348fcbb78c2f4`; compact original reproduzido oficialmente com 32.206.848 bytes SHA256 `202aaaf67fe5c0a963965c4e29f67866b509916e0bdff15dde38ef55b3d321e7`.
- EXP18.2: Fastboot do bootloader `product=pipa`, `is-userspace=no`, `current-slot=b`, `slot-count=2`, `unlocked=yes`; driver Windows funcional.
- EXP18.3/21.3: `fastboot reboot` e reconexão real ADB no Android slot `_b`, `pipa`.
- EXP21.2: A/B ambos `successful=yes`, `unbootable=no`, `retry-count=6`. **Não comprova fallback bootável**, nem recuperação automática após trocar só o kernel. O AOSP informa que quando há atualização/set_active flags de sucesso e retry podem ser resetadas, variando o fluxo; não supor fallback automático sem inspecionar resposta real. Fonte https://source.android.com/docs/core/architecture/bootloader/updating .
- EXP21.8D: backups `boot_a/vendor_boot_a/dtbo_a/vbmeta_a` preservados no Windows, SHA256 iguais às leituras on-device da EXP21.8B.
- EXP21.8E: oito imagens A/B com hashes fixados, parsers de boot v3, vendor_boot v3, DTBO e VBMeta concluídos.
- EXP21.8F: 6 descritores AVB com salt testados, **1 MATCH e 5 MISMATCH**, inclusive B original `boot` e `vendor_boot` divergentes.
- EXP21.8G: VBMeta A e B com `HEADER_AUX_HASH=MATCH`, `SELF_RSA4096_SIGNATURE=VALID` em ambos e **mesma chave embutida**, fingerprint SHA256 `7728e30f50bfa5cea165f473175a08803f6a8346642b5aa10913e9d9e6defef6`; hash blob assinado B `f6a9a87fa3187d6c2d544d724c1c0e4a36a2c365dec1b2ab86f91f16178e3c9c`, igual à propriedade Android. Autoassinatura correta **não** prova confiança OEM na chave nem aceitação de kernel modificado.
- Inconsistência ativa: bootloader `unlocked=yes` versus Android `verifiedbootstate=green`, `device_state=locked`, `flash.locked=1`. AOSP estabelece normalmente `green` em LOCKED e `orange` em UNLOCKED; não inferir política no dispositivo com esse conflito. Fonte https://source.android.com/docs/security/features/verifiedboot/boot-flow .

## O que falta para autorização de teste

**Primeiro, concluir apenas duas ações sem alteração de partições:**

1. **Auditar a fonte de restauração local**: confirmar existência e hashes `C:\platform-tools\pipa_backup\boot_b.img` e `C:\Users\User\Downloads\EXP19-output\EXP19-EXP06-NOT-FOR-FLASH.candidate.bin`; verificar espaço livre no PC e integridade da cópia alternativa, manter todos os backups A e B fora do diretório de teste.
2. **Conferir capacidades Fastboot do bootloader** com consultas `getvar`, explicitamente `partition-size:boot_b`, `partition-type:boot_b`, `max-download-size`, `current-slot`, `is-userspace`, `unlocked`, `product`, além de `devices -l`. Resultado não suportado (`FAIL/unknown variable`) significa **UNKNOWN**, não `no`. **Nenhum comando de boot temporário pode ser testado por `getvar` de modo conclusivo**; suporte depende da implementação do bootloader.
3. Definir plano de contingência que **não dependa de inicializar Android nem trocar para A**: acesso físico ao modo bootloader pelas teclas em caso de kernel B que não inicia, cabo/porta/driver e Fastboot no Windows, original `boot_b.img` com SHA256 fixado, passo de restauração `boot_b` **somente depois de confirmar o alvo e aceitar explicitamente a operação de escrita**. Uma restauração não foi executada: `BROKEN_BOOT_RECOVERY=UNTESTED`.
4. Selecionar primeira tentativa: **preferência por caminho temporário/não persistente** somente se a implementação do bootloader o suportar e for avaliada segura, com teste primeiro usando imagem original compacta (não EXP06) mediante aprovação explícita. Alternativa é escrita controlada no `boot_b` sob aceitação consciente de risco e plano de restauração. Não fabricar suporte de `fastboot boot` a partir do fato de o cliente Windows aceitar o comando.
5. **Não usar slot A como segurança comprovada:** ambas as cópias de inicialização A e B estão salvas, mas nenhum teste de boot de A nem compatibilidade com `system/vendor` foi feito.

## Comandos — apenas leitura / sem operações de boot sobre uma imagem

### A. Windows, Android funcionando

```powershell
$original = "C:\platform-tools\pipa_backup\boot_b.img"
$candidate = "$env:USERPROFILE\Downloads\EXP19-output\EXP19-EXP06-NOT-FOR-FLASH.candidate.bin"
foreach ($path in @($original, $candidate)) {
  if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Arquivo ausente: $path" }
  Get-Item -LiteralPath $path | Select-Object FullName, Length
  Get-FileHash -LiteralPath $path -Algorithm SHA256 | Select-Object Path, Hash
}
```

Critérios:
`boot_b.img` **201326592 bytes** e hash `31f57cded5fa4b37426b4387b58c1c7330703a1c1a8a5aa584b348fcbb78c2f4`; candidato compacto **32206848 bytes** e hash `30065a39be707d836594da574be11b08c0228018ca91a681e1b122e6f0e6f60c`. Interromper em qualquer divergência.

### B. Fastboot do bootloader, ainda sem alteração

Após entrar em Fastboot do bootloader (operação previamente repetida sem problema), consultar somente:

```powershell
$fb = "C:\platform-tools\fastboot.exe"
& $fb devices -l
foreach ($v in @("product","current-slot","is-userspace","unlocked","partition-size:boot_b","partition-type:boot_b","max-download-size")) {
  Write-Output "=== $v ==="
  & $fb getvar $v
  Write-Output "EXIT_CODE=$LASTEXITCODE"
}
```

Retornar com `fastboot reboot` e verificar Android `pipa`, slot `_b`. **Esse reboot normal já foi homologado duas vezes em fases anteriores; repetir somente se for entrar de novo para conferir variáveis.**

### C. Procedimento de restauração a desenhar, NÃO EXECUTAR

Se uma futura tentativa autorizada de EXP06 impedir Android iniciar, será necessário verificar que o Fastboot continua acessível mesmo sem Android, checar `product/current-slot`, confirmar SHA256 do original e decidir como restaurar a partição `boot_b`. Isso implicará **escrita permanente** e deverá ter comando auditado, alvo explícito, backup fora do tablet e aprovação específica do usuário naquele momento. Não publicar comando de flash como comando de preparação ou teste passivo.

## Gatilhos de PARADA

- Backup `boot_b.img` ausente/divergente; candidato EXP06 divergente.
- Variáveis de identidade `product` ou slot diferentes do esperado.
- Fastboot não acessível de modo estável ou `boot_b` não resolvível como partição no bootloader.
- Sem estratégia plausível de retorno ao Fastboot no caso de falha de kernel e sem aceitação explícita do risco.
- Qualquer tentativa de `fastboot flash`, `fastboot boot`, `set_active`, `flashing unlock/lock`, `erase` fora de aprovação específica.

## Critério de saída

`EXP22_RECOVERY_PREPARATION=PASS` requer evidência de arquivos fixados e Fastboot read-only, mais procedimento humano de contingência revisado. **Mesmo `PASS` não equivale a `BROKEN_BOOT_RECOVERY=TESTED` nem torna `FLASH_READY=true` automaticamente.** Uma primeira execução com imagem só poderá ocorrer depois de escolher rota, validar suas limitações e receber autorização explícita.

**Estado antes de novas provas:** `EXP21.8G=PASS_REAL`; `EXP22_RECOVERY_PLAN=PREPARED_READ_ONLY_GATES_PASS`; `FLASH_READY=false`.
