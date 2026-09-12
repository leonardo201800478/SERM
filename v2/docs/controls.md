# Controles e hardware

O SERM V2 trata entrada como um subsistema próprio. A identidade física do
hardware não pertence a um emulador específico: MAME, RetroArch e os demais
emuladores receberão perfis derivados da mesma base.

## Fase atual: MAME

A primeira integração é com MAME. O objetivo é chegar a um fluxo no qual o
SERM consiga:

1. detectar o dispositivo físico conectado;
2. identificar fabricante, modelo, VID/PID, revisão, serial quando disponível,
   caminho e GUID do backend;
3. reconhecer a classe do dispositivo sem confundir gamepad, volante,
   teclado, mouse ou periféricos especializados;
4. ler os elementos físicos e normalizá-los em controles lógicos;
5. ler do `-listxml` os requisitos reais da máquina MAME;
6. comparar requisitos da máquina com o layout lógico disponível;
7. gerar um perfil específico para aquela máquina/emulador sem alterar a
   identidade física do dispositivo.

O `-listxml` continua sendo a fonte de verdade para a estrutura de entrada do
MAME. O SERM não deve inferir que uma máquina possui volante, pedal ou uma
quantidade de botões apenas pelo gênero. Quando a informação estiver no XML,
ela deve ser preservada com sua evidência.

## Camadas

### 1. Identidade física

`hidapi` é usado para inventário e identidade de baixo nível: VID, PID,
revisão, fabricante, produto, serial, usage, interface e caminho. A identidade
física é persistida separadamente do mapeamento lógico.

### 2. Entrada lógica

`SDL3` é o backend principal para gamepads. Ele normaliza botões, eixos e
D-pad e fornece GUID, VID/PID, nome, caminho e mapeamento. O SERM mantém essa
camada separada da identidade HID para não depender de uma única API.

A SDL_GameControllerDB é uma fonte comunitária de mapeamentos, não a base
mestre do SERM. Um mapeamento externo pode sugerir uma normalização, mas não
substitui a identidade física nem um perfil explicitamente salvo pelo usuário.

### 3. Requisitos do MAME

`MameControlService` lê os nós `<input>` e `<control>` do ListXML em streaming.
São preservados, entre outros:

- tipo do controle;
- jogador;
- quantidade de botões;
- ways;
- minimum/maximum;
- sensitivity;
- keydelta;
- reverse;
- demais atributos originais do XML.

Isso permite trabalhar também com controles analógicos e periféricos que não
cabem no modelo de gamepad.

### 4. Perfil lógico

`ControlProfile` representa a camada intermediária entre hardware e emulador.
Ele associa elementos físicos a controles como D-pad, face buttons, Start,
Select/Back, shoulders, triggers, sticks, steering, accelerator, brake, coin,
service e test.

Um perfil pode posteriormente ser projetado para a sintaxe específica do
MAME, inclusive arquivos `ctrlr` e mecanismos de associação de dispositivos,
sem transformar essa sintaxe em parte do modelo de domínio.

## Persistência

A migration `020_input_control_schema.sql` cria a base inicial para:

- dispositivos físicos;
- elementos físicos;
- perfis de controle;
- bindings lógicos;
- associação de perfil ao sistema/emulador.

## Regra importante para o MAME

O MAME pode associar entradas automaticamente de acordo com o dispositivo
conectado e pode apresentar uma organização diferente para gamepads,
volantes, teclados e outros dispositivos. O SERM não deve lutar contra essa
camada gravando permanentemente um mapeamento global.

A estratégia será gerar perfis determinísticos por dispositivo + máquina +
versão/configuração do MAME e aplicar somente a configuração necessária para
aquela execução.

## Próxima etapa

A próxima etapa da implementação deve construir o **catálogo visual de
controles**: enumerar os dispositivos conectados, apresentar a identidade
real, mostrar os elementos detectados e permitir um teste de entrada ao vivo.
Depois disso entraremos na comparação entre o layout físico e os requisitos
de cada máquina MAME, seguida pela geração do perfil `ctrlr`/mapeamento.
