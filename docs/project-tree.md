# Estrutura atual do projeto

A raiz do repositório é também a raiz do projeto Python. O pacote ativo é `serm_v2`; não há subdiretório `v2/`.

```text
SERM/
├── .github/                 Integração do repositório
├── config/                  Configurações de ferramentas do projeto
├── docs/                    Documentação técnica
├── serm_v2/                 Aplicação Python
│   ├── assets/              Recursos empacotados
│   ├── catalog/             Catálogos e normalização
│   ├── config/              Configuração interna
│   ├── database/            Persistência e migrations
│   ├── domain/              Modelos e regras de domínio
│   ├── emulation/           Integração com emuladores
│   ├── gui/                 Interface PySide6
│   ├── integrations/        Integrações externas
│   ├── library/             Biblioteca e conteúdo local
│   ├── models/              Modelos compartilhados
│   ├── runtime/             Caminhos e ambiente de execução
│   ├── services/            Serviços e workflows
│   ├── sources/             Providers e adapters de fontes
│   └── tools/               Ferramentas de auditoria e manutenção
├── tests/                   Testes automatizados
├── README.md                Visão geral e instruções rápidas
└── pyproject.toml           Empacotamento, dependências e ferramentas
```

## Organização da GUI

`serm_v2/gui/` contém as páginas principais e subpacotes de componentes, serviços visuais e fluxos do Arcade Studio. A configuração central é composta por páginas próprias para diretórios, emuladores, vídeo, drivers, som, controles e aparência. Páginas específicas de WinUAE, Amiberry, Altirra, ares e Azahar lidam com particularidades dos respectivos arquivos e formatos.

No ares, os editores nativos de configurações preservam `settings.bml` e fazem backup antes de salvar. A integração cobre vídeo/shaders/bezels, opções de áudio, controles e Virtual Gamepads, opções gerais, paths e drivers. O estado da interface e os caminhos selecionados pelo usuário ficam fora do código-fonte, na área de dados da aplicação.

## Dados locais

Bancos, logs, caches, configurações selecionadas, downloads e backups são dados de execução do usuário, não parte da estrutura do pacote Python. Seus caminhos são administrados pelo runtime e pelas áreas de configuração do SERM.

## Fonte de verdade

Use a árvore real do repositório para detalhes finos. Este documento descreve apenas os principais limites e deve ser atualizado quando a organização de pacotes mudar.
