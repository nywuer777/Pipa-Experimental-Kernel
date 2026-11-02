# EXP76 — canal de evidências CI (não-flash)

Este branch é destinado a resultados resumidos do workflow Clang 21. Ele não
contém uma imagem de kernel aprovada e não é destinado a flash.

Arquivos após a primeira publicação bem-sucedida:

- `ci-evidence/clang21-latest.json`: execução de CI mais recente publicada.
- `ci-evidence/runs/<run_id>.json`: histórico imutável por execução.

Os registros incluem URL da execução, SHA do código-fonte, resultado do job,
status de `make prepare`, erros do compilador limitados, status dos três
objetos e manifestos dos Stages 19–21. Ausência de um artefato é registrada
como ausência, não como aprovação.

A publicação é feita em um job separado, com `contents:write`; o job que
compila o kernel mantém `contents:read`. Apenas JSON de diagnóstico deve
ser enviado a este branch.

`EXP75_PERMANENT=PRESERVED`  
`KERNEL_BUILT=false`  
`FLASH_READY=false`
