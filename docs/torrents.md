# Torrents

A integração com torrents deve ser tratada como mecanismo de aquisição, não como fonte canônica de identidade.

## Arquitetura

```text
Torrent metadata
      ↓
Acquisition backend
      ↓
Downloaded resource
      ↓
Validation
      ↓
Source adapter / scan
```

## Regras

- preservar a origem do recurso;
- não confiar no nome do arquivo como identidade;
- validar conteúdo quando houver DAT/hash de referência;
- manter downloads fora do banco canônico até serem reconhecidos;
- separar aquisição de reconstrução.

O suporte efetivo a um backend torrent específico deve ser documentado junto ao código que o implementa.
