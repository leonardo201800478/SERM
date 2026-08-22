# MAME SET BUILDER — PROMPT MESTRE v4

**Estado de referência:** 21/08/2026

## 1. Fonte de verdade

O código do repositório `leonardo201800478/mame-set-builder` é a fonte de verdade da implementação.

Antes de alterar código:

1. consultar o GitHub;
2. consultar modelos e schema afetados;
3. consultar consumidores;
4. verificar commits recentes;
5. preservar funções ativas;
6. implementar e testar;
7. atualizar a documentação apenas com fatos verificados.

Documentação antiga não supera o código.

## 2. Objetivo

Construir uma aplicação desktop Python/Qt capaz de:

```text
MAME/listxml + fontes dos emuladores
 ↓
dataset / discovery
 ↓
filtros
 ↓
seleção
 ↓
Scan físico
 ↓
current_scan.jsonl
 ↓
reconstrução
 ↓
Meu Set
 ↓
residual
 ↓
Torrent futuro
```

O produto é um gerenciador de dataset, auditor e construtor de sets orientado a dependências.

## 3. Machine ≠ arquivo

Machine é entidade lógica. Arquivo é artefato físico.

Nunca assumir `machine == machine.zip` sem resolver ROMs compartilhadas, parent/clone, BIOS, devices, samples, disks e CHDs.

## 4. FULLSET

O FULLSET/origens são **somente leitura**. É proibido modificar, mover, renomear, apagar ou sobrescrever arquivos de origem durante Scan ou reconstrução.

## 5. Configurações e artefatos dos emuladores

Arquivos de configuração existentes são preservados. **Nunca regenerar ou sobrescrever uma configuração válida apenas para alimentar o banco.**

A política obrigatória é:

```text
arquivo existe
   ↓
validar
   ├── válido → reutilizar/importar
   └── inválido → preservar backup → gerar somente se houver gerador oficial

arquivo não existe
   ↓
gerar somente se houver gerador oficial
```

Se não houver gerador configurado, o sistema não inventa conteúdo e não apaga o arquivo inválido.

A implementação central fica em `app/core/services/emulator_config_service.py`.

### Emuladores

- **MAME:** reutilizar `mame.ini` e arquivos existentes; `-createconfig` é recuperação, não operação normal de importação.
- **Flycast:** reutilizar `emu.cfg` e mappings; não criar XML artificial.
- **Supermodel:** reutilizar `Supermodel.ini`; `Games.xml` e `Music.xml` são artefatos diferentes de configuração.
- **FBNeo:** reutilizar configuração existente; DAT/listinfo são artefatos de catálogo e só podem ser gerados quando ausentes/inválidos e quando o comando correspondente estiver explicitamente definido.

A geração deve ser silenciosa no Windows, sem `shell=True`, com `stdin=DEVNULL`, stdout/stderr capturados e validação posterior.

Arquivo inválido é preservado como `.corrupt.<timestamp>.bak` antes da tentativa de regeneração.

## 6. Scan ROMs

O Scan descobre e registra o estado físico. Seu resultado `current_scan.jsonl` é a ponte para a reconstrução.

Quando disponível, o manifesto deve preservar:

- machine;
- ROM esperada;
- tamanho;
- CRC;
- SHA-1;
- status;
- `source.kind`;
- `source.archive`;
- `source.member`;
- demais dados necessários para reuso da origem.

A reconstrução não deve repetir uma varredura global para descobrir aquilo que o Scan já registrou.

## 7. Reconstrução — arquitetura obrigatória

A reconstrução deve ser segura, sequencial e orientada ao manifesto:

```text
current_scan.jsonl
      ↓
1 machine
      ↓
1 ROM
      ↓
source registrada
      ↓
streaming em blocos
      ↓
CRC + tamanho + SHA-1 quando disponível
      ↓
staging no destino
      ↓
próxima ROM
      ↓
ZIP completo
      ↓
validação final
      ↓
os.replace()
      ↓
próxima machine
```

### Regras

- uma machine por vez;
- uma ROM por vez;
- RAM limitada por buffer;
- nenhuma cópia permanente em cache;
- staging apenas no destino;
- origem somente leitura;
- conteúdo deve ser validado antes de publicação;
- falhas devem permitir retry limitado;
- arquivo parcial nunca deve ser considerado concluído.

## 8. Correção de nome

Se a ROM encontrada possui conteúdo correto mas nome diferente, o destino recebe o nome esperado pelo set. Nunca renomear a origem.

## 9. ROM compartilhada

Se uma machine precisa de uma ROM presente em outra machine, usar a origem registrada no Scan. Transferir somente a ROM necessária para o destino da machine em processamento.

Não construir cache permanente nem copiar coleções intermediárias desnecessárias.

## 10. Integridade

Verificar tamanho e CRC. Quando SHA-1 existir no dataset, utilizar também SHA-1 para confirmação. Sempre que possível calcular os hashes durante o mesmo streaming da transferência.

## 11. Set types

A interface deve oferecer:

- Split — padrão;
- Merged;
- Non-Merged.

A implementação deve respeitar a semântica MAME de parent/clone. Não considerar a semântica final validada sem testes reais com fixtures.

## 12. Residual

Após reconstrução:

```text
concluído → destino
não resolvido → current_reconstruction.jsonl
```

O residual deve conter **somente** ROMs/dependências ainda não resolvidas. O `current_scan.jsonl` original permanece preservado.

O residual será a entrada da futura aba Torrent.

## 13. GUI

A GUI apresenta e coordena; regras de negócio ficam em services/modelos.

Menus contextuais de widgets devem ser encapsulados no próprio widget para manutenção e reuso.

Operações pesadas devem rodar fora da thread da interface, com progresso, logs e cancelamento cooperativo.

## 14. Banco

SQLite e migrations atuais são autoridade. Nunca alterar SQL por suposição baseada em documentação antiga. Antes de alterar schema, auditar modelos, services e consumidores.

## 15. listxml

O listxml do mesmo MAME é a fonte estrutural primária. Preservar os elementos necessários ao produto. Não reconstruir XML a partir de um modelo reduzido quando isso perder informação.

## 16. Filtros

Separar classificação de seleção. A GUI produz configuração; a camada de negócio executa as regras.

## 17. Torrent

qBittorrent é futuro. Deve consumir o residual e adquirir somente os artefatos necessários. Não assumir que torrent metadata está disponível antes de obtê-la e não selecionar arquivos por posição arbitrária.

## 18. Estado real em 21/08/2026

### Implementado

- dataset/listxml e modelos em evolução;
- SQLite/migrations;
- filtros e classificação;
- geração de XML filtrado;
- Scan ROMs;
- manifesto `current_scan.jsonl`;
- origem física no resultado do Scan quando disponível;
- aba Reconstrução;
- serviço de reconstrução;
- opções Split/Merged/Non-Merged;
- streaming e staging como arquitetura da reconstrução;
- política central de preservação/regeneração segura de arquivos de configuração;
- testes unitários da política de configuração.

### Em validação

- protocolo transacional completo;
- validação pós-escrita/retry;
- residual preciso;
- recuperação após interrupção;
- semântica completa dos três layouts;
- todos os `source.kind`;
- integração do discovery/importer com MAME, Flycast, Supermodel e FBNeo.

### Pendente

- conectar o `EmulatorConfigService` ao fluxo de discovery/importação;
- fechar comandos específicos de geração por versão instalada de Flycast, Supermodel e FBNeo;
- persistir no banco origem/versão/data dos artefatos importados;
- Torrent/qBittorrent;
- Dependency Resolver completo;
- integração completa de BIOS/device/sample/disk/CHD;
- testes de integração abrangentes.

## 19. Regras de implementação

- Não remover função ativa sem justificativa e auditoria.
- Não duplicar entidades/modelos existentes.
- Não colocar SQL de negócio na GUI.
- Não fazer trabalho de I/O global quando o manifesto já contém a origem.
- Não otimizar por paralelismo sem medir I/O e memória.
- Não afirmar que código foi testado se não foi executado.
- Ao modificar um arquivo, verificar os arquivos dependentes.
- Nunca sobrescrever configuração válida para gerar dados.
- Nunca apagar configuração inválida antes de criar backup.
- Sempre documentar o estado real, distinguindo **implementado**, **em validação** e **pendente**.
