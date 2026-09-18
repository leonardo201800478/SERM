# ArchiveService

O ArchiveService encapsula operações sobre arquivos compactados para impedir que regras de ZIP/7Z/RAR sejam espalhadas pelos services.

## Backends

```text
ZIP → Python zipfile
7Z  → 7z.exe preferencial / backend Python quando suportado
RAR → backend externo quando necessário
```

## Responsabilidades

- identificar formato;
- listar conteúdo;
- testar integridade quando suportado;
- extrair para staging seguro;
- criar/atualizar arquivos quando o workflow exigir;
- controlar temporários;
- publicar atomicamente.

## Segurança

Entradas de archive são não confiáveis. Extração deve validar caminhos e impedir path traversal. Links e objetos especiais devem ser tratados conservadoramente.

## Relação com reconstrução

ArchiveService não decide qual ROM pertence a uma machine. Ele executa operações de arquivo solicitadas pelo serviço de reconstrução.

CHD possui tratamento específico e não deve ser confundido com um archive genérico.
