# Sets

Um set é uma organização lógica de conteúdo derivada de um catálogo. Não deve ser confundido com o conjunto físico atualmente existente no disco.

## MAME

Sets MAME precisam respeitar relações parent/clone, ROMs compartilhadas, BIOS, devices e CHDs. A composição do set deve ser derivada do catálogo ingerido e dos filtros selecionados.

## Scan × set

```text
Catalog definition → expected set
Filesystem scan     → observed content
Matching            → relationship
Reconstruction      → physical publication
```

Um scan não deve apagar automaticamente conteúdo residual. Arquivos não reconhecidos são evidência e podem ser úteis para reconstrução futura.

## Filtros

A composição de um set filtrado deve registrar ou permitir reproduzir os critérios utilizados. Alterar filtros não modifica a fonte original.
