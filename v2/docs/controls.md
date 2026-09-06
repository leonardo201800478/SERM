# Controles e perfis do ARCADE MANAGER

**Estado:** arquitetura definida; implementação pendente.

## Objetivo

Criar um sistema de configuração de controles que permita configurar um jogo e reaproveitar essa configuração para outros jogos com o mesmo modelo de controle.

O sistema não deve ser apenas um editor de arquivos `.cfg`/`.ini`. Deve conhecer dispositivos, perfis, famílias de jogos e particularidades do hardware arcade.

## Modelo

```text
Physical Device
      ↓
Hardware Profile
      ↓
Control Profile
      ↓
Control Family
      ↓
Machine Mapping
      ↓
Backend Configuration
```

## Physical Device

Representa o equipamento detectado no Windows, por exemplo:

- teclado;
- gamepad;
- arcade stick;
- Logitech G27;
- pedais;
- lightgun;
- joystick analógico.

O identificador físico deve ser separado do nome amigável para permitir estabilidade dos perfis.

## Hardware Profile

Descreve capacidades físicas do dispositivo:

```text
G27
 ├── steering axis
 ├── accelerator
 ├── brake
 ├── clutch
 └── H-pattern shifter
```

## Control Profile

Descreve a intenção do controle:

```text
Fighting 6 Buttons
 ├── Up
 ├── Down
 ├── Left
 ├── Right
 ├── LP
 ├── MP
 ├── HP
 ├── LK
 ├── MK
 └── HK
```

O perfil não deve depender de um único emulador.

## Control Family

Agrupa jogos com controles equivalentes.

Exemplos:

- Street Fighter;
- Mortal Kombat;
- Neo Geo;
- Fighting 6B;
- Beat'em Up 2P;
- Shooter;
- Lightgun;
- Driving;
- Motorcycle;
- Flight Stick;
- Spinner;
- Trackball.

A família pode ser criada manualmente ou futuramente sugerida com base nos dados do dataset.

## Aplicação em lote

Exemplo:

```text
Street Fighter II
    ↓
configurar controles
    ↓
salvar "Street Fighter"
    ↓
aplicar à família
    ↓
SF2CE
SF2HF
SF2T
SFZ2
SFZ3
...
```

Antes de aplicar, o sistema deve mostrar o conjunto de máquinas afetadas e permitir excluir máquinas individualmente.

## Herança

Prioridade:

```text
Global
  ↓
Control Family
  ↓
Machine
  ↓
Machine override explícito
```

O nível mais específico vence.

## Backends

O perfil lógico será convertido para a configuração do backend:

```text
Control Profile
      ↓
MAME mapping
Flycast mapping
FBNeo mapping
Supermodel mapping
RetroArch mapping
```

Nenhuma configuração de um backend deve ser considerada o modelo canônico do controle.

## MAME

A implementação deve considerar configurações globais e por jogo/família quando suportadas pelo MAME.

O objetivo é eliminar o trabalho manual de editar dezenas de arquivos individuais sem destruir configurações específicas que já existam.

## Segurança

- preservar arquivos de configuração existentes;
- criar backup antes de alterações destrutivas;
- nunca alterar ROMs;
- mostrar o diff lógico antes de operações em lote quando possível;
- registrar quais máquinas foram alteradas;
- permitir desfazer a operação em lote por meio de backup/manifesto.

## Futuro

O sistema poderá associar automaticamente uma família a partir de dados de input do MAME, fabricante, sistema, série e outras características do dataset, mas sugestões automáticas devem ser explicitamente classificadas como sugestões até validação.
