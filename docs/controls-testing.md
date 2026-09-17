# Guia de testes — Controles e hardware

Este documento define a validação do subsistema de controles do SERM V2 antes da construção da GUI definitiva de controles.

A arquitetura e os limites deste guia seguem `docs/controls.md`: o SERM descobre, identifica, normaliza, analisa e gera configuração; ele não cria driver virtual nem encaminha eventos de entrada em tempo real. fileciteturn844file0

## 1. Objetivo

Validar, nesta ordem:

1. enumeração física;
2. identidade do dispositivo;
3. classificação do tipo de dispositivo;
4. correlação HID ↔ SDL3;
5. inventário dos elementos físicos;
6. análise do layout;
7. reconhecimento de controles de quatro e seis botões;
8. preservação de dispositivos analógicos/especializados;
9. leitura dos requisitos de uma máquina MAME pelo ListXML;
10. comparação hardware ↔ requisitos MAME;
11. persistência do dispositivo, elementos e perfil;
12. geração futura da configuração MAME sem alterar permanentemente o hardware.

O fluxo atual do `InputControlService` consolida descoberta HID, correlação, identificação e análise de layout e expõe a comparação com os requisitos do MAME. fileciteturn845file0

## 2. Regra de ouro do teste físico

Testar **um dispositivo por vez**.

Antes de conectar o próximo dispositivo:

- fechar qualquer teste que esteja lendo o dispositivo;
- registrar o nome apresentado pelo Windows;
- registrar VID/PID quando disponível;
- registrar fabricante/produto/revisão/serial quando disponíveis;
- registrar o caminho físico quando disponível;
- registrar o GUID/path do SDL3 quando disponível;
- registrar se o dispositivo foi identificado de forma inequívoca;
- remover o dispositivo e verificar se a instância desaparece da enumeração.

Não usar índice de enumeração como identidade persistente. O índice pode mudar entre sessões. Dispositivos fisicamente idênticos sem serial precisam continuar sendo instâncias separadas. fileciteturn844file0

## 3. Matriz inicial de hardware

A primeira rodada deve utilizar os dispositivos disponíveis no ambiente de teste, preferencialmente nesta ordem:

| Ordem | Dispositivo | Classe esperada | Ponto crítico |
|---:|---|---|---|
| 1 | Xbox One | gamepad | XInput/correlação |
| 2 | DualShock 4 | gamepad | identidade e layout |
| 3 | DualSense | gamepad | identidade e elementos |
| 4 | 8BitDo Ultimate 2C | gamepad | modos de conexão |
| 5 | Machine G5 PRO | gamepad/arcade | classificação real, sem suposição |
| 6 | 8BitDo M30 | gamepad/arcade | **seis botões de face** |
| 7 | Logitech G27 | steering wheel | analógicos, volante e pedais |
| 8 | teclado | keyboard | teclas, não gamepad |
| 9 | mouse | mouse | botões/eixos, não gamepad |

A classificação acima é uma expectativa de teste, não uma identidade forçada. O catálogo deve aceitar `UNKNOWN` quando os dados disponíveis não forem suficientes para uma identificação confiável.

O M30 merece um caso dedicado: o SERM não pode reduzir um controlador de seis botões para o modelo convencional de quatro botões. O modelo lógico já possui `FACE_EXTRA_1` e `FACE_EXTRA_2` para preservar esse layout.

## 4. Teste A — enumeração HID

### Procedimento

1. Conectar somente o dispositivo em teste.
2. Executar a enumeração HID.
3. Registrar o registro retornado.
4. Desconectar o dispositivo.
5. Executar novamente.

### Resultado esperado

- conectado → exatamente uma instância correspondente aparece;
- desconectado → a instância desaparece;
- VID/PID são preservados quando fornecidos pelo dispositivo;
- fabricante, produto, versão e serial são preservados quando disponíveis;
- ausência de serial não causa colisão automática entre dois dispositivos iguais;
- nenhuma leitura contínua permanece aberta depois da enumeração.

HIDAPI é utilizado para inventário/identidade e diagnóstico, não como caminho de execução do emulador. fileciteturn844file0

## 5. Teste B — classificação

Para cada dispositivo, validar uma destas classes:

- `GAMEPAD`;
- `ARCADE_STICK`;
- `FIGHTING_CONTROLLER`;
- `STEERING_WHEEL`;
- `KEYBOARD`;
- `MOUSE`;
- `LIGHTGUN`;
- `SPECIALIZED`;
- `UNKNOWN`.

### Critério

A classe deve ser determinada pelos dados observáveis. Não classificar um volante como gamepad apenas porque possui botões; não classificar um M30 como gamepad de quatro botões apenas pelo nome genérico.

## 6. Teste C — correlação HID ↔ SDL3

Quando o dispositivo também for reconhecido pelo SDL3, executar a correlação.

Validar:

- VID/PID coincidentes aumentam a confiança;
- versão, fabricante e produto podem reforçar a correlação;
- GUID/path SDL podem reforçar a correlação;
- um dispositivo lógico não pode ser associado simultaneamente a dois físicos na mesma correlação;
- candidatos ambíguos devem permanecer sem correlação automática;
- uma correlação abaixo do limiar não deve ser promovida a identificação confirmada.

A identidade persistente não deve depender de SDL instance ID ou de índice de enumeração. fileciteturn844file0

## 7. Teste D — inventário de elementos

Para cada gamepad:

- pressionar cada botão físico individualmente;
- mover cada stick em todas as direções;
- testar D-pad;
- testar triggers;
- verificar shoulders;
- verificar Start/Select/Back;
- verificar todos os botões extras.

Para o G27:

- volante centro/esquerda/direita;
- acelerador;
- freio;
- embreagem, se exposta;
- botões do volante;
- demais eixos/controles expostos pelo driver.

Para teclado:

- teclas alfanuméricas;
- setas;
- modificadores;
- teclas especiais relevantes.

Para mouse:

- movimento X/Y;
- botão esquerdo;
- botão direito;
- botão central;
- botões adicionais, se existirem;
- wheel/scroll, se exposto.

### Critério

O SERM deve registrar o elemento observado sem transformar automaticamente um eixo analógico em botão digital ou vice-versa.

## 8. Teste E — análise do layout

O `InputLayoutAnalyzer` deve produzir um resumo consistente com os elementos observados.

Validar pelo menos:

| Dispositivo | Resultado esperado |
|---|---|
| Gamepad comum | perfil `four-button-gamepad` quando houver quatro faces utilizáveis |
| M30 | `six-button-gamepad` e seis face buttons |
| G27 | `steering-wheel` |
| teclado | `keyboard` |
| mouse | `mouse` |
| hardware incompleto/desconhecido | `custom-gamepad` ou `unknown`, conforme evidência |

O resultado não deve apagar elementos extras apenas para encaixar o dispositivo em um perfil convencional.

## 9. Teste F — caso obrigatório do M30

Este é um teste de aceitação específico.

### Procedimento

1. Conectar o M30.
2. Enumerar HID e SDL3.
3. Correlacionar os registros.
4. Analisar o layout.
5. Acionar os seis botões de face individualmente.

### Deve resultar em

- seis controles de face identificáveis;
- `has_six_face_buttons = true`;
- `profile_kind = six-button-gamepad`;
- os dois controles extras não podem ser descartados;
- a sugestão de mapeamento deve preservar a ordem lógica dos seis controles.

Falha neste caso bloqueia a passagem para a etapa de geração automática de perfil MAME.

## 10. Teste G — MAME ListXML

Selecionar uma máquina MAME real e ler somente essa máquina através de `MameControlService`.

O ListXML é a fonte de verdade da estrutura de entrada do MAME. fileciteturn844file0

Validar:

- tipo de controle;
- jogador;
- quantidade de botões;
- `ways`;
- limites mínimo/máximo;
- sensitivity;
- keydelta;
- reverse;
- atributos adicionais presentes no XML.

Selecionar máquinas com perfis diferentes, pelo menos:

1. gamepad de quatro botões;
2. máquina com seis ou mais botões;
3. máquina com joystick de 8-way;
4. máquina com dial/paddle/trackball;
5. máquina com volante/pedal, quando disponível.

Não usar gênero, nome ou categoria da máquina para inventar requisitos que não estejam no XML.

## 11. Teste H — comparação hardware ↔ MAME

Para cada combinação de hardware e máquina, executar `InputControlService.map_mame()`.

Classificar o resultado como:

- **compatível** — hardware atende aos requisitos principais;
- **compatível com ressalvas** — funciona, mas existe perda ou adaptação;
- **incompatível** — requisito essencial não é atendido;
- **indeterminado** — dados insuficientes para decisão segura.

Exemplos esperados:

- gamepad de quatro botões × máquina de quatro botões → compatível;
- M30 × máquina de seis botões → compatível sem descartar os dois extras;
- gamepad × máquina que exige trackball → incompatibilidade/ressalva, conforme requisitos;
- G27 × máquina de volante/pedais → candidato forte;
- teclado × máquina cujo controle principal é teclado → candidato forte;
- mouse × máquina que exige mouse → candidato forte.

O mapper deve explicar a decisão com score, avisos e sugestões, e não apenas retornar verdadeiro/falso.

## 12. Teste I — persistência

Depois da descoberta, persistir:

- dispositivo físico;
- elementos físicos;
- perfil lógico;
- bindings.

Executar o mesmo teste duas vezes.

### Resultado esperado

- a segunda execução atualiza a mesma identidade quando for realmente o mesmo dispositivo;
- elementos antigos que não existem mais não permanecem silenciosamente no inventário atual;
- dois dispositivos iguais sem serial podem coexistir;
- perfil e bindings permanecem associados ao dispositivo correto;
- nenhuma nova biblioteca é necessária para persistência.

A migration `020_input_control_schema.sql` é a base inicial dessa persistência. fileciteturn844file0

## 13. Teste J — remoção e reconexão

Para dispositivos sem serial, este teste é obrigatório.

1. conectar A;
2. registrar identidade;
3. desconectar A;
4. conectar B, fisicamente idêntico a A;
5. comparar as identidades;
6. verificar se a sessão distingue A de B;
7. reconectar A e verificar quais sinais permitem correlacioná-lo novamente.

O SERM não deve declarar que A e B são o mesmo dispositivo somente porque VID/PID são iguais.

## 14. Teste K — backend do MAME

A execução real deve respeitar a política do backend:

- Windows/MAME: `winhybrid` como caminho preferencial;
- XInput para dispositivos compatíveis;
- DirectInput como fallback;
- não forçar XInput puro;
- `controller_map`/`ctrlmap` somente quando o provider for `sdlgame`;
- `ctrlr`/`mapdevice`/`remap` somente na etapa de configuração específica do MAME.

O SERM não deve alterar a rota de eventos em tempo real. fileciteturn844file0

## 15. Teste L — execução real no MAME

Depois que A–K estiverem verdes:

1. selecionar uma máquina simples;
2. selecionar o dispositivo físico;
3. gerar a configuração temporária;
4. iniciar o MAME;
5. verificar os controles dentro do próprio MAME;
6. fechar o MAME;
7. verificar que a configuração global não foi corrompida;
8. repetir com outra máquina;
9. repetir com outro dispositivo.

A execução deve ser testada com pelo menos:

- gamepad XInput;
- gamepad não-XInput/DirectInput;
- M30;
- G27;
- teclado;
- mouse.

## 16. Critérios de bloqueio

Não avançar para geração automática de perfis se ocorrer qualquer um destes problemas:

- identidade física instável ou incorreta;
- dois dispositivos iguais tratados como uma única instância;
- M30 reduzido para quatro botões;
- G27 classificado como gamepad sem justificativa;
- elemento analógico perdido;
- correlação ambígua aceita automaticamente;
- requisito MAME inferido sem evidência do ListXML;
- mapper declarar compatibilidade quando falta um requisito essencial;
- persistência misturar dispositivos;
- SERM precisar permanecer executando para encaminhar eventos ao emulador;
- configuração global do MAME ser alterada sem necessidade explícita.

## 17. Ordem de implementação após os testes

A evolução deve seguir esta ordem:

1. backend de descoberta e diagnóstico;
2. catálogo visual de controles;
3. teste de entrada ao vivo na GUI;
4. persistência visual de dispositivos/perfis;
5. seleção de uma máquina MAME;
6. comparação visual hardware × requisitos;
7. geração do perfil específico;
8. execução controlada do MAME;
9. validação final em diferentes tipos de hardware.

A documentação arquitetural já define o catálogo visual como a próxima etapa natural antes da geração de `ctrlr`/mapeamentos. fileciteturn844file0

## 18. Registro de execução

Para cada dispositivo, manter uma ficha com:

```text
Data:
Dispositivo:
Conexão: USB / Bluetooth / outra
VID:
PID:
Versão:
Fabricante:
Produto:
Serial:
Path:
SDL GUID:
SDL Path:
Classe detectada:
Perfil de layout:
Quantidade de botões:
Quantidade de eixos:
Hats/D-pad:
Face buttons:
Resultado HID:
Resultado SDL:
Resultado correlação:
Resultado layout:
Resultado MAME:
Resultado persistência:
Resultado execução real:
Observações:
```

A ficha deve registrar fatos observados, não apenas a expectativa do teste.

## 19. Automação

A suíte rápida deve permanecer determinística e sem hardware físico. Testes que dependem de dispositivos reais, MAME instalado, arquivos ListXML grandes ou execução de emuladores pertencem à camada estendida/integrada.

Os testes unitários devem cobrir principalmente:

- identidade;
- classificação;
- correlação;
- análise de layout;
- parsing SDL;
- parsing de requisitos MAME;
- mapper;
- persistência;
- políticas de backend.

Os testes físicos devem ser executados manualmente por dispositivo e registrados neste roteiro. O objetivo é evitar que uma execução lenta ou dependente de hardware torne a suíte normal do projeto inadequada para desenvolvimento diário.
