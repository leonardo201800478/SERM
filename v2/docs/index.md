# SERM V2 — Documentação

Esta é a documentação técnica oficial da V2 do **Strife Emulator and Roms Manager (SERM)**.

> **Regra de manutenção:** a documentação deve descrever o comportamento e a estrutura existentes na V2. Planos futuros devem ser identificados explicitamente como planejamento; não devem ser apresentados como funcionalidades concluídas.

## Ordem de autoridade

Quando houver divergência entre documentos, use esta ordem:

1. comportamento validado do código V2;
2. testes V2;
3. contratos e decisões arquiteturais atuais;
4. documentação operacional atual;
5. documentação histórica.

A V1 é referência histórica e comportamental. A árvore ativa de `main` contém a V2 e não possui um pacote V1 importável.

## Documentação principal

| Documento | Escopo |
|---|---|
| [`../README.md`](../README.md) | Visão geral, instalação, execução e estado |
| [`architecture.md`](architecture.md) | Arquitetura e limites entre camadas |
| [`project-tree.md`](project-tree.md) | Estrutura real do pacote V2 |
| [`development-environment.md`](development-environment.md) | Ambiente, testes e qualidade |
| [`database.md`](database.md) | SQLite, SQLAlchemy e migrations |
| [`data-foundation.md`](data-foundation.md) | Modelo de dados, identidade e proveniência |
| [`catalogs.md`](catalogs.md) | Catálogos, ingestão e normalização |
| [`source-strategy.md`](source-strategy.md) | Fontes, autoridade e adapters |
| [`filters.md`](filters.md) | Filtragem de catálogos |
| [`sets.md`](sets.md) | Sets e relações parent/clone |
| [`reconstruction.md`](reconstruction.md) | Reconstrução e publicação |
| [`reconstruction-dependencies.md`](reconstruction-dependencies.md) | Dependências de reconstrução |
| [`mame-semantic-validation.md`](mame-semantic-validation.md) | Auditorias, invariantes e regras semânticas do MAME |
| [`arcade-mame-rom-architecture.md`](arcade-mame-rom-architecture.md) | Artigo aprofundado sobre a arquitetura de ROMs MAME no SERM V2 |
| [`external-resources.md`](external-resources.md) | Catálogo, providers e aquisição de recursos externos |
| [`projeto-snaps.md`](projeto-snaps.md) | Guia consolidado da integração projeto-SNAPS no Arcade Studio |
| [`decisions/0003-mame-rom-reconstruction-architecture.md`](decisions/0003-mame-rom-reconstruction-architecture.md) | ADR-0003 e invariantes da reconstrução de ROMs |
| [`reconstruction/multi-emulator-layout.md`](reconstruction/multi-emulator-layout.md) | Layout multi-emulador |
| [`archives.md`](archives.md) | Operações com arquivos compactados |
| [`chd-reconstruction.md`](chd-reconstruction.md) | CHD e validação |
| [`retroarch.md`](retroarch.md) | RetroArch, cores e configuração |
| [`video-filters.md`](video-filters.md) | Shaders, filtros e apresentação |
| [`controls.md`](controls.md) | Controles |
| [`force-feedback.md`](force-feedback.md) | Force Feedback |
| [`emulator-config-policy.md`](emulator-config-policy.md) | Política de configuração |
| [`launchbox.md`](launchbox.md) | LaunchBox como provider opcional |
| [`download-manager.md`](download-manager.md) | Aquisição, cache, validação e downloads |
| [`torrents.md`](torrents.md) | Torrents e aquisição |
| [`status/scan_status.md`](status/scan_status.md) | Estado e invariantes do scanner |
| [`phases.md`](phases.md) | Roadmap e critérios de conclusão |

## Documentos históricos e auxiliares

`ARCHITECTURE_RECOMMENDATIONS.md`, `AUDIT_NOTES.md`, `Arquitetura_recomendada_para_scan_e_reconstrução_d.md`, `Auditoria_inicial_—_MAME_Set_Builder.md`, `mame_database_audit.md` e os arquivos de prompts são registros de desenvolvimento, auditoria ou planejamento. Eles não definem contratos atuais da V2.

`MAME.pdf` é material de referência e não documentação normativa do SERM.

## Princípios

- **V2 é autônoma:** não importa modelos, serviços, configuração ou runtime da V1.
- **Fonte, catálogo, identidade, arquivo e evidência de scan são conceitos distintos.**
- **SQLite administra o estado e os metadados do SERM;** ROMs, ISOs, CHDs e arquivos permanecem no filesystem do usuário.
- **A GUI coordena e apresenta;** serviços concentram regras de negócio e I/O.
- **Adapters isolam formatos externos.**
- **Scan produz evidência; reconstrução transforma e publica.**
- **A origem física não deve ser modificada silenciosamente por uma reconstrução.**
- **O código deve ser a referência final para o que realmente está implementado.**

## Estado atual

A V2 está em desenvolvimento **Alpha**. A integração inicial do projeto-SNAPS no Arcade Studio está concluída para esta etapa e documentada em [`projeto-snaps.md`](projeto-snaps.md). O restante da V2 continua em desenvolvimento conforme o roadmap.

## Manutenção da documentação

Ao alterar uma funcionalidade, atualize na mesma mudança o documento correspondente quando houver impacto em contrato, fluxo, configuração, persistência ou comportamento observável. Evite criar documentos paralelos para a mesma responsabilidade; prefira atualizar o documento canônico e manter material antigo explicitamente identificado como histórico.
