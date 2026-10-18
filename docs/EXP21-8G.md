## EXP21.8G — HOMOLOGAÇÃO REAL CRIPTOGRÁFICA OFFLINE (18/10/2026)

Usuário executou `--self-test` em Windows com resultado `EXP21.8G SYNTHETIC SIGNED VBMeta SHA256_RSA4096 SELFTEST: PASS`, seguido da auditoria real das oito imagens A/B. Todas as entradas tiveram `SHA256=PASS`; o script analisou os dois VBMETA originais e emitiu:

```text
VBMETA_A ALGORITHM=SHA256_RSA4096 FLAGS=3 ROLLBACK=0 RELEASE=avbtool 1.3.0
VBMETA_A HEADER_AUX_HASH=MATCH
DECLARED=e243b8d1458201f4a7458c5d6b0397ede8d92921113272a496a368153621d7ca
CALCULATED=e243b8d1458201f4a7458c5d6b0397ede8d92921113272a496a368153621d7ca
VBMETA_A SELF_RSA4096_SIGNATURE=VALID
VBMETA_A PUBLIC_KEY_BLOB_SHA256=7728e30f50bfa5cea165f473175a08803f6a8346642b5aa10913e9d9e6defef6
VBMETA_A MODULUS_SHA256=36949b827927c883836897ab67eb01360795186cb81faca37ef7de583a1b65b1
VBMETA_A SIGNED_BLOB_SHA256=810a8dfa0dbb80074b60730a72108b5bcdb2eadaa434f6c43e209c9b92977a42
VBMETA_B ALGORITHM=SHA256_RSA4096 FLAGS=3 ROLLBACK=0 RELEASE=avbtool 1.3.0
VBMETA_B HEADER_AUX_HASH=MATCH
DECLARED=175c430d64403d61eeb90995c4d4fccfd72e071a365723ff820602ae9132cd64
CALCULATED=175c430d64403d61eeb90995c4d4fccfd72e071a365723ff820602ae9132cd64
VBMETA_B SELF_RSA4096_SIGNATURE=VALID
VBMETA_B PUBLIC_KEY_BLOB_SHA256=7728e30f50bfa5cea165f473175a08803f6a8346642b5aa10913e9d9e6defef6
VBMETA_B MODULUS_SHA256=36949b827927c883836897ab67eb01360795186cb81faca37ef7de583a1b65b1
VBMETA_B SIGNED_BLOB_SHA256=f6a9a87fa3187d6c2d544d724c1c0e4a36a2c365dec1b2ab86f91f16178e3c9c
KEY_A_EQUALS_B=true
VBMETA_B_BLOB_SHA256_MATCHES_PRIOR_ANDROID_PROPERTY=true
EXP21.8G AVB SELF-SIGNATURE AUDIT: COMPLETE valid=2 invalid=0
NO DEVICE ACCESS. NO FILE WRITTEN. FLASH_READY=false
```

**Veredicto:** `EXP21.8G_REAL_RSA4096_SELF_SIGNATURE=PASS_REAL`, duas assinaturas internas válidas relativamente à mesma chave RSA4096 **embutida** nos blobs VBMeta; `HEADER_AUX_HASH=MATCH` em ambas. O digest do VBMeta B dos 5184 bytes coincide com a propriedade Android da EXP13.3. **Isso não prova** chave de confiança OEM, validade dos 5 descritores de partição `MISMATCH` na EXP21.8F, aceite de nova imagem modificada, rollback efetivo, mecanismo de recuperação ou possibilidade de boot temporário.

**Marco técnico de encerramento das auditorias offline preliminares:** EXP12–21.8G geraram cópias A/B com hashes fixados, o candidato EXP06 AOSP com identidade de kernel e bytes não-kernel preservados, e auditorias estruturais/criptográficas reprodutíveis. Não há justificativa para exigir sucessivas leituras de pequenos campos como pré-requisito universal de boot; focalizar **EXP22 — plano de restauração e portão Fastboot somente leitura**, sem ações de flash até uma autorização explícita e avaliação do risco. AOSP referência A/B https://source.android.com/docs/core/ota/ab/ab_implement e Verified Boot https://source.android.com/docs/security/features/verifiedboot/boot-flow .

**Estado:** `SLOT_A_RECOVERY=UNPROVEN`, `BROKEN_BOOT_RECOVERY=UNTESTED`, `AVB_BOOTLOADER_TRUST=UNKNOWN`, `FLASH_READY=false`.

# EXP21.8G — Auditoria criptográfica offline da própria assinatura VBMeta A/B

**Data:** 18/10/2026 | **Entrada homologada:** EXP21.8F `PASS_REAL`, oito backups SHA256 de A/B aprovados. Descritores AVB: seis comparados, **um MATCH** (`dtbo_b`) e **cinco MISMATCH**. **`FLASH_READY=false`.**

## Objetivo e fonte AOSP

Distinguir a coerência de **assinatura/hash do próprio blob VBMeta** da coerência dos **descritores de HASH das imagens** e da aceitação efetiva da **chave de confiança do bootloader**. O algoritmo AVB `algorithm_type=2` corresponde a `SHA256_RSA4096`. O `avbtool` oficial calcula `SHA256(header[0:256] || auxiliary_data)` para comparar o hash armazenado e valida a assinatura RSA4096/PKCS#1 v1.5 desse digest contra a chave pública embutida no próprio VBMeta. Essa validação é **autoassinatura** e nunca confirma que a chave seja confiável para o fabricante ou bootloader.

Fonte oficial direta: https://android.googlesource.com/platform/external/avb/+/refs/heads/main/avbtool.py (`verify_vbmeta_signature`, `ALGORITHMS`), e layout de cabeçalho: https://android.googlesource.com/platform/external/avb/+/refs/heads/main/libavb/avb_vbmeta_image.h .

## Ferramenta implementada e testes

Artefato entregue na conversa: `PipaExperimental-EXP21-8G-offline-vbmeta-signature.zip`, **7683 bytes**, SHA-256 **`8b55a1eab671df21a3c1f7494f1a14ecdd6add2d035af1db5937a8c7f3de1cd3`**.

- `EXP21-8G/EXP21-8G-vbmeta-signature.py`, SHA-256 `1f75d3d0d30b465b96ab1d637551dc3e70a2bbd4acb462edfa816cfacaecd07c`.
- `EXP21-8G/EXP21-8G-LEIA-ME.txt`, SHA-256 `a5bbcd021e43000706c2e029dcffe12a6c304857233ccf5a74bb065d2d920b89`.

O script depende **somente da biblioteca padrão do Python 3** no computador do usuário, abre os oito arquivos `C:\platform-tools\pipa_backup_a\*_a.img` e `C:\platform-tools\pipa_backup\*_b.img` exclusivamente em modo `rb` e **antes de qualquer parsing comprova tamanho e SHA-256 integrais** frente aos oito pinos homologados. Rejeita arquivos trocados, truncados ou symlinks, tamanhos/offsets AVB incompatíveis e chaves de tamanho incorreto.

Extrai apenas o início de 5184 bytes de cada `vbmeta_a/b.img`, confere AVB v1.0, `algorithm_type=2`, `flags=3`, blocos de autenticação=576 e auxiliar=4352. Recalcula digest e verifica assinatura RSA4096 com implementação pura Python de RSA público/PKCS#1 v1.5 (assume exponent 65537 conforme AVB), incluindo consistência da representação Montgomery `n0inv`/`rr` da chave. Reporta:
- `VBMETA_{A,B} HEADER_AUX_HASH=MATCH/MISMATCH`;
- `VBMETA_{A,B} SELF_RSA4096_SIGNATURE=VALID/INVALID`;
- SHA256 da representação AVB da chave pública A/B e se são idênticas;
- SHA256 do blob VBMeta assinado (5184 bytes), incluindo confronto de `vbmeta_b` com o digest já observado no Android na EXP13.3;
- `COMPLETE valid=N invalid=N` para não confundir teste completo com assinatura necessariamente válida.

**Testes realizados no container de desenvolvimento:**
- `python -m py_compile`: PASS;
- `--self-test`: **`EXP21.8G SYNTHETIC SIGNED VBMeta SHA256_RSA4096 SELFTEST: PASS`**, com chave RSA4096 gerada exclusivamente no ambiente de testes, somente chave pública e assinatura de fixture sintético incluídas no script; testes de detecção de cabeçalho adulterado, assinatura RSA adulterada e precomputation de chave corrompida;
- `unzip -t`: PASS;
- verificações de SHA256 dos arquivos ZIP e membros: PASS.

**Ainda não realizado:** processamento dos oito arquivos reais do usuário, que estão somente no Windows. Não afirmar assinatura `VALID`, chaves iguais, nem digest top-level confirmado até o usuário executar a EXP21.8G e fornecer o relatório. A chave privada de fixture criada no teste **não é distribuída**.

## Comandos PowerShell 5.1

```powershell
Expand-Archive `
  -LiteralPath "$env:USERPROFILE\Downloads\PipaExperimental-EXP21-8G-offline-vbmeta-signature.zip" `
  -DestinationPath "$env:USERPROFILE\Downloads" `
  -Force

python "$env:USERPROFILE\Downloads\EXP21-8G\EXP21-8G-vbmeta-signature.py" --self-test

python "$env:USERPROFILE\Downloads\EXP21-8G\EXP21-8G-vbmeta-signature.py" `
  --slot-a "C:\platform-tools\pipa_backup_a" `
  --slot-b "C:\platform-tools\pipa_backup"
```

## Interpretação rigorosa

1. `HASH=MATCH`, `SELF_SIGNATURE=VALID` demonstra somente que o conteúdo do VBMeta está criptograficamente consistente com a chave pública **embutida naquele mesmo blob**. **Não valida uma âncora de confiança OEM** e não é aval do bootloader para o kernel EXP06.
2. `KEY_A_EQUALS_B` mostra apenas identidade das chaves embutidas no VBMeta; não demonstra que qualquer uma é confiável.
3. Cinco descritores HASH estavam MISMATCH na EXP21.8F mesmo com backups íntegros e `flags=3`. Verificação de autoassinatura não resolve essa discrepância.
4. `ro.boot.verifiedbootstate=green` e `ro.boot.vbmeta.device_state=locked` no Android continuam divergentes de `fastboot getvar unlocked=yes`; não supor qual política prevalecerá sobre imagem nova.
5. Não executar `fastboot flash`, `fastboot boot`, `fastboot --set-active`, bypass de AVB ou alteração de KernelSU como consequência desta análise.

**`EXP21.8G_SELFTEST=PASS_LOCAL`; `EXP21.8G_REAL_SIGNATURE_AUDIT=PASS_REAL`; `SLOT_A_RECOVERY=UNPROVEN`; `FLASH_READY=false`.**
