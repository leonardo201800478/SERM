# RetroArch no ARCADE MANAGER

**Estado:** arquitetura definida; implementação pendente.

## Objetivo

Adicionar RetroArch como runtime de execução e gerenciamento, mantendo MAME, FBNeo e Flycast standalone independentes.

## Modelo

```text
RetroArch Runtime
 ├── MAME Core
 ├── FBNeo Core
 └── Flycast Core
```

RetroArch não deve gerar cópias das entidades `machine`/`rom`.

## Core

Cada core deve possuir:

- identificador;
- nome;
- arquivo `.dll`;
- versão;
- arquitetura;
- sistema suportado;
- caminho instalado;
- origem do pacote;
- hash/tamanho quando disponível;
- status de instalação.

## Execução

Conceitualmente:

```text
Machine
 ↓
RetroArch Backend
 ↓
Core
 ↓
Content
```

O backend deve montar a linha de comando adequada e validar que o core existe antes de iniciar.

## MAME core

O core MAME não deve ser tratado como equivalente automático ao MAME standalone. Compatibilidade depende da versão do core e do conteúdo.

O scanner/reconstructor continua tendo o dataset MAME como referência do set. A compatibilidade com um core específico é uma camada de execução.

## FBNeo core

FBNeo possui seu próprio ecossistema de ROMs e regras. Não misturar automaticamente o catálogo FBNeo com o catálogo MAME.

## Flycast core

Flycast RetroArch é outra forma de execução do ecossistema Flycast. Configurações e conteúdo devem continuar separados do Flycast standalone quando necessário.

## Diretórios

O runtime deverá permitir configurar, conforme suporte da versão instalada:

- RetroArch executable;
- cores;
- system;
- assets;
- shaders;
- saves;
- states;
- downloads.

## Configuração

Não sobrescrever `retroarch.cfg` válido para simplesmente registrar configurações no banco.

O ARCADE MANAGER deve editar somente propriedades que conhece e preservar outras configurações.

## Versões

A versão do RetroArch e a versão dos cores devem ser armazenadas separadamente.

```text
RetroArch 1.x
 ├── MAME core A
 ├── FBNeo core B
 └── Flycast core C
```

## Futuro

O Download Manager deverá instalar/atualizar RetroArch e cores. O gerenciador deve validar arquivos baixados antes da instalação.
