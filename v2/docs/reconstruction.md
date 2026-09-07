# Reconstrução

## Objetivo

Reconstrução converte conteúdo disponível no filesystem em uma organização compatível com um catálogo e um destino de execução, usando evidências do scan e regras do sistema.

Reconstrução não é scan: **scan observa; reconstrução transforma.**

## Pipeline

```text
Catalog + scan evidence
        ↓
Dependency resolver
        ↓
Candidate selection
        ↓
Plan
        ↓
Staging
        ↓
Archive / CHD / filesystem transform
        ↓
Validation
        ↓
Atomic publish
```

## Princípios

- origens permanecem somente leitura;
- nenhum arquivo parcial deve aparecer no destino final;
- operações destrutivas devem ocorrer apenas em destino explicitamente controlado;
- hashes e tamanhos devem ser validados quando a fonte fornecer esses dados;
- dependências precisam ser resolvidas antes da publicação;
- falhas devem permitir diagnóstico e retomada quando possível.

## Matching

O nome de arquivo é auxiliar. Matching deve priorizar evidências fortes como hash, tamanho, identidade catalogada e relações parent/clone/dependência.

O sistema deve registrar a evidência que levou a uma correspondência quando houver ambiguidade.

## Staging

A transformação deve ocorrer em área temporária. A publicação só acontece depois da validação do resultado.

```text
source → staging → validate → destination
```

## MAME

MAME possui semântica própria para parent/clone, ROMs compartilhadas, device ROMs, BIOS e CHDs. O resolver deve respeitar essas relações e não tratá-las como uma simples lista plana de arquivos.

## Consoles / No-Intro

A reconstrução deve respeitar a identidade e o nome definidos pelo DAT aplicável. Variantes, regiões e revisões não devem ser misturadas por heurística fraca.

## Discos / Redump / CHD

Discos devem ser tratados como mídia estruturada. CHD é uma representação específica e deve ser criada/validada por ferramentas compatíveis quando exigido pelo workflow.

## Arquivos

Operações de ZIP/7Z/RAR devem passar pelo serviço de arquivo. O serviço deve encapsular diferenças entre bibliotecas Python e executáveis externos.

## Segurança

Entradas externas devem ser consideradas não confiáveis. Extração deve impedir path traversal e links maliciosos quando o formato permitir. Conteúdo não deve ser executado como parte da validação.

## Estado

Planos e resultados de reconstrução devem poder ser associados à versão do catálogo e às evidências do scan que os originaram. Uma reconstrução antiga não deve ser apresentada como validação automática de um catálogo mais novo.
