# ADR-0003: Arquitetura de reconstrução de ROMs MAME

- Status: Accepted
- Escopo: Arcade Studio V2
- Data: 2026-09-08

## Contexto

A estrutura de ROMs MAME combina identidade de máquinas, relações parent/clone, dependências `romof`, referências `merge` em ROMs e identidade física por hashes. Uma implementação que trate todos esses conceitos como uma única relação de nomes produz reconstruções incorretas.

A auditoria do catálogo real do SERM revelou 179.667 relações `merge`. Antes da normalização de duplicatas fisicamente idênticas, parte dessas relações aparecia como `MISSING` por duplicação representacional. O planner foi ajustado para distinguir duplicatas idênticas de conflitos físicos.

## Decisão

O SERM V2 separa a reconstrução em três níveis:

1. **catálogo lógico** — `ArcadeGame` e `ArcadeRom`;
2. **plano de origem** — `ArcadeRomReconstructionPlanner`;
3. **resolução física** — `ArcadeRomReconstructionEngine`.

A materialização só ocorre depois dessas três dimensões serem resolvidas e auditadas pelo manifesto.

## Identidades

`machine_name` identifica a máquina.

`display_name` identifica a ROM declarada dentro da máquina.

`source_machine` identifica a máquina de onde o conteúdo deve ser obtido.

`source_rom_name` identifica a ROM física/logicamente solicitada.

Hashes identificam o conteúdo físico.

## Semântica de `merge`

`merge` é tratado como nome de ROM. O planner procura primeiro a máquina atual e depois as máquinas explicitamente relacionadas (`romof` e parent). Uma correspondência global em máquina não relacionada é rejeitada.

Quando a origem é outra máquina, o resultado é `MERGED`. Quando a própria máquina contém a ROM correspondente, o resultado é `SELF`.

## Duplicatas

Duplicatas com SHA1/CRC/size idênticos representam a mesma identidade física e podem ser resolvidas deterministicamente. Duplicatas com identidade física diferente continuam ambíguas.

## Identidade física

A resolução física segue:

```text
SHA1 > MD5 > CRC + size
```

Mais de um candidato para a mesma identidade produz `AMBIGUOUS`; o SERM não seleciona arbitrariamente.

## Layouts

A materialização segue três modelos:

- SPLIT: dependências compartilhadas permanecem no archive de origem;
- NON_MERGED: cada set recebe seus componentes necessários;
- FULL_MERGED: a família é armazenada no archive da raiz.

CHDs possuem pipeline separado e não são empacotados como ROMs.

## Consequências

A arquitetura privilegia determinismo e auditabilidade sobre heurísticas. Uma relação não resolvida deve permanecer explicitamente não resolvida até que evidência suficiente permita sua resolução.

O contrato também impede a colisão de múltiplas ROMs da mesma máquina no manifesto: resultados são indexados por `(machine_name, rom_name)`, onde `rom_name` é o `display_name` da ROM.

## Validação

A auditoria real do catálogo atingiu:

```text
SELF     167637
MERGED    12030
PARENT        0
ROMOF         0
MISSING       0
DIVERGENCIAS  0
```

A suíte complementar de reconstrução e materialização também foi executada sem falhas.
