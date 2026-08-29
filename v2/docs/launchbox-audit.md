# Auditoria LaunchBox — SERM V2

## Objetivo

A auditoria permite estudar a estrutura real do LaunchBox sem importar dados nem modificar a instalação externa.

## Execução

Com o ambiente virtual V2 ativo:

```powershell
python -m serm_v2.tools.audit_launchbox
```

Para uma amostra menor:

```powershell
python -m serm_v2.tools.audit_launchbox --sample 5
```

Para escolher outro arquivo de saída:

```powershell
python -m serm_v2.tools.audit_launchbox --output C:\Temp\serm-launchbox-audit.json
```

A saída padrão é:

```text
v2/data/exports/launchbox-audit.json
```

O arquivo é operacional e não deve ser versionado.

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

O relatório real será utilizado para avaliar especialmente:

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
