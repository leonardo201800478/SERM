# Force Feedback e FFBArcadePlugin

**Estado:** arquitetura definida; implementação pendente.

## Objetivo

Integrar Force Feedback ao ARCADE MANAGER como uma camada transversal aos emuladores e permitir perfis por jogo e por família.

## Plugin de referência

O primeiro plugin suportado será o **FFBArcadePlugin**, utilizando como referência o fork:

`leonardo201800478/FFBArcadePlugin`

O plugin possui integração com MAME, Supermodel, Flycast e outros ambientes e suporta diversos jogos arcade com FFB específico.

## Arquitetura

```text
Game
 ↓
Arcade FFB Profile
 ↓
Plugin Compatibility
 ↓
FFBArcadePlugin
 ↓
Physical Device
```

O plugin não é um emulador.

## Perfis

Herança:

```text
Global FFB
    ↓
Family FFB
    ↓
Game FFB
```

Um perfil de jogo pode substituir somente alguns parâmetros e herdar os demais.

## Parâmetros possíveis

A camada de domínio deve suportar, quando aplicável ao plugin/backend:

- MinForce;
- MaxForce;
- Feedback length;
- Rumble;
- Reverse Rumble;
- PowerMode;
- Alternative FFB;
- Alternative MinForce/MaxForce;
- Input Support;
- parâmetros específicos do jogo.

Nem todo parâmetro deve ser exibido para todo jogo. A GUI deve usar capabilities do plugin.

## Compatibilidade

O plugin possui uma lista de jogos suportados. Essa lista deve ser tratada como fonte de compatibilidade do plugin e não como catálogo MAME completo.

Exemplos de categorias importantes:

- Daytona;
- Hard Drivin';
- OutRun;
- Sega Rally;
- Sega Touring Car;
- San Francisco Rush;
- F-1 Grand Prix;
- Power Drift;
- jogos Flycast suportados.

## MAME

A integração deve respeitar a forma de saída exigida pelo plugin e não assumir que toda versão do MAME possui exatamente o mesmo comportamento.

Configuração deve ser validada antes de iniciar o jogo.

## Supermodel

Quando o FFBArcadePlugin for usado em substituição ao FFB nativo, a configuração deve evitar conflito entre os dois mecanismos.

## Flycast

A camada deve separar FFB nativo do Flycast e FFB provido pelo plugin. O usuário deve escolher explicitamente qual mecanismo utilizar.

## Dispositivo

FFB Profile não deve fixar um dispositivo específico quando isso não for necessário. O perfil de hardware pode indicar o dispositivo, enquanto o perfil de FFB define o comportamento.

## Segurança

- nunca instalar DLL arbitrariamente em diretórios sem validação;
- verificar arquitetura 32/64 bits;
- preservar arquivos existentes;
- fazer backup quando uma instalação substituir arquivos;
- registrar versão do plugin;
- validar compatibilidade com o backend antes de ativar.

## Evolução

A primeira implementação deve começar por descoberta/instalação e compatibilidade. Depois serão adicionados perfis de FFB e aplicação automática por família.
