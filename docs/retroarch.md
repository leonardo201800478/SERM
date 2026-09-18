# RetroArch

RetroArch é tratado como runtime de emulação, enquanto os cores Libretro são componentes selecionáveis desse runtime.

## Responsabilidades do SERM

- descobrir/administrar instalação quando suportado;
- catalogar cores disponíveis;
- distinguir Stable de Beta/Nightly quando a fonte fornecer essa informação;
- instalar cores de forma controlada;
- manter paths e configurações relevantes;
- integrar profiles de execução.

## Catálogo de cores

O catálogo remoto/local deve ser adquirido pelo serviço responsável e filtrado antes da instalação. Instalações sequenciais devem validar sucesso, tratar retry e verificar integridade quando houver mecanismo de CRC/hash disponível.

## Configuração

O SERM não deve reescrever indiscriminadamente o `retroarch.cfg` ou configurações de cores. Somente propriedades conhecidas e suportadas devem ser administradas.

## Estado

Filtros de catálogo podem permanecer como estado de sessão quando essa for a implementação atual. Não documentar estado transitório como preferência persistente.

## BIOS, system, saves e shaders

Esses recursos possuem ciclo de vida próprio e devem ser modelados separadamente de ROMs. Paths físicos permanecem referências externas ao banco.
