# Catalog Manager — SERM

**Estado:** arquitetura consolidada; implementação da nova fase pendente.  
**Referência:** 29/08/2026

## 1. Papel

O Catalog Manager fica sobre a Data Foundation e mantém referências locais de fontes externas para identificação, auditoria, organização e reconstrução.

Ele **não é um cache de ROMs** e não baixa conteúdo de jogos apenas para completar um catálogo.

```text
Source
 ↓
Provider
 ↓
Download / leitura local
 ↓
Staging
 ↓
Validation
 ↓
Parser específico
 ↓
Normalize
 ↓
CatalogVersion
 ↓
Canonical Identity / Mapping
 ↓
Scan / Reconstruction / Execution
```

## 2. Classes de fonte

### Preservação / referência

- No-Intro / Dat-o-MATIC;
- Redump;
- MAME/listxml;
- FBNeo;
- MAME Softlists;
- fontes confiáveis de BIOS.

### Conveniência

- WHDLoad/Retroplay;
- eXoDOS;
- C64 Dreams/EasyFlash e fontes semelhantes;
- packs comunitários específicos.

### Metadata / integração

- RetroArch `.rdb`;
- LaunchBox `LaunchBox.Metadata.db`;
- LaunchBox `Platforms.xml`;
- LaunchBox `MAME.xml`;
- LaunchBox `Files.xml`;
- caches externos quando sua utilidade for comprovada.

## 3. Fontes não compartilham semântica automaticamente

Cada provider mantém a semântica da fonte.

```text
NoIntroGame
RedumpDisc
MameMachine
AmigaPackage
ExoDosPackage
RetroArchEntry
LaunchBoxGame
```

Infraestrutura de armazenamento, hashing, staging, versionamento e mapping pode ser comum.

## 4. No-Intro

Fonte principal para cartuchos e mídias digitais suportadas.

O parser deve preservar, quando presentes:

- game name;
- cloneof/parent;
- ROM name;
- size;
- CRC32;
- MD5;
- SHA1;
- demais metadados do DAT.

A identidade física não deve depender somente do nome.

## 5. Redump

Fonte orientada a discos ópticos. O modelo deve preservar sistema, título, edição, versão, serial, região, idiomas e dados de faixas/hashes conforme disponibilizados pela fonte.

O provider só deve assumir endpoints/arquivos depois de validação da fonte atual.

## 6. MAME

MAME continua derivado do LISTXML e do pipeline existente. O novo Catalog Manager não deve criar uma segunda fonte de verdade para máquinas MAME.

## 7. RetroArch RDB

Os `.rdb` são providers locais de metadata/identificação. Podem auxiliar matching por hash/nome e associação com sistemas/core, mas não substituem No-Intro, Redump ou MAME quando essas fontes forem aplicáveis.

## 8. LaunchBox

O LaunchBox será tratado como provider externo de metadata e referência arquitetural, nunca como dependência obrigatória do SERM.

A análise do `LaunchBox.Metadata.db` identificou:

```text
Games
Platforms
Emulators
EmulatorPlatforms
GameAlternateTitles
GameImages
```

O `Platforms.xml` fornece dados úteis para normalização e classificação de plataformas, incluindo campos como `Category`, `Emulated` e `UseMameFiles`.

O SERM poderá importar esses dados por adapter e armazenar a proveniência LaunchBox.

## 9. DE-PARA

Fontes convenientes são relacionadas à identidade canônica por mapping explícito:

```text
Official Entry
      ↕
Identity Mapping
      ↕
Convenience Entry
```

O mapping pode registrar confiança, evidências, regras, versão da fonte e data.

## 10. Nomenclatura

O Catalog Manager não deve destruir o nome original da fonte.

O modelo deverá separar, quando aplicável:

```text
source_name
canonical_name
display_name
scraper_name
filename
normalized_name
```

Isso permite organizar WHDLoad/eXoDOS e outras fontes para scraping e execução sem perder a proveniência.

## 11. Atualização

```text
catálogo ativo
 ↓
verificar versão/data/integridade
 ↓
obter nova fonte
 ↓
staging
 ↓
validar
 ↓
parse
 ↓
importar em transação
 ↓
ativar nova versão
```

Se uma nova versão falhar, a anterior continua válida.

Registrar:

- provider;
- conjunto;
- versão/data;
- origem;
- integridade quando disponível;
- data da sincronização;
- parser/schema.

## 12. Cache

```text
Catalog Cache ≠ ROM Cache
```

DATs, índices e arquivos de metadata podem ser mantidos localmente. ROMs não devem ser baixadas somente por causa do Catalog Manager.

## 13. Relação com reconstrução

O Catalog Manager fornece referência lógica. Ele não cria ZIPs/CHDs/pacotes finais.

```text
Catalog
  ↓
Matching
  ↓
Mapping
  ↓
Reconstruction Planner
  ↓
ArchiveService / CHD Service
```

## 14. GUI futura

A GUI poderá exibir providers, conjuntos, versões, data da última sincronização, integridade e estado de atualização.

Deve existir atualização manual mesmo com atualização automática.

## 15. Próxima implementação

1. Source Registry;
2. CatalogVersion/cache;
3. adapters locais de LaunchBox e RetroArch para validar o modelo;
4. No-Intro provider/parser;
5. fixture Mega Drive/Genesis;
6. testes de sincronização/rollback;
7. Redump após validar a fonte atual;
8. MAME adapter integrado ao dataset existente;
9. FBNeo;
10. WHDLoad/Retroplay;
11. eXoDOS;
12. demais providers.
