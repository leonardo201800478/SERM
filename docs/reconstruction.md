# Reconstrução de ROMs

## Regra de integridade

A unidade de validade é **cada arquivo ROM**, nunca o CRC/hash do ZIP completo.

Uma machine pode estar funcional mesmo que seu ZIP de origem contenha arquivos
extras, obsoletos ou inúteis. A reconstrução remove esses extras.

### Operações da reconstrução

1. **Localizar** a origem registrada pelo Scan.
2. **Transferir** a ROM individual em streaming de 1 MiB.
3. **Renomear** para o nome esperado pelo LISTXML.
4. **Validar** tamanho + CRC e SHA-1 quando disponível.
5. **Adicionar** ao ZIP temporário da machine.
6. Repetir até todas as ROMs obrigatórias estarem validadas.
7. Validar as entradas do ZIP temporário.
8. Publicar atomicamente com `os.replace()`.

A origem nunca é modificada.

## Machine perfeita

Mesmo uma machine com todas as ROMs `valid` não é copiada como ZIP bruto pelo
novo motor. Ela é reconstruída pelas entradas esperadas. Isso garante a limpeza
de arquivos extras e a correção de nomes.

## ROM encontrada em outra machine

O Scan pode construir um catálogo físico filtrado por `(CRC, tamanho)`. O catálogo
registra `archive`, `member`, `machine`, `CRC` e `size`. A reconstrução reutiliza
essa origem registrada e não faz uma nova busca global.

Para ZIPs, a indexação usa somente o diretório central. `ZipInfo.CRC` e
`ZipInfo.file_size` representam, respectivamente, o CRC-32 e o tamanho
**descompactado** do membro; o conteúdo só é transferido depois. Isso é suportado
pela documentação atual do `zipfile` do Python. citeturn0search0

## Staging

O destino usa apenas:

```text
<destino>/.reconstruction_tmp/
```

Não existe cache permanente de ROMs.

Um ZIP vazio ou incompleto nunca deve ser publicado.

## Residual

`current_reconstruction.jsonl` contém somente ROMs que não puderam ser
reconstruídas. Uma ROM já validada e publicada não deve aparecer no residual.

O residual é destinado à próxima etapa de aquisição, incluindo Torrent.

## Tipos de set

- **Split**: machine reconstruída com suas ROMs próprias.
- **Non-Merged**: inclui as ROMs necessárias herdadas do parent.
- **Merged**: agrupa ROMs por raiz de clone conforme o modelo atual.

A implementação de Merged/Non-Merged ainda requer validação com fixtures reais
do LISTXML MAME antes de ser considerada final.

## Estado atual

### Implementado

- streaming de ROM individual;
- origem somente leitura;
- retry automático;
- staging temporário;
- validação por ROM;
- limpeza de extras durante reconstrução completa;
- publicação atômica;
- manifesto residual;
- reparo individual transacional;
- catálogo físico filtrado por CRC/tamanho.

### Em validação

- integração completa do catálogo com todos os cenários de parent/clone;
- Merged;
- Non-Merged;
- CHDs/devices/samples/disks;
- recuperação após interrupção.

### Ainda não concluído

- download via Torrent;
- resolução automática de fontes externas via qBittorrent;
- cobertura integral de 7Z/RAR como fontes de ROM;
- suíte de integração completa contra um fullset real.
