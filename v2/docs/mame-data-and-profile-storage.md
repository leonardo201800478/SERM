# MAME — Dados, perfis e integridade

## Objetivo

A V2 deve tratar a instalação do MAME como recurso externo e preservá-la. O SERM mantém seus dados, caches e perfis fora da raiz do MAME, salvo quando o próprio usuário solicitar explicitamente uma alteração de configuração nativa.

## Fontes de dados

A ordem de precedência para dados da máquina é:

1. `-listxml` executado pelo executável MAME selecionado pelo usuário;
2. `folders/resolution.ini` e `folders/Vsync.ini` como fallback quando o ListXML não fornecer o dado;
3. fallback explícito e documentado do SERM/MAME quando nenhuma fonte fornecer o valor.

O ListXML é a fonte primária porque é produzido pela mesma versão do executável que será utilizada na emulação. A origem de cada dado deve ser registrada no modelo/banco quando isso for relevante para auditoria e diagnóstico.

## Resolução e timing

Para cada máquina, preservar separadamente:

- resolução nativa;
- pixel aspect ratio;
- physical/display aspect ratio quando disponível;
- orientação;
- refresh nativo com precisão de ponto flutuante;
- fonte do dado.

Não arredondar refresh não convencional para 50/55/60/75 Hz.

`resolution.ini` e `Vsync.ini` não substituem dados do ListXML quando estes estiverem disponíveis.

## Perfis SERM

O SERM pode gerar um perfil por sistema/máquina, mas esse perfil pertence ao SERM, não ao driver NVIDIA/AMD. Não criar perfis de driver por jogo.

Estrutura recomendada:

```text
SERM/data/mame/
├── profiles/
│   ├── systems/
│   └── games/
├── generated/
├── cache/
└── metadata/
```

Um perfil físico só deve ser criado quando houver uma decisão/override que precise ser persistida. O comportamento padrão não deve gerar milhares de arquivos redundantes.

## Arquivos nativos do MAME

Não reformatar arquivos existentes apenas para alterar uma opção. Preservar, quando tecnicamente possível:

- comentários;
- chaves desconhecidas pelo SERM;
- ordem das opções;
- espaçamento;
- finais de linha;
- encoding compatível;
- valores que não estejam sob gerenciamento do SERM.

Alterações futuras em arquivos nativos devem utilizar leitura estruturada, validação, backup e escrita atômica. Nunca truncar o arquivo original antes de validar a nova representação.

## Hierarquia de configuração

O SERM não deve inventar uma hierarquia própria que conflite com a do MAME. Antes de gerar arquivos nativos, mapear a precedência real entre configuração global, sistema/jogo, defaults e linha de comando. O perfil SERM representa intenção; a materialização final deve respeitar a semântica do MAME.

## Geometria e artwork

A resolução nativa e os aspectos da máquina são armazenados mesmo quando não alteram a emulação. Eles são necessários para a camada Shaders/Artworks/afins e para calcular uma saída fullscreen na resolução nativa do monitor, preservando a proporção da tela original.

Prioridade de apresentação:

1. fullscreen na resolução nativa do monitor;
2. aspecto original;
3. pixel-perfect/integer scaling quando possível;
4. bordas ou artwork quando necessário;
5. nunca distorcer a geometria apenas para preencher a tela.

## Hardware Profile

O SERM deve detectar e persistir um perfil do PC/display contendo, quando disponível:

- CPU/GPU;
- resolução ativa;
- refresh máximo e modos relevantes;
- VRR mínimo/máximo;
- G-Sync/FreeSync/VRR;
- recursos de áudio relevantes.

## Timing Advisor

O Timing Advisor recebe o perfil da máquina, o perfil de hardware e as políticas do usuário e calcula a estratégia de apresentação. A meta é minimizar input lag sem degradar frame pacing, preservar o clock/timing original e evitar tearing.

VRR deve ser preferido quando a taxa nativa da máquina estiver dentro da faixa suportada pelo display. Quando não houver compatibilidade, preservar o comportamento padrão do MAME antes de introduzir alterações artificiais.

`syncrefresh` não é default universal. `waitvsync`, `lowlatency`, `refreshspeed` e `triplebuffer` devem ser decisões do Advisor, considerando as recomendações do MAME e o hardware detectado.

## Perfis de usuário

O algoritmo deve permitir políticas como:

- Fidelity;
- Balanced;
- Low Latency;
- Compatibility.

Esses modos são políticas do Advisor, não conjuntos independentes de configurações de driver.
