# ADR 0004 — Regras de curadoria inspiradas no MAME Smart ROM Sorter

## Status

Accepted

## Contexto

O SERM V2 já possui catálogo MAME normalizado, fontes auxiliares persistidas, pipeline de scan/filtros e reconstrução física. O projeto `Cyborgbob/MAME-Smart-ROM-Sorter` apresenta um conjunto útil de regras de curadoria orientadas ao uso real de um gabinete: 1G1R, prioridade de região/idioma, controles, jogadores, botões, orientação, status de emulação, qualidade e otimização de materialização.

## Decisão

Adotar os conceitos como regras nativas do SERM V2, sem copiar a implementação do projeto externo e sem acoplá-lo como dependência.

### Regras adotadas

1. **1G1R por família lógica** — agrupar por `cloneof`/raiz e selecionar deterministicamente um representante.
2. **Preferência regional e linguística configurável** — ranking explícito, nunca dependente da ordem de inserção no banco.
3. **Filtragem de controles** — capacidades e vias devem ser comparadas com modo permissivo ou estrito.
4. **Limites de jogadores e botões** — filtros de capacidade do gabinete devem ser aplicáveis antes da seleção 1G1R.
5. **Orientação de display** — usar informação estrutural do ListXML e permitir filtro horizontal/vertical.
6. **Status de driver/emulação** — permitir níveis ordenados de aceitação.
7. **Qualidade opcional** — scores de fontes auxiliares podem atuar como critério de seleção, preservando sua proveniência.
8. **Exclusão de máquinas não-jogáveis** — usar classificação persistida; heurísticas de texto somente como fallback.
9. **Motivo de exclusão** — cada filtro deve produzir evidência auditável.
10. **Hard link seguro** — permitido na materialização quando origem/destino forem compatíveis e com fallback para cópia.

## Limites

Não adotar como regra estrutural a heurística de detectar SPLIT/NON-MERGED observando apenas alguns clones físicos. O SERM já possui arquitetura explícita de identidade, dependência, scan e reconstrução, que deve prevalecer.

Não misturar `cloneof`, `romof` e `merge`: são relações de domínios diferentes.

## Consequências

A camada de filtros do SERM fica mais expressiva para curadoria prática sem sacrificar a autoridade do ListXML nem a rastreabilidade das fontes. A seleção de jogos permanece independente da materialização física, e a reconstrução pode preservar dependências compartilhadas mesmo quando uma variante foi descartada pelo 1G1R.
