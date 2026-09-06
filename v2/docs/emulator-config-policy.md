# Política de configuração dos emuladores

**Referência:** 21/08/2026

## Regra principal

O MAME Set Builder não deve regenerar arquivos de configuração que já existem e estão válidos. A existência de uma configuração do usuário é presumida como intencional.

```text
EXISTE?
 ├─ não → gerar somente se houver gerador oficial configurado
 └─ sim
     ↓
   VALIDAR
     ├─ válido → reutilizar/importar
     └─ inválido → backup → gerar somente se houver gerador
```

## Arquivo inválido

Antes da regeneração, o arquivo inválido é preservado como:

```text
<arquivo>.corrupt.<timestamp>.bak
```

Se não existir um comando de geração apropriado, o sistema mantém o arquivo inválido e registra a situação. Ele não inventa conteúdo e não remove o arquivo.

## Execução

A geração é executada com `shell=False`, `stdin=DEVNULL`, stdout/stderr capturados, `CREATE_NO_WINDOW` no Windows, timeout e validação do artefato após o processo.

## Fontes por emulador

### MAME

`mame.ini` e arquivos existentes são reutilizados. `-createconfig` é reservado para recuperação de configuração ausente ou inválida. O `-listxml` é artefato de dataset, não configuração de usuário.

### Flycast

`emu.cfg` e mappings existentes são reutilizados. O projeto não deve criar um `flycast.xml` artificial.

### Supermodel

`Supermodel.ini` é configuração. `Games.xml` descreve jogos/ROMs e `Music.xml` descreve músicas customizadas; são artefatos distintos e não devem ser sobrescritos como se fossem uma única configuração.

### FinalBurn Neo

A configuração principal é reutilizada. DAT/listinfo são artefatos de catálogo. Só podem ser gerados quando estiverem ausentes ou inválidos e houver comando explícito de geração disponível para a versão instalada.

## Implementação

A política é implementada por `app/core/services/emulator_config_service.py`. `EmulatorConfigService` recebe caminho, validador e, quando aplicável, comando de geração, mantendo a regra de segurança independente dos collectors específicos.

## Estado

### Implementado

- reutilização de configuração válida;
- geração condicional;
- backup de arquivo inválido;
- execução silenciosa e segura;
- validação pós-geração;
- testes unitários da política.

### Pendente

- conectar a política ao discovery/importer;
- definir comandos concretos de geração para cada versão instalada de Flycast, Supermodel e FBNeo;
- persistir origem, versão e data dos artefatos no banco.
