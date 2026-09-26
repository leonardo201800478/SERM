# Política de configuração de emuladores

## Objetivo

Centralizar no SERM somente as configurações que o aplicativo consegue identificar, validar e manter com segurança.

## Estado da implementação

A central de configuração oferece áreas compartilhadas para Diretórios, Emuladores, Vídeo, Drivers, Som e Controles. Páginas específicas lidam com formatos e caminhos próprios de alguns emuladores; o escopo por emulador está descrito em [Arquitetura da GUI V2](gui-architecture-v2.md). Os editores atuais leem o arquivo registrado, habilitam somente opções presentes e preservam o arquivo por meio de backup ao salvar. Formatos BML, INI e texto chave/valor usam leitores ou editores específicos; nenhum campo deve inventar chaves ausentes sem uma opção explícita que documente esse comportamento.

Para Amiberry, `amiberry.conf` guarda preferências globais e caminhos; `amiberry.ini` guarda estado da interface e ROMs detectadas. Perfis Quickstart, hardware e CPU pertencem a configurações UAE específicas e não devem ser escritos no arquivo global. Listas dependentes de dispositivo não devem ser apresentadas como opções universais.

## Padrões obrigatórios de GUI

Além das regras de persistência e segurança deste documento, toda tela de Diretórios ou Configurações de Emuladores deve seguir os padrões funcionais definidos na [Arquitetura da GUI V2](gui-architecture-v2.md):

1. controles interativos devem oferecer ajuda contextual por tooltip ao passar o mouse, especialmente ações representadas por ícones;
2. telas com configurações persistentes devem oferecer **Salvar** e **Restaurar Padrões**;
3. **Salvar** deve respeitar somente as chaves/opções suportadas pelo editor;
4. **Restaurar Padrões** deve ser uma ação explícita e documentada, sem sobrescrever configurações externas não administradas pela tela.

A implementação de novos editores deve considerar esses requisitos desde a composição da GUI, e não como uma etapa posterior de acabamento.


## Princípios

1. A instalação do emulador é um recurso externo.
2. O SERM registra paths, versão e propriedades administradas pelo próprio SERM.
3. Configurações nativas desconhecidas devem ser preservadas.
4. Alterações devem ser reversíveis sempre que possível.
5. A GUI deve usar os leitores e editores específicos do formato; regras compartilhadas de escrita, backup e validação devem ficar encapsuladas em helpers ou serviços reutilizáveis.

## Execution Profile

O profile de execução relaciona plataforma, runtime/emulador/core e opções necessárias para iniciar conteúdo.

```text
Platform
   ↓
Execution Profile
   ↓
Runtime / Emulator / Core
   ↓
Content
```

Arguments, BIOS, shaders, overlays e paths podem pertencer ao profile quando fizerem parte do contrato de execução.

## Segurança

Antes de alterar configuração externa:

- validar caminho;
- confirmar o executável esperado;
- evitar sobrescrita de arquivos desconhecidos;
- registrar a operação quando houver risco de alteração persistente.
