# SERM — PROMPT MESTRE

**Produto:** Strife Emulator and Roms Manager (SERM)
**Repositório histórico:** `leonardo201800478/mame-set-builder`
**Referência:** 29/08/2026

## 1. Identidade

O produto chama-se **Strife Emulator and Roms Manager — SERM**.

O nome `mame-set-builder` permanece somente como identidade histórica do repositório. Novos textos, títulos de janela, documentação e funcionalidades devem utilizar SERM.

O SERM nasceu como construtor de sets MAME e evoluiu para uma plataforma de:

- auditoria de bibliotecas;
- reconstrução de conteúdo;
- gerenciamento de emuladores;
- RetroArch e cores;
- BIOS;
- shaders/overlays;
- catálogos externos;
- controles/hardware/FFB;
- downloads e integrações.

## 2. Fonte de verdade

O código atual do GitHub é a fonte de verdade.

Antes de modificar qualquer componente:

1. consultar o código atual no GitHub;
2. consultar modelos/schema afetados;
3. consultar consumidores;
4. verificar funções ativas e legadas;
5. preservar comportamento funcional;
6. implementar em blocos pequenos;
7. executar testes da arquitetura atual;
8. validar o fluxo real;
9. atualizar documentação somente com fatos verificados.

Não manter testes ou documentação apenas para preservar código legado que já não faz parte da arquitetura atual.

## 3. Arquitetura

```text
GUI / Qt
 ↓
Application Services
 ↓
Domains
├── Library / Dataset / Scan
├── Reconstruction
│   ├── MAME
│   ├── No-Intro
│   ├── Redump
│   └── Amiga / WHDLoad / Retroplay
├── RetroArch BIOS
├── Emulator / Backend / Core
├── Archive / Package
├── Catalog Manager
├── Controls / Hardware / FFB
└── Presentation / Shader / Overlay
```

GUI não deve conter regras de negócio nem I/O pesado.

## 4. Reconstrução

MAME e consoles são domínios separados.

### MAME

Fonte: LISTXML + Scan + `current_scan.jsonl` + Dependency Resolver.

ROMs, BIOS, devices, samples, disks e CHDs seguem as regras MAME já estabelecidas.

### Consoles

```text
No-Intro → cartuchos / mídias digitais
Redump   → discos ópticos
Amiga    → WHDLoad / Retroplay
```

No-Intro usa DAT/XML e hashes. Redump possui modelo orientado a discos. Amiga possui catálogo e formatos próprios.

Não criar um parser universal que apague diferenças semânticas entre fontes.

## 5. No-Intro

Implementação futura prioritária.

O DAT deve ser tratado como fonte de verdade para o conjunto.

Modelo mínimo:

```text
Game
├── name
├── cloneof / parent
└── ROM[]
    ├── name
    ├── size
    ├── CRC32
    ├── MD5
    └── SHA1
```

Matching por hash/tamanho. Nome não é identidade primária.

O DAT Mega Drive/Genesis fornecido em 29/08/2026 deve ser usado como fixture real da primeira implementação.

## 6. Redump

Implementação futura prioritária após validar a fonte de download/catalogação atual.

Modelo orientado a `Disc`, preservando sistema, título, edição, versão, serial, região, idiomas e hashes/metadados disponíveis.

CHD é o formato de saída preferencial para discos quando a conversão puder preservar corretamente a mídia.

Não assumir endpoints de download sem validação.

## 7. Amiga / WHDLoad / Retroplay

Possui domínio próprio. O catálogo deve contemplar pacote, versão, variante, plataforma/chipset, idioma e arquivo.

Formatos LHA/LZX devem ter suporte explícito quando entrarem em escopo.

## 8. RetroArch BIOS

Domínio separado dos catálogos No-Intro/Redump.

O catálogo deve derivar de `.info`/fontes confiáveis quando aplicável.

Fluxo:

```text
catalogar → scan/hash → classificar → reconstruir/instalar somente o necessário
```

Prioridade: rapidez, limpeza e ausência de reprocessamento global desnecessário.

## 9. Catalog Manager

O Catalog Manager mantém referências locais atualizadas.

```text
Provider
 ↓
Download catálogo
 ↓
Validação
 ↓
Parser específico
 ↓
Cache/versionamento
 ↓
Reconstruction / Scan
```

Catálogo não é cache de ROMs. Atualização automática deve baixar apenas metadados/referências.

Providers planejados:

- No-Intro Dat-o-MATIC;
- Redump;
- Amiga / Retroplay;
- MAME/listxml.

Falha de atualização não deve destruir o catálogo local anterior válido.

## 10. ArchiveService

Serviço comum para operações de ZIP/7Z/RAR.

```text
ZIP → zipfile
7Z  → 7z.exe preferencial / py7zr fallback
RAR → backend externo quando necessário
```

Deve suportar inspeção, teste, extração, criação e edição controlada.

ZIP é crítico para reconstrução MAME e No-Intro.

CHD não é archive genérico e permanece em `CHDService`.

## 11. RetroArch / cores

A Home está concluída.

Não reintroduzir botões sem função, carregamento prévio desnecessário ou lógica duplicada.

Atualização de cores:

```text
índice oficial
 ↓
CRC local × remoto
 ↓
somente divergentes selecionados
 ↓
download
 ↓
CRC
 ↓
instalação
```

Falha de core: três tentativas consecutivas; após três falhas, registrar o core e continuar a fila.

## 12. Presentation

```text
Sistema
├── Core
├── Override
├── Shader
└── Overlay
```

Shaders de terceiros são baixados diretamente de seus repositórios e não incorporados ao repositório do SERM.

Priorizar CRT limpo, fiel e leve. Evitar presets agressivos, reflexos e camadas pesadas que aumentem processamento/input lag.

Aspect ratio do shader representa o sistema/emulação, não a tela do usuário. Nunca forçar 16:9 por padrão.

## 13. Configuração de emuladores

Preservar configurações válidas. Alterar somente propriedades suportadas. Fazer backup antes de substituir configuração inválida.

Diretórios e schemas devem ser específicos de cada emulador; não assumir que uma opção MAME existe em Flycast, Supermodel, FBNeo ou RetroArch.

## 14. Downloads

```text
Provider
 ↓
Package metadata
 ↓
Download
 ↓
Integrity
 ↓
Staging
 ↓
Install
```

Download não deve publicar diretamente no destino final antes da validação.

## 15. Testes

A suíte deve representar somente a arquitetura atual.

Testes legados devem ser removidos quando o código correspondente for eliminado. Não adaptar testes mortos apenas para obter números verdes.

Cada domínio deve possuir testes unitários e integração; fluxos de download/arquivo devem ter validação real quando aplicável.

## 16. Próxima sequência de implementação

1. Catalog Manager;
2. No-Intro provider/parser;
3. fixture Mega Drive/Genesis;
4. modelo Game/ROM/Parent-Clone;
5. hash matching;
6. ZIP Builder;
7. validador DAT;
8. Redump provider/parser;
9. Disc model;
10. CHD Builder;
11. Amiga/Retroplay catalog;
12. RetroArch BIOS;
13. integração gradual do ArchiveService na reconstrução MAME;
14. somente depois expandir aquisição/Torrent e integrações restantes.

## 17. Regra de conclusão

Uma fase só é considerada concluída quando a funcionalidade estiver implementada e validada. Modelo, placeholder, tela vazia ou documentação não equivalem a funcionalidade concluída.
