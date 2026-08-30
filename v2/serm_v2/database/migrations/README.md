# V2 Migrations

Migrations in this directory belong exclusively to the V2 schema.

## Regras

- não importar o schema da V1;
- foreign keys habilitadas;
- índices explícitos;
- toda coluna precisa ter consumidor definido;
- migrations versionadas e idempotentes;
- mudanças destrutivas são permitidas durante o desenvolvimento da V2 quando melhorarem o modelo.

## Migration atual

`001_configuration_schema.sql` cria a base relacional para a futura aba **Configurações** e para o catálogo de hardware/configuração:

- emuladores;
- grupos de configuração;
- opções nativas;
- valores discretos;
- dependências entre opções;
- vínculos com capacidades do hardware;
- escopos e precedência;
- arquivos de configuração;
- perfis SERM;
- observações da versão real do executável;
- capacidades detectadas do PC.

A migration é aplicada automaticamente pelo bootstrap da V2.
