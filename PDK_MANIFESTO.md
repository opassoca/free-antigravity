# PDK Manifesto - Paçoca Deterministic Kernel

## Visão Geral
O PDK é a camada de inteligência determinística que transforma o Gemini CLI puro em um ecossistema de alta performance para o ambiente Debian/Android. Ele resolve o problema de latência de carregamento de skills através de injeção lógica de contexto.

## Engenharia Reversa e Origem dos Dados
- **Gemini CLI:** Identificado via `bundle/chunk-4IXP3BQP.js` que a detecção de ferramentas é estática no boot ou via reload manual. O PDK faz o bypass lendo o disco diretamente.
- **Hardware Telemetry:** Mapeado cirurgicamente nos nós `/sys` para o Exynos 9820.
  - CPU Principal: `thermal_zone0` e `thermal_zone2`.
  - Limite de Estabilidade: 80°C (Ponto de intervenção PDK).

## Gestão de Skills (Arsenal)
A biblioteca oculta `.library` é protegida com permissões `0700` e indexada para despacho determinístico.

### Categorias de Despacho
- **android-***: Integração host/chroot via `nsenter`.
- **samsung-***: Estabilidade de kernel e prevenção de panics.
- **office-***: Scripts Python para manipulação de DOCX/PDF/XLSX.
- **web-***: Frameworks de design e automação de navegador.
- **dev-***: Padrões de engenharia Opus e Codexx.

## Auditoria e Validação
Todas as decisões do PDK são registradas em `kernel_audit.log`, permitindo a engenharia reversa de falhas de decisão do agente.
