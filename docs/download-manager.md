# Download Manager do ARCADE MANAGER

**Estado:** arquitetura definida; implementação pendente.

## Objetivo

Criar um gerenciador de downloads/atualizações reutilizável. O primeiro alvo será o ecossistema RetroArch.

A referência arquitetural é o projeto StellarUpdater/Stellar, que é um atualizador de RetroArch Nightly. O ARCADE MANAGER não deve copiar código; deve reaproveitar conceitos adequados.

## Modelo

```text
Provider
   ↓
Package Metadata
   ↓
Download Job
   ↓
Temporary File
   ↓
Validation
   ↓
Staging
   ↓
Install
   ↓
Backup / Rollback
```

## Provider

Um provider sabe descobrir pacotes disponíveis em uma fonte.

Primeiros providers previstos:

- RetroArch;
- RetroArch cores;
- assets/system quando houver fonte confiável.

## Package

Representa um artefato baixável:

- nome;
- versão;
- arquitetura;
- plataforma;
- URL/origem;
- tamanho esperado;
- hash quando disponível;
- tipo;
- dependências;
- destino.

## Download Job

Deve suportar:

- progresso;
- cancelamento;
- retry;
- timeout;
- logs;
- erro recuperável;
- validação posterior.

Operações pesadas não devem bloquear a GUI.

## Segurança

Nunca instalar diretamente do arquivo parcialmente baixado.

```text
Download
 ↓
complete
 ↓
validate
 ↓
staging
 ↓
install
```

## Atualização

Antes de atualizar:

1. detectar versão instalada;
2. descobrir versão disponível;
3. comparar;
4. confirmar compatibilidade;
5. criar backup quando necessário;
6. baixar;
7. validar;
8. instalar;
9. validar instalação.

## Rollback

Quando o artefato e o formato permitirem, preservar a versão anterior para recuperação.

## RetroArch

O primeiro fluxo será:

```text
RetroArch instalado?
       ↓
versão conhecida?
       ↓
listar versão disponível
       ↓
selecionar arquitetura
       ↓
baixar
       ↓
validar
       ↓
staging
       ↓
instalar
```

Cores terão ciclo de vida independente do executável principal.

## Relação com reconstrução

O Download Manager é uma camada separada do futuro Torrent Manager.

Torrent é uma estratégia de aquisição de ROMs residuais.

Download Manager é gerenciamento de software e pacotes do próprio ecossistema do ARCADE MANAGER.
