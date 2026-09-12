# Controles e hardware

O SERM V2 trata entrada como um subsistema próprio. A identidade física do
hardware não pertence a um emulador específico: MAME, RetroArch e os demais
emuladores recebem perfis derivados da mesma base.

## Princípio fundamental: SERM não deve virar um driver virtual

O SERM não deve interceptar cada botão em Python e reenviar a entrada para o
emulador. Isso acrescentaria uma camada de polling/eventos, aumentaria a
complexidade e poderia introduzir atraso desnecessário.

As bibliotecas usadas pelo SERM (`PySDL3` e `hidapi`) são bibliotecas de acesso
a dispositivos e não substituem os drivers de controle do Windows. Elas são
usadas para descoberta, identificação, normalização e testes durante a
configuração.

Quando um emulador estiver rodando, a regra é:

1. o Windows continua sendo o dono dos dispositivos físicos e de seus drivers;
2. o emulador lê o dispositivo diretamente através do backend nativo mais
   adequado;
3. o SERM prepara a configuração antes da execução, em vez de permanecer no
   caminho de cada evento de entrada;
4. nenhuma camada de virtualização de controle será criada pelo SERM sem uma
   necessidade técnica comprovada.

Isso permite, por exemplo, que o SERM use SDL3 para reconhecer e testar um
controle enquanto o MAME usa XInput para um gamepad compatível com XInput. Não
há conflito: são duas leituras do mesmo hardware em momentos/finalidades
diferentes. O SERM não deve tentar transformar a entrada SDL3 em eventos
XInput.

## Política para Windows 11

A prioridade do SERM no Windows 11 é, nesta ordem:

1. compatibilidade com o maior número de dispositivos;
2. menor latência e jitter possível;
3. configuração automática e previsível;
4. preservação de recursos específicos do dispositivo, como analógicos,
   pedais, volante, múltiplos botões e dispositivos especializados;
5. nenhuma dependência adicional quando a plataforma ou o próprio emulador já
   fornece a capacidade necessária.

O SERM deve preferir as APIs nativas do próprio emulador para a execução. A
camada Python serve principalmente para configuração, diagnóstico, persistência
e geração dos perfis.

## Política por emulador

### MAME Windows nativo

O MAME 0.289 oficial para Windows possui o provider `winhybrid`, que usa XInput
para controles compatíveis e faz fallback para DirectInput para os demais.
A documentação do MAME descreve `winhybrid` como normalmente a melhor opção no
Windows. Portanto, este é o caminho padrão do SERM para MAME.

Não devemos trocar automaticamente o MAME para `xinput` puro, porque isso
limitaria o conjunto de dispositivos a até quatro controles XInput e excluiria
ou prejudicaria periféricos que funcionam melhor por DirectInput, como
volantes e outros dispositivos especializados.

O SERM pode deixar `auto` quando quiser respeitar o comportamento padrão do
MAME, ou usar `-joystickprovider winhybrid` quando a execução precisar ser
explicitamente determinística. Essa decisão ficará na política do backend do
MAME, não na camada física do SERM.

Para o MAME, `-controller_map`/`-ctrlmap` somente será usado quando o provider
for `sdlgame`. Portanto, um mapa SDL não deve ser aplicado indiscriminadamente
a uma execução nativa `winhybrid`.

### RetroArch Windows

RetroArch possui seus próprios input/controller drivers e autoconfiguração.
No Windows, seus drivers de controle incluem XInput e DirectInput, além de SDL2
quando disponível. O SERM não deve impor SDL3 ao RetroArch.

A estratégia será descobrir o hardware com a camada comum do SERM e gerar ou
ajustar a configuração específica do RetroArch de acordo com o controller
driver efetivamente usado pelo RetroArch. Para controles XInput, a preferência
é manter o caminho XInput nativo e aproveitar a autoconfiguração existente.

### Outros emuladores

Cada integração terá uma `InputBackendPolicy` própria. O SERM não terá um
"driver universal". A política deverá declarar:

- backend nativo preferencial do emulador;
- backends de fallback;
- formato de configuração suportado;
- como o dispositivo é identificado pelo emulador;
- se existe mapeamento lógico intermediário;
- se a configuração é global, por usuário, por sistema ou por jogo;
- quais recursos analógicos/especiais são preservados.

Assim, a camada comum do SERM descreve o hardware uma vez, mas a última milha
sempre respeita a arquitetura de entrada do emulador.

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
   identidade física do dispositivo;
8. iniciar o MAME sem inserir o SERM no caminho dos eventos de entrada.

O `-listxml` continua sendo a fonte de verdade para a estrutura de entrada do
MAME. O SERM não deve inferir que uma máquina possui volante, pedal ou uma
quantidade de botões apenas pelo gênero. Quando a informação estiver no XML,
ela deve ser preservada com sua evidência.

## Monitoramento de conexão

O SERM V2 agora possui um monitor HID de baixa frequência para detectar
conexão, desconexão e troca de modo sem permanecer no caminho dos eventos do
jogo. O monitor trabalha por inventário, não abre um fluxo contínuo de reports
HID e não injeta nenhuma entrada.

Quando um dispositivo muda, a interface pode informar:

- controle conectado;
- controle desconectado;
- VID/PID e tipo de conexão;
- modelo reconhecido, quando houver evidência suficiente;
- mudança de modo quando a mesma família de dispositivo reaparece com outra
  assinatura.

A linha de base inicial é silenciosa para não produzir popups ao abrir o SERM.
Trocas posteriores geram uma notificação visual.

## 8BitDo M30: modos e identificação

O M30 Bluetooth é um caso especial porque deliberadamente se apresenta com
identidades diferentes dependendo do modo. A matriz de assinaturas usada pelo
SERM é:

| Modo | VID:PID | Conexão típica | Comando de inicialização |
|---|---|---|---|
| D-Input / Android | `2DC8:0651` | Bluetooth | `B + START` |
| D-Input / USB | `2DC8:5006` | USB | `B + START` |
| XInput | `045E:02E0` | Bluetooth | `X + START` |
| XInput | `045E:028E` | USB | `X + START` |
| Nintendo Switch | `057E:2009` | Bluetooth/USB | `Y + START` |
| macOS / DS4 | `054C:05C4` | Bluetooth/USB | `A + START` |

As assinaturas `045E:028E`, `045E:02E0`, `057E:2009` e `054C:05C4` são
identidades genéricas compartilhadas por outros controles. Portanto, o SERM
não deve afirmar que qualquer dispositivo com esses IDs é um M30. Nesses casos
a identificação é apresentada como **assinatura compatível** até que o nome do
dispositivo ou outra evidência confirme o M30.

Quando o M30 é reconhecido, o popup de conexão disponibiliza as instruções de
modo, incluindo `B + START`, `X + START`, `A + START` e `Y + START`, além dos
comandos de desligamento e pareamento. O SERM somente exibe as instruções; não
aciona os botões remotamente.

O teste físico realizado no ambiente do projeto também confirmou a importância
dessa estratégia: o mesmo M30 apareceu sucessivamente como `2DC8:0651`,
`045E:02E0`, `057E:2009`, `054C:05C4` e novamente como `2DC8:5006`, conforme o
modo escolhido. O diagnóstico preserva essas assinaturas por varredura para
que a evolução do catálogo não dependa de um único VID/PID.

## Camadas

### 1. Identidade física

`hidapi` é usado para inventário e identidade de baixo nível: VID, PID,
revisão, fabricante, produto, serial, usage, interface e caminho. A identidade
física é persistida separadamente do mapeamento lógico.

HIDAPI não é tratado como um driver de execução. O SERM não deve abrir um
handle HID de leitura contínua para competir com o emulador pelo dispositivo.
A enumeração e as leituras necessárias ao diagnóstico devem ser curtas e
controladas.

### 2. Entrada lógica de configuração

`SDL3` é o backend principal do SERM para normalizar gamepads durante a
configuração e o diagnóstico. Ele normaliza botões, eixos e D-pad e fornece
GUID, VID/PID, nome, caminho e mapeamento.

Essa camada não representa o caminho de entrada do emulador. Ela existe para o
SERM poder apresentar um layout consistente, testar botões/eixos e comparar o
hardware com os requisitos do sistema emulado.

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

### 5. Adaptação para MAME

A integração final não será feita alterando o cadastro físico do dispositivo.
O SERM produzirá artefatos de configuração do MAME a partir do perfil lógico.

O MAME 0.289 possui dois mecanismos especialmente relevantes:

- `-controller_map`/`-ctrlmap`: mapa de gamepads no formato SDL/Steam,
  utilizado pelo provider `sdlgame`;
- `-ctrlr` + `ctrlrpath`: perfil XML de controlador, onde entram `mapdevice`,
  `remap`, `port` e `newseq`.

`mapdevice` será usado quando precisarmos tornar determinístico o número
lógico de um dispositivo. Os identificadores que o MAME recebe do provider
continuam sendo a referência para esse mecanismo; VID/PID ou caminho HID do
SERM não devem ser simplesmente assumidos como equivalentes ao `device id` do
MAME.

Para isso, a implementação futura deverá capturar também o identificador
reportado pelo próprio MAME. A base física do SERM servirá para correlacionar
essa identificação com o dispositivo detectado pelo SDL/HID.

## Identidade e correlação

A identidade persistente de um dispositivo não deve ser o SDL instance ID nem
um simples índice de enumeração. Esses valores podem mudar entre execuções.

A correlação futura deverá considerar, conforme disponibilidade:

- VID/PID;
- fabricante/produto;
- versão;
- serial;
- caminho/identificador do Windows;
- SDL GUID e path;
- identificador reportado pelo emulador;
- interface/bus quando necessário para diferenciar interfaces do mesmo
  hardware.

Dois controles fisicamente idênticos sem número de série não podem ser
tratados como um único dispositivo persistente. O perfil persistente deve
permitir múltiplas instâncias e a camada de execução deve resolver a instância
presente naquele momento.

## Persistência

A migration `020_input_control_schema.sql` cria a base inicial para:

- dispositivos físicos;
- elementos físicos;
- perfis de controle;
- bindings lógicos;
- associação de perfil ao sistema/emulador.

A evolução do schema deverá manter separadas a identidade persistente, a
instância de sessão e a identidade observada pelo emulador.

## Regra importante para o MAME

O MAME pode associar entradas automaticamente de acordo com o dispositivo
conectado e pode apresentar uma organização diferente para gamepads,
volantes, teclados e outros dispositivos. O SERM não deve lutar contra essa
camada gravando permanentemente um mapeamento global.

A estratégia será gerar perfis determinísticos por dispositivo + máquina +
versão/configuração do MAME e aplicar somente a configuração necessária para
aquela execução, sempre que possível sem modificar permanentemente a
configuração global do usuário.

## Latência

O caminho crítico de jogo deve ser:

`hardware -> driver/API do Windows -> backend do emulador -> emulação`

E não:

`hardware -> Python/SERM -> tradução -> IPC/teclado virtual -> emulador`.

O segundo caminho será evitado. O SERM pode realizar testes de entrada e
monitoramento antes ou fora da execução, mas não deve fazer forwarding de cada
evento em tempo real.

## Próxima etapa

A próxima etapa da implementação deve construir o **catálogo visual de
controles**: enumerar os dispositivos conectados, apresentar a identidade
real, mostrar os elementos detectados e permitir um teste de entrada ao vivo.
Depois disso entraremos na comparação entre o layout físico e os requisitos
de cada máquina MAME, seguida pela geração do perfil `ctrlr`/mapeamento e pela
integração da política `winhybrid` do MAME.
