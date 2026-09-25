# Documentação do SERM V2

Esta documentação descreve o código ativo em `serm_v2/`. O SERM está em desenvolvimento Alpha; funcionalidades incompletas e trabalho futuro devem ser acompanhados pelo [roadmap](phases.md), não inferidos de registros de auditoria antigos.

## Estado e orientação

- [Roadmap da V2](phases.md) — estado macro, prioridades e critérios de conclusão.
- [Arquitetura da GUI V2](gui-architecture-v2.md) — navegação, configuração e páginas dos emuladores.
- [Política de configuração dos emuladores](emulator-config-policy.md) — limites para leitura e edição de arquivos externos.
- [Estrutura do projeto](project-tree.md) — organização atual do repositório e pacote.
- [Ambiente de desenvolvimento](development-environment.md) — instalação, execução e ferramentas.

## Arquitetura e dados

- [Arquitetura](architecture.md) — camadas e limites entre componentes.
- [Banco de dados](database.md) — SQLite, modelos e migrations.
- [Fundação de dados](data-foundation.md) — identidade, proveniência e relações.
- [Catálogos](catalogs.md) — ingestão e normalização.
- [Estratégia de fontes](source-strategy.md) — autoridade e adapters.
- [Política de fontes externas](external-resources.md) — catálogo e aquisição de recursos.

## Arcade Studio e reconstrução

- [Filtros](filters.md), [sets](sets.md) e [estado do scan](status/scan_status.md).
- [Reconstrução](reconstruction.md), [dependências](reconstruction-dependencies.md), [layouts multi-emulador](reconstruction/multi-emulator-layout.md) e [CHD](chd-reconstruction.md).
- [Arquitetura de ROMs MAME](arcade-mame-rom-architecture.md) e [validação semântica](mame-semantic-validation.md).
- [ADR-0003: reconstrução de ROMs MAME](decisions/0003-mame-rom-reconstruction-architecture.md).

## Emuladores e recursos

- [RetroArch](retroarch.md), [filtros de vídeo](video-filters.md), [controles](controls.md) e [force feedback](force-feedback.md).
- [LaunchBox](launchbox.md) como integração opcional.
- [Downloads](download-manager.md), [torrents](torrents.md) e [arquivos compactados](archives.md).

## Documentos históricos

Auditorias iniciais, notas, prompts e recomendações registram decisões e resultados de momentos anteriores do desenvolvimento. Seus números e conclusões são snapshots históricos; consulte o código V2, os testes e o roadmap para saber o estado atual.

## Ordem de autoridade

Quando houver divergência, use: código V2 e comportamento executável; testes; ADRs e contratos atuais; documentação operacional; materiais históricos.
