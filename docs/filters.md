# Filtros e seleção

**Referência:** 17/08/2026

## Princípio

A GUI coleta opções; regras de seleção ficam na camada de serviço/modelo. O filtro deve produzir uma seleção de machines que posteriormente pode alimentar Scan, XML e construção do set.

## Filtros atuais

O projeto trabalha com categorias/macrocategorias, estado de emulação e relações de machines, além das opções disponíveis na interface atual. Os nomes exatos das opções devem ser obtidos do código atual, não deste documento.

## Arcade

O objetivo principal inclui conjuntos Arcade. A classificação deve priorizar informações estruturais do MAME e os dados complementares existentes, evitando regras textuais frágeis como única fonte de decisão.

A política histórica do projeto exclui categorias como casino, quiz, tabletop, fruit machines e eletromecânicas quando elas não pertencem ao conjunto desejado.

## Clones

Parent e clone são entidades lógicas diferentes. A política de clones precisa respeitar o tipo físico do set.

```text
Split      → parent e clones possuem arquivos relacionados separadamente
Non-Merged → cada machine precisa ser autossuficiente
Merged     → parent/clone compartilham o arquivo segundo a semântica MAME
```

## Status de emulação

A seleção deve considerar os estados disponíveis no dataset. Não confundir status de emulação com classificação de plataforma.

## Relação com Scan

O filtro seleciona machines; o Scan verifica o estado físico. A reconstrução não redefine o filtro nem deve usar a GUI para localizar ROMs.

## Pendências

- Consolidar todas as regras de classificação no serviço de filtro.
- Validar categorias com fixtures do dataset MAME usado pelo projeto.
- Integrar completamente a seleção de dependências ao resultado físico do Scan.
