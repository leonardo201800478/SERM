# Roadmap da V2

Este documento define o estado macro do desenvolvimento. Datas de auditorias antigas não são usadas como status.

## Concluído / operacional

### Fundação

- estrutura independente da V2;
- empacotamento e entry points;
- configuração/runtime paths;
- SQLite + SQLAlchemy;
- infraestrutura de migrations;
- testes e tooling de qualidade.

### Home e emuladores

- Home consolidada;
- descoberta/configuração de emuladores;
- persistência de executáveis e versões instaladas;
- instalação/atualização onde suportado;
- restauração segura de janela/monitor;
- catálogo de cores RetroArch e filtragem de canais.

### Catálogos

- foundations de MAME/ListXML;
- normalização e classificação MAME;
- filtros MAME;
- dados de resolução/display/VSync;
- foundations de No-Intro;
- foundations WHDLoad/Amiberry;
- foundations C64/TOSEC;
- integração/provider LaunchBox.

### Scan

- engine genérico de scan;
- scan MAME e No-Intro em evolução;
- persistência de resultados;
- checkpoints e resiliência;
- cache/indexação auxiliar;
- pipeline de filtros de scan.

### Reconstrução

- serviços de reconstrução e arquivo;
- resolução de dependências em evolução;
- infraestrutura para CHD e publicação.

## Em desenvolvimento

1. consolidar o scanner genérico para diferentes modelos de catálogo;
2. completar a integração MAME do scan e a classificação de resultados;
3. refinar matching por hash/tamanho/identidade;
4. ampliar DE-PARA e proveniência entre fontes;
5. completar planejamento e execução de reconstruções;
6. consolidar ArchiveService e CHD service com publicação atômica;
7. ampliar integração de execução/perfis;
8. ampliar adapters de sistemas adicionais.

## Critérios de conclusão de uma capacidade

Uma capacidade só deve ser marcada como concluída quando:

- existe implementação V2;
- existe cobertura de teste apropriada;
- caminhos de erro relevantes são tratados;
- persistência/estado é consistente;
- a GUI não contém regras que deveriam estar nos services;
- a documentação descreve o comportamento real;
- a funcionalidade foi validada no ambiente-alvo quando depender de ferramenta externa.

## Prioridade técnica

```text
Dados e identidade
       ↓
Scan confiável
       ↓
Matching / dependências
       ↓
Reconstrução segura
       ↓
Execução
       ↓
Apresentação e otimizações
```

A prioridade é preservar correção e rastreabilidade antes de otimizar throughput ou adicionar integrações periféricas.
