# CHD

CHD é um formato de mídia gerenciado por ferramentas do ecossistema MAME e deve ser tratado separadamente de archives comuns.

## Princípios

- identificar CHDs pela definição do catálogo;
- procurar o arquivo no local esperado da machine;
- não realizar busca global indiscriminada durante o scan;
- validar CHD existente com ferramenta compatível quando o workflow exigir;
- publicar somente depois da validação.

## Reconstrução

```text
Disk definition
    ↓
Scan evidence
    ↓
Candidate / source
    ↓
Staging
    ↓
CHD creation or copy
    ↓
Verification
    ↓
Atomic publish
```

`chdman` é uma ferramenta externa e seu caminho deve ser configurável. A reconstrução deve registrar versão/ferramenta utilizada quando essa informação estiver disponível.

## Ausência

A ausência de um CHD não deve provocar uma varredura global do filesystem. O resultado deve ser registrado como ausência para que o resolver de reconstrução possa consultar fontes alternativas posteriormente.
