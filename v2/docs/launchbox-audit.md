# Auditoria LaunchBox — SERM V2

## Objetivo

A auditoria permite estudar a estrutura real do LaunchBox sem importar dados nem modificar a instalação externa.

## Escopo atual

A primeira versão inspeciona:

- tabelas SQLite não internas;
- colunas, tipos, PK e obrigatoriedade;
- quantidade de registros;
- quantidade de plataformas do `Platforms.xml`;
- quantidade de plataformas marcadas como emuladas;
- amostra limitada de jogos.

## Segurança

O acesso ao `LaunchBox.Metadata.db` usa SQLite em modo somente leitura. O provider não executa `INSERT`, `UPDATE`, `DELETE`, `CREATE`, `ALTER` ou qualquer operação de publicação no banco externo.

`Platforms.xml` é somente lido pelo parser XML.

## Objetivo da auditoria

O resultado da auditoria não é o schema do SERM. Ele é evidência para decidir:

```text
LaunchBox field
     ↓
valor arquitetural?
     ├── sim → modelo V2
     ├── provider-only → manter no adapter
     ├── redundante → não importar
     └── específico do LaunchBox → metadata de origem
```

## Próxima investigação

Com o provider validado no ambiente Windows real, usar a API de auditoria para gerar um relatório controlado da instalação do usuário e avaliar especialmente:

- `Games`;
- `Platforms`;
- `Emulators`;
- `EmulatorPlatforms`;
- `GameAlternateTitles`;
- `GameImages`;
- `PlatformAlternateNames`;
- índices;
- migrations;
- cardinalidades implícitas;
- campos efetivamente preenchidos.

A auditoria deve preservar a distinção entre metadata do LaunchBox e dados canônicos do SERM.
