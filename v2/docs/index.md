# SERM V2 — Documentação

Esta é a documentação técnica oficial da V2 do **Strife Emulator and Roms Manager (SERM)**.

> **Regra de manutenção:** a documentação deve descrever o código existente na V2. Planos futuros devem ser identificados explicitamente como planejamento; não devem ser apresentados como funcionalidades concluídas.

## Visão geral

| Documento | Escopo |
|---|---|
| [`../README.md`](../README.md) | Visão geral, instalação, execução e estado do projeto |
| [`architecture.md`](architecture.md) | Arquitetura e limites entre camadas |
| [`project-tree.md`](project-tree.md) | Estrutura real do pacote V2 |
| [`development-environment.md`](development-environment.md) | Ambiente de desenvolvimento e comandos |
| [`database.md`](database.md) | SQLite, SQLAlchemy e migrations |
| [`data-foundation.md`](data-foundation.md) | Modelo de dados, identidade e proveniência |
| [`catalogs.md`](catalogs.md) | Catálogos, ingestão e normalização |
| [`source-strategy.md`](source-strategy.md) | Fontes, autoridade e adapters |
| [`filters.md`](filters.md) | Filtragem de catálogos |
| [`sets.md`](sets.md) | Sets, parent/clone e organização lógica |
| [`reconstruction.md`](reconstruction.md) | Reconstrução e publicação |
| [`reconstruction-dependencies.md`](reconstruction-dependencies.md) | Dependências entre arquivos e máquinas |
| [`reconstruction/multi-emulator-layout.md`](reconstruction/multi-emulator-layout.md) | Layout de reconstrução multi-emulador |
| [`archives.md`](archives.md) | Operações com ZIP/7Z/RAR |
| [`chd-reconstruction.md`](chd-reconstruction.md) | CHD e validação com ferramentas MAME |
| [`retroarch.md`](retroarch.md) | RetroArch, cores e configuração |
| [`video-filters.md`](video-filters.md) | Shaders, filtros e apresentação |
| [`controls.md`](controls.md) | Controles e integração de hardware |
| [`force-feedback.md`](force-feedback.md) | Force Feedback |
| [`emulator-config-policy.md`](emulator-config-policy.md) | Política de configuração de emuladores |
| [`launchbox.md`](launchbox.md) | LaunchBox como provider de metadata |
| [`download-manager.md`](download-manager.md) | Downloads e aquisição de fontes |
| [`torrents.md`](torrents.md) | Integração/planejamento de torrents |
| [`status/scan_status.md`](status/scan_status.md) | Estado e invariantes do scanner |
| [`phases.md`](phases.md) | Roadmap e critérios de conclusão |

## Documentos históricos

`AUDIT_NOTES.md`, `mame_database_audit.md`, os documentos de auditoria inicial e os prompts históricos são registros de desenvolvimento. Eles não definem contratos atuais da V2.

Quando um documento histórico divergir do código ou desta documentação, prevalece, nesta ordem:

1. comportamento validado do código V2;
2. testes V2;
3. contratos e decisões arquiteturais atuais;
4. documentação histórica.

## Princípios documentais

- **V2 é autônoma.** V1 permanece apenas como referência histórica e comportamental.
- **Fonte, catálogo, identidade e arquivo são conceitos distintos.**
- **SQLite é a fonte de verdade dos metadados administrados pelo SERM.**
- **Filesystem continua sendo a origem física dos ROMs, ISOs, CHDs e arquivos do usuário.**
- **A GUI apresenta e coordena; serviços executam regras de negócio e I/O.**
- **Adapters isolam formatos externos.**
- **Scans produzem evidência; reconstruções transformam/publicam conteúdo.**
- **Nenhum caminho de reconstrução deve modificar silenciosamente a origem.**

## Estado do projeto

A V2 possui uma superfície funcional de Home, gerenciamento de emuladores, ingestão e tratamento de catálogos, filtros MAME/No-Intro, infraestrutura de scan e componentes de reconstrução. O desenvolvimento atual deve ser acompanhado pelo roadmap e pelos documentos de status, não por datas antigas gravadas em documentos de auditoria.
