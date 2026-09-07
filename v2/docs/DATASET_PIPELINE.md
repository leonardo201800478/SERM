# Dataset pipeline

## Pipeline canônico

```text
External source
      ↓
Acquisition
      ↓
Adapter / parser
      ↓
Normalization
      ↓
Catalog version
      ↓
Filter
      ↓
Scan / matching
      ↓
Reconstruction
```

## Regras

A aquisição preserva a origem. A normalização cria o modelo consumido pelo SERM. Filtros produzem visões/datasets derivados. Scan compara o catálogo com o filesystem. Reconstruction produz arquivos de destino.

Nenhuma etapa deve alterar silenciosamente a fonte anterior.

## Persistência

Metadados e estado operacional são persistidos no SQLite V2. Arquivos físicos permanecem no filesystem.

## Reprocessamento

Uma etapa derivada deve poder ser reexecutada quando a versão do catálogo ou a configuração mudar. Resultados antigos devem ser identificáveis para não serem confundidos com resultados atuais.
