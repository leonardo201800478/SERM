# Arquitetura da GUI — SERM V2

## Navegação principal

1. **Início** — visão geral.
2. **Configuração** — diretórios, ferramentas, emuladores e vídeo.
3. **Fontes e Dados** — aquisição e atualização de DATs e fontes externas.
4. **MAME Studio** — fluxo operacional MAME.
5. **Outros Sistemas** — pipelines específicos de No-Intro, Redump, WHLoader e C64.

## MAME Studio

O fluxo operacional deve ser linear:

**Catálogo → Scan → Filtros → Reconstrução**

As páginas de fase são as implementações canônicas. Interfaces antigas embutidas em páginas de catálogo não devem duplicar operações de filtro ou reconstrução.

## Regra de organização

- Uma operação deve ter uma única tela canônica.
- Componentes visuais compartilhados devem ser públicos e reutilizáveis.
- Serviços concentram regras de negócio; páginas concentram composição da GUI.
- Páginas legadas podem permanecer durante a migração V1 → V2, mas não devem ser expostas simultaneamente na navegação V2.
