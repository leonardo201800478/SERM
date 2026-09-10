# Download Manager

O Download Manager é responsável por aquisição de recursos externos e por separar download de ingestão.

## Pipeline

```text
Provider
   ↓
Resource Catalog
   ↓
Download
   ↓
Temporary file / cache
   ↓
Integrity check
   ↓
Safe extraction
   ↓
Source repository
   ↓
Scan / ingestion
   ↓
Explicit destination publication
```

O Download Manager não deve escrever cegamente na instalação do emulador. Quando a etapa de publicação de recursos auxiliares estiver habilitada, ela deve usar o mesmo princípio de validação de destino adotado pela reconstrução.

## Provider

Providers encapsulam sites e formatos externos. O primeiro provider do Arcade Studio é `ProgettoSnapsProvider`.

O provider deve:

- descobrir recursos;
- identificar versão;
- informar tipo funcional;
- fornecer origem de aquisição;
- informar metadados de pacote;
- mapear somente membros úteis do pacote;
- evitar que URLs e convenções do site vazem para o domínio.

## Recursos atuais mapeados

O provider possui referência explícita para:

- CatVer 0.289;
- BestGames 0.280;
- Series 0.289;
- Languages 0.289;
- GameInit 0.289;
- Command 0.273;
- MAME Samples FullPack 0.289.

A versão de cada recurso é independente da versão do MAME. O provider não deve fabricar uma versão nova somente porque o MAME foi atualizado.

## Princípios

- downloads devem ocorrer em arquivo temporário;
- validar tamanho/hash quando a fonte fornecer referência;
- não considerar download concluído antes da validação mínima;
- permitir retry e falha explícita;
- registrar origem e versão quando possível;
- não executar conteúdo baixado durante a validação;
- impedir path traversal na extração;
- reutilizar cache quando a identidade do recurso já for conhecida;
- comparar hash para detectar conteúdo idêntico entre versões;
- manter aquisição fora do destino até que a publicação seja explicitamente autorizada.

## Separação

Download Manager transporta recursos. Providers interpretam a fonte remota. O `ExternalResourceCatalog` mantém identidade e proveniência. Services de catálogo decidem como persistir e normalizar. O materializer decide quando um artefato pode ser publicado no destino.

## Publicação de arquivos auxiliares

Os pacotes de support files podem conter membros destinados a pastas diferentes. O provider informa essa relação, por exemplo:

```text
folders/*.ini → <MAME>/folders/
dats/*.dat    → <MAME>/dats/
samples/*.zip  → <MAME>/samples/
```

O `DownloadManager.install_members()` faz primeiro o **preflight de todos os conflitos** e somente depois executa as cópias. Isso impede publicação parcial de um pacote quando um membro posterior está em conflito.

Estados de destino:

- `CREATE`: não existe arquivo no destino;
- `REUSE`: o arquivo existente é byte a byte idêntico;
- `REPLACE`: o arquivo existente é diferente e a substituição foi autorizada explicitamente;
- `BLOCK`: o arquivo existente é diferente e a publicação é interrompida.

Não há exclusão automática de arquivos desconhecidos e não há sobrescrita silenciosa.

## MAME / Progetto-SNAPS

Metadados como CatVer, Series e Languages podem enriquecer o catálogo do SERM, mas não substituem o MAME ListXML como autoridade para identidade e relações das máquinas. `GameInit` e `Command` são informações auxiliares; `BestGames` é curadoria pessoal; Samples são recursos físicos separados e devem entrar no source repository MAME, sendo validados antes da reconstrução.
