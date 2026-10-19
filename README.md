# EXP

**EXP** é um kernel Android ARM64 experimental para o **Xiaomi Pad 6 (pipa, Snapdragon 870)**.

**Versão de desenvolvimento: EXP25A.** A última versão com `fastboot boot` e inicialização confirmados no dispositivo é a **EXP24**. EXP25A não está homologada, e nenhuma versão está autorizada para instalação persistente (`FLASH_READY=false`).

## Estado técnico do projeto

| Frente | Estado atual |
| --- | --- |
| Nome oficial do projeto | **EXP** |
| Versão de desenvolvimento | **EXP25A** (correção experimental de IRQ Novatek; validação pendente) |
| Última inicialização temporária validada | **EXP24** (Linux 4.19.404R, Clang 21) |
| Ethernet Realtek RTL8153 | `r8152`, `eth0` e IPv4 comprovados na EXP24; reconexão USB intermitente |
| Touchscreen slot B | Novatek NT36532 reconhecido, falha de recarga de firmware CSOT após suspend/resume, IRQ 521 em zero |
| Fonte de origem | E404 fixado no commit `fed88a6024cd4d46c52eda607a95d97d7371ba81` |
| Boot e instalação | Somente ensaio reversível com `fastboot boot` quando validado; sem flash |

**Identidade própria não significa fonte própria concluída.** A partir desta decisão, o E404 deixa de ser o nome principal do projeto, mas a compilação ainda recupera a árvore de origem `kvsnr113/xiaomi_sm8250_kernel_e404`, commit acima, com patches EXP e ferramentas reprodutíveis. A migração para uma árvore de código mantida integralmente neste repositório é uma etapa futura e deverá preservar as condições de licença, histórico e compatibilidade. A identificação técnica Linux `4.19.404R` não é a versão do produto EXP.

## Desenvolvimento e próximas validações

- **EXP24:** base experimental iniciada temporariamente; driver Ethernet funcional sob enumeração, com instabilidade USB-C/hub ainda em investigação.
- **EXP25A:** mudança isolada no retorno da IRQ do Novatek ao acordar a tela; compilação Clang 21 no GitHub Actions, sem afirmar solução para firmware ou touch antes do ensaio físico.
- **EXP25B (reserva):** diagnóstico/correção separada de recuperação do firmware CSOT após análise dos resultados da EXP25A.
- **Próximas versões:** estabilidade USB-C/RTL8153 e melhorias de desempenho orientadas por medições, sem reduzir proteções elétricas ou térmicas.

Documentação: [versões e política de liberação](docs/EXP-VERSIONING.md) · [toque no slot B](docs/EXP24-TOUCH-SLOT-B.md) · [Ethernet e USB-C](docs/EXP24-ETHERNET.md).

CI: [EXP25A — Clang21, Novatek IRQ (sem flash)](../../actions/workflows/exp25-touch-clang21-build.yml) · [EXP24 — Ethernet Clang21 (sem flash)](../../actions/workflows/exp24-ethernet-clang21-build.yml).

## Base histórica e proteção dos dados

O experimento inicial EXP01 alterou o intervalo inicial do governador `schedutil` de 2000 para **1500 µs** com patch explícito; a EXP24 acrescentou suporte Ethernet embutido sem módulos. A fonte histórica está arquivada em `PipaExperimental-EXP01-source.zip` (SHA-256 `548ebb47ad0febe3c4541b9e93f2233bb9188c78d8f9ec298dd397a11216b852`). O patch corrigido permanece em `patches/0001-pipa-exp01-schedutil-rate-limit.patch`.

**Não instalar** os ZIPs de fonte via recovery, Magisk, KernelSU ou fastboot. Este repositório não fornece `boot.img` homologado. Antes de qualquer teste de boot persistente serão necessários compilação confirmada, checagem de DTB/DTBO/vendor_boot, compatibilidade com a ROM, plano de recuperação e validações graduais com hardware. **Nunca publicar backups privados de partições ou dumps com chaves/identificadores.**
