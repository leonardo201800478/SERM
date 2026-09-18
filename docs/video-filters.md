# Filtros de vídeo e apresentação

A camada de apresentação deve separar a identidade do sistema emulado das características do monitor físico.

## Princípios

- proporção deve seguir o sistema/conteúdo quando conhecido;
- não forçar 16:9 apenas porque o monitor é widescreen;
- shaders e filtros são propriedades de apresentação, não de identidade do ROM;
- configurações específicas devem ser aplicadas por profile/override quando suportado.

## RetroArch

Shaders podem ser associados ao runtime/core e ao profile de execução. O SERM deve preservar configurações nativas que não administra.

## CRT

A prioridade é oferecer presets consistentes, leves e configuráveis, evitando acoplamento da GUI a um único shader ou pacote externo.

## Integridade

Pacotes externos devem ser tratados como recursos de terceiros. O SERM deve registrar a origem quando precisar reproduzir um preset específico.
