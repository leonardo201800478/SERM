# Arquivos compactados e integridade — SERM

**Referência:** 29/08/2026

## Papel

O `ArchiveService` é a infraestrutura única para operações com arquivos compactados. Ele deve ser reutilizado por reconstrução MAME, reconstrução No-Intro, downloads RetroArch, shaders e demais funcionalidades que manipulem ZIP/7Z/RAR.

```text
ArchiveService
├── inspeção
├── listagem
├── teste
├── extração
├── criação
└── edição controlada
```

## Backends

### ZIP

Usar `zipfile` da biblioteca padrão do Python como backend principal.

### 7Z

Preferência:

```text
7z.exe detectado no Windows
        ↓
       usar

7z.exe ausente
        ↓
      py7zr
```

A detecção procura o executável no PATH e em locais usuais de instalação do Windows. O SERM não altera o PATH do usuário nem exige instalação externa para funcionar.

### RAR

RAR é suportado como capacidade futura/condicional. O SERM não deve tornar WinRAR obrigatório. Quando um backend externo for necessário, sua disponibilidade deve ser detectada explicitamente.

## Criação de ZIP

Criação é uma operação crítica da reconstrução.

```text
arquivos
 ↓
ZIP temporário no destino
 ↓
teste de integridade
 ↓
os.replace()
 ↓
ZIP final
```

O temporário deve possuir extensão reconhecível pelo serviço ou ser testado explicitamente pelo formato conhecido.

Nunca publicar ZIP parcial.

## Edição

O serviço deverá suportar, quando necessário:

- adicionar;
- substituir;
- remover;
- renomear;
- criar a partir de conjunto de arquivos.

A implementação deve evitar descompactar/recompactar um conjunto inteiro quando uma estratégia segura e eficiente puder executar a operação necessária diretamente.

## Segurança

Extrações devem rejeitar caminhos que escapem do destino, incluindo traversal relativo e caminhos absolutos.

Arquivos temporários devem ser limpos em sucesso e falha.

Conteúdo baixado não deve ser executado durante validação de arquivo.

## Identidade de ROM

Nome de arquivo não define identidade quando hashes estiverem disponíveis. Reconstrução deve utilizar a evidência do catálogo/Scan.

## Relação com CHD

CHD não é um archive genérico. Operações de CHD pertencem ao `CHDService`, usando ferramentas e validações próprias do formato/MAME.

Para discos de consoles, o `CHDService` deverá permitir construção de CHD a partir de imagens compatíveis com a fonte Redump.

## Testes obrigatórios

- ZIP create/list/extract/test;
- ZIP atomic publication;
- path traversal;
- arquivos grandes;
- 7Z com 7z.exe;
- 7Z sem 7z.exe usando py7zr;
- RAR quando backend estiver implementado;
- falha de extração sem resíduos;
- falha de criação sem arquivo final parcial.
