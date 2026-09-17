# Catálogos

## Objetivo

O Catalog Manager transforma fontes externas em dados canônicos consumíveis pelos filtros, scanners e workflows de reconstrução.

## Pipeline

```text
Fonte externa
   ↓
Aquisição
   ↓
Parsing / adapter
   ↓
Normalização
   ↓
Catalog version
   ↓
Persistência
   ↓
Filtros / scan / matching
```

## Separação de responsabilidades

- **Source** identifica de onde o dado veio.
- **Catalog** representa uma coleção/versionamento de entradas.
- **Canonical identity** representa a entidade reconhecida pelo SERM.
- **File** representa o objeto físico encontrado no filesystem.
- **Scan result** registra a relação observada entre catálogo e filesystem.

## MAME

A principal entrada de catálogo MAME é o ListXML produzido pelo próprio MAME. A V2 possui serviços para ingestão, normalização, classificação, auditoria, filtros, resolução, display, VSync e CHD.

Dados auxiliares podem complementar o catálogo, mas não devem sobrescrever silenciosamente a informação factual do ListXML.

## No-Intro

DATs/arquivos No-Intro são tratados por adapters próprios. O formato do DAT deve ser preservado o suficiente para auditoria e matching, enquanto o SERM utiliza uma representação canônica interna.

## WHDLoad e C64/TOSEC

WHDLoad/Amiberry e C64/TOSEC são fontes especializadas. Não devem ser forçados ao modelo semântico de MAME ou No-Intro apenas para reutilização de código.

## Versionamento

Uma atualização de fonte deve ser identificável por versão/estado de ingestão. Resultados derivados de uma versão anterior não devem ser confundidos com resultados do catálogo atual.

## Integridade

Ingestores devem validar:

- estrutura mínima do documento;
- identidade e nomes obrigatórios;
- hashes/tamanhos quando fornecidos;
- duplicidades relevantes;
- consistência entre parent/clone e dependências quando aplicável.

Erros de ingestão devem ser reportados sem descartar silenciosamente a origem.
