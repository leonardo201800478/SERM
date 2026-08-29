# Arquitetura do SERM

**Produto:** Strife Emulator and Roms Manager (SERM)
**Repositório histórico:** `mame-set-builder`
**Referência:** 29/08/2026

## 1. Princípio arquitetural

O SERM é dividido em domínios de preservação, reconstrução, execução, apresentação, hardware, downloads e integrações.

```text
GUI / Qt
   ↓
Application Services
   ↓
Domain
├── Library / Dataset / Scan
├── Reconstruction
│   ├── MAME
│   ├── Consoles / No-Intro
│   ├── Discs / Redump
│   └── Amiga / WHDLoad / Retroplay
├── RetroArch BIOS
├── Emulator / Backend / Core
├── Archive / Package
├── Controls / Hardware / FFB
├── Presentation / Shader / Overlay
└── Catalog Manager
```

A GUI coordena. Regras de negócio e I/O pesado permanecem em services/workers.

## 2. Fonte de verdade

O código atual do GitHub é a fonte de verdade. Documentação deve acompanhar o comportamento realmente implementado.

## 3. Núcleo MAME

```text
MAME listxml
 ↓
Dataset / SQLite
 ↓
Filtros
 ↓
Scan físico
 ↓
current_scan.jsonl
 ↓
Dependency Resolver
 ↓
Reconstrução MAME
 ↓
Set / residual
```

FULLSET e origens são somente leitura. O Scan fornece evidência física para a reconstrução. Nenhuma camada de execução deve alterar a identidade física do conteúdo.

## 4. Reconstrução ampla

A reconstrução é um domínio único com adaptadores por fonte:

```text
                 Reconstruction Engine
                          │
          ┌───────────────┼────────────────┐
          │               │                │
        MAME          Console Sources   RetroArch BIOS
          │               │                │
   LISTXML rules    No-Intro/Redump/     .info rules
                   Retroplay rules
```

O motor comum pode oferecer hash matching, planejamento, staging, publicação atômica e validação. Cada fonte mantém sua própria semântica.

### MAME

MAME permanece conforme as regras já definidas para ROMs, parent/clone, BIOS, devices, samples, disks e CHDs.

### Consoles — No-Intro

No-Intro é a fonte principal para conjuntos de cartuchos/mídias digitais suportados. O parser deve preservar, quando presentes:

- game name;
- cloneof/parent;
- ROM name;
- size;
- CRC32;
- MD5;
- SHA1;
- demais metadados relevantes do DAT.

A identidade física da ROM é determinada por hashes/tamanho, não pelo nome isolado.

### Discos — Redump

Redump é tratado como fonte orientada a discos, não como uma simples extensão do modelo No-Intro. O domínio deverá preservar metadados de sistema, título, edição, versão, serial e hashes conforme a fonte disponibilizada.

Quando a mídia for compatível com conversão, **CHD é o formato de saída preferencial**. ISO/BIN-CUE permanecem formatos intermediários/alternativos quando necessários.

### Amiga — WHDLoad / Retroplay

Amiga possui catálogo e regras próprios. A fonte de catálogo planejada é o ecossistema Retroplay/WHDLoad, com distribuição/índice compatível com a página de downloads do GamesNostalgia. O modelo deverá contemplar pacote, versão, variante e arquivo, sem fingir que um pacote WHDLoad é um DAT No-Intro.

## 5. Catalog Manager

O Catalog Manager mantém referências locais de fontes externas sem baixar conteúdo de jogos automaticamente.

```text
Catalog Manager
├── No-Intro
├── Redump
├── Amiga / Retroplay
└── MAME
```

Cada provider possui descoberta, download, validação, parsing e versionamento próprios. O cache de catálogo é separado do cache de ROMs: **não existe cache permanente de ROMs apenas por causa do catálogo**.

O catálogo deve registrar origem, conjunto, versão/data, sincronização e integridade quando disponível.

## 6. ArchiveService

O SERM possui uma infraestrutura comum para arquivos compactados:

```text
ArchiveService
├── ZIP → Python zipfile
├── 7Z  → 7z.exe preferencial / py7zr fallback
└── RAR → backend externo quando necessário
```

Responsabilidades:

- detectar formato;
- listar;
- testar integridade;
- extrair;
- criar;
- editar quando necessário;
- trabalhar com temporários seguros;
- impedir path traversal;
- publicar atomicamente.

ZIP é especialmente crítico para a reconstrução MAME e No-Intro.

CHD possui serviço próprio e não deve ser tratado como um archive genérico.

## 7. Hash matching

A identidade física deve priorizar:

```text
SHA1
 ↓
MD5
 ↓
CRC32 + tamanho
```

A ordem exata depende da fonte e da evidência disponível. Nome é metadado de reconstrução, não identidade primária.

## 8. Emulator / Backend / Core

```text
Emulator
Backend
Core
```

MAME, Flycast, FBNeo e Supermodel podem possuir backends standalone. RetroArch é runtime e executa cores Libretro.

Não duplicar a entidade de conteúdo apenas porque existem diferentes backends.

## 9. RetroArch

RetroArch possui:

- runtime;
- cores;
- system;
- assets;
- saves;
- states;
- shaders;
- configuração própria.

O runtime e os cores possuem versões independentes.

A Home de RetroArch está concluída e validada em fluxo real, incluindo instalação/atualização do runtime, atualização de cores por CRC, retry por core e uso do 7-Zip externo quando disponível.

## 10. BIOS RetroArch

BIOS de RetroArch é um domínio separado de No-Intro/Redump. O catálogo é derivado dos `.info`/metadados do ecossistema RetroArch quando aplicável.

Objetivo:

```text
catalogar
 ↓
scan/hash
 ↓
classificar
 ├── OK
 ├── renomeável/movível
 ├── reconstruível
 └── missing
 ↓
reconstruir/instalar somente o necessário
```

A operação deve ser rápida e limpa, sem reprocessamento global desnecessário.

## 11. Presentation

```text
Sistema
├── Core
├── Override
├── Shader
└── Overlay
```

Shaders de terceiros são baixados de seus próprios repositórios e não incorporados ao repositório do SERM. A seleção prioriza CRT limpo, fiel e leve. Presets agressivos, com reflexos/overlays pesados ou grande custo de processamento não são padrões.

A proporção do shader representa o sistema/emulação. O SERM não deve forçar 16:9 apenas porque o monitor do usuário é 16:9.

RetroArch deve preferir seu sistema nativo de shaders. Standalone pode utilizar mecanismos específicos, como ReShade, quando tecnicamente apropriado.

## 12. Configuração de emuladores

Arquivos nativos válidos devem ser preservados. O serviço deve alterar somente propriedades conhecidas e suportadas, com backup antes de substituir configuração inválida.

## 13. Downloads

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

Downloads não devem gravar diretamente em destinos finais antes de validação.

## 14. Controles / Hardware / FFB

Esses domínios permanecem separados da reconstrução e do catálogo. Perfis de hardware e controle podem ser convertidos para diferentes backends sem duplicar a entidade de ROM.

## 15. GUI e lazy loading

As abas devem ser carregadas sob demanda. Dados pesados de catálogo, scan, downloads e reconstrução não devem ser materializados no startup sem necessidade.

A Home RetroArch está concluída; novas funcionalidades devem evitar reintroduzir carregamento antecipado ou botões sem implementação real.

## 16. Testes

A suíte deve cobrir somente a arquitetura atual. Testes de implementações legadas devem ser removidos, não adaptados artificialmente para manter código morto.

Cada fase relevante requer:

- testes unitários;
- integração;
- fixtures reais quando possível;
- validação de filesystem;
- fluxo real quando houver download/runtime.

## 17. Segurança e integridade

- origens somente leitura;
- staging temporário;
- publicação atômica;
- hashes antes da publicação;
- proteção contra path traversal;
- nenhum arquivo parcial publicado;
- nenhum cache permanente de ROMs;
- não executar conteúdo baixado como parte da validação;
- preservar configurações válidas;
- registrar falhas de forma acionável.
