# Filtros

Filtros reduzem um catálogo ou dataset segundo regras explícitas. Eles não alteram a fonte original.

## Pipeline

```text
Catalog
  ↓
Fundamental filters
  ↓
Advanced/category filters
  ↓
Resolved dataset
```

## MAME

A V2 possui filtros fundamentais e avançados para o catálogo MAME, incluindo classificação e critérios relacionados ao tipo de máquina. O filtro deve operar sobre dados normalizados, não sobre XML bruto dentro do widget.

## Persistência

Filtros podem ter estado de aplicação/sessão ou persistência própria quando implementada. Documentação deve distinguir claramente os dois casos.

## Regras

- filtro não modifica o catálogo authoritative;
- resultado deve ser reprodutível a partir do catálogo e configuração;
- filtros devem ser testáveis sem GUI;
- novos critérios devem ter cobertura de teste;
- filtros usados no scan devem ser identificáveis junto ao resultado quando necessário para auditoria.
