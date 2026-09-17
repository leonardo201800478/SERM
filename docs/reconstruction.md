# Reconstrução

## Objetivo

Reconstrução converte conteúdo disponível no filesystem em uma organização compatível com um catálogo e um destino de execução, usando evidências do scan e regras do sistema.

Reconstrução não é scan: **scan observa; reconstrução transforma.**

## Pipeline V2

```text
Catálogo
   ↓
Plano de origem lógica
   ↓
Resolução de evidência física
   ↓
Manifesto de materialização
   ↓
Staging
   ↓
Materialização
   ↓
Validação do destino
   ↓
Publicação atômica
```

A separação entre essas etapas é deliberada. O catálogo não prova existência física; o planner não copia arquivos; o manifesto não deve executar operações de filesystem.

## O que já está implementado

A V2 possui:

- `ArcadeRomReconstructionPlanner` para origem lógica;
- `ArcadeRomReconstructionEngine` para matching físico;
- `ArcadeSetLayoutPlanner` para SPLIT/NON_MERGED/FULL_MERGED;
- `ArcadeReconstructionManifestBuilder` para consolidar operações;
- `ArcadeChdReconstructionEngine` para CHD;
- `Materializer` como camada de materialização física.

A lógica de ROM foi validada contra catálogo MAME real com 179.667 relações `merge`, sem divergências entre evidência esperada e decisão do planner.

## Matching físico

A identidade física segue a ordem:

```text
SHA1
  ↓
MD5
  ↓
CRC + size
```

Uma identidade física ambígua não deve ser resolvida arbitrariamente.

O nome de arquivo é evidência auxiliar. Quando o catálogo fornece hashes, eles têm precedência sobre heurísticas de nome.

## Staging e publicação

A materialização deve sempre ocorrer em destino temporário e somente depois ser promovida para o destino final.

```text
origem somente leitura
        ↓
     staging
        ↓
    validação
        ↓
 publicação atômica
```

O destino final não deve apresentar arquivos parciais de uma reconstrução incompleta.

## Segurança

- origem física somente leitura;
- path traversal deve ser rejeitado;
- conflitos de destino devem bloquear publicação;
- identidades ambíguas devem bloquear publicação;
- dependências não resolvidas devem bloquear publicação;
- a validação nunca executa conteúdo encontrado no filesystem;
- operações destrutivas somente podem atingir destinos explicitamente controlados.

## MAME

MAME não deve ser tratado como uma lista plana de arquivos. O pipeline precisa preservar parent/clone, `romof`, `merge`, BIOS, devices, samples e CHDs.

Para ROMs:

```text
machine_name → machine set
 display_name → ROM declarada
 merge        → ROM de origem
 SHA1/CRC/... → identidade física
```

Para CHDs, o pipeline permanece separado da cadeia de ZIPs de ROM.

## Layouts

### SPLIT

O archive de cada machine contém seus componentes próprios. Uma dependência fornecida por parent/related set não deve ser duplicada no clone.

### NON_MERGED

Cada machine recebe os componentes necessários para ser autocontida conforme o grafo selecionado.

### FULL_MERGED

A família utiliza o archive da raiz. Componentes compartilhados são deduplicados por origem física.

O comportamento detalhado e as invariantes estão em `arcade-mame-rom-architecture.md` e no ADR-0003.

## Estado documental versus estado físico

`good`, `baddump` e `nodump` são propriedades do conhecimento MAME sobre o dump. `valid`, `missing`, `invalid` e `error` descrevem a evidência física obtida pelo scan.

Essas dimensões não podem ser colapsadas em um único booleano.

## Próximas pendências

A próxima etapa não é criar mais heurísticas de matching. É fechar o ciclo físico e comprovar o resultado no filesystem:

1. validar o `Materializer` com fixtures reais de ZIP;
2. provar os três layouts em famílias parent/clone reais;
3. validar BIOS/device/sample dependencies;
4. validar CHD normal e delta em famílias reais;
5. executar uma reconstrução end-to-end e reescanear o destino;
6. somente depois integrar o fluxo completo à GUI.

## Estado da capacidade

**Planejamento lógico: validado.**

**Manifesto: validado.**

**Materialização física end-to-end: ainda em validação.**

**Integração completa com GUI: pendente.**
