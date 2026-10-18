# EXP16 confirmada e EXP17 preparada — 18/10/2026

## EXP16 homologada no Windows real

O usuário confirmou o autoteste `EXP16 SYNTHETIC CANONICAL V3 REPACK HASH: PASS` e a auditoria `EXP16 REAL AOSP-STYLE BOOT-V3 CANONICAL REPACK ANALYSIS: PASS` contra `C:\platform-tools\pipa_backup\boot_b.img`.

O header canônico apresentou 0 divergências; os paddings de kernel e ramdisk tinham 0 bytes não-nulos; as duas versões compactas, de 32206848 bytes, produziram SHA-256 `202aaaf67fe5c0a963965c4e29f67866b509916e0bdff15dde38ef55b3d321e7`. Resultado `MATCH`. A região restante da partição, 169119744 bytes, **não foi considerada vazia ou descartável**. Nenhum arquivo alterado. `FLASH_READY=false`.

## EXP17 — ferramenta oficial AOSP, reprodução exclusivamente do original

Preparado um pacote externo de auditoria com `EXP17-aosp-mkbootimg-compare.py` e `EXP17-run-windows.ps1`. O Python extrai para pasta temporária apenas kernel e ramdisk da imagem **original**, chama o `mkbootimg.py` original do AOSP (fonte de código conferida por hash de blob Git) e compara byte a byte o resultado compacto de 32206848 bytes com o backup de origem. O diretório temporário é automaticamente excluído. O script não inclui, injeta ou produz kernel experimental, e não chama ferramentas de flash.

Fontes AOSP fixadas com Git blob SHA1:
- `mkbootimg.py`: `ec2958179691a434df917cd1b6f196edaa80e31d`;
- `gki/generate_gki_certificate.py`: `739c61b04a9dbd95cafa5196533e3a472c31f2d9`.

**Status:** autoteste sintético do wrapper Python `PASS` no ambiente local. A ferramenta original do AOSP **ainda não foi executada** neste ambiente, e a auditoria com o backup privado do usuário também está pendente. Isso não equivale a homologação oficial do repack.

Próximo gate: executar EXP17 no Windows do usuário; resultado esperado `RESULT=MATCH`; nenhum flash. Ainda é necessário planejar recuperação, avaliar KernelSU, AVB e bootabilidade para qualquer teste experimental posterior. `FLASH_READY=false`.
