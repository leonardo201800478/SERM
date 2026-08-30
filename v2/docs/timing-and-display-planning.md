# SERM V2 — Planejamento de Timing, Display e Artwork

## Status

Planejamento consolidado a partir das decisões funcionais do projeto. Esta documentação é normativa para a implementação V2.

## 1. Hierarquia de fontes

Para resolução e refresh da máquina:

```text
MAME ListXML
    ↓
folders/resolution.ini ou folders/Vsync.ini, somente quando o ListXML não fornecer o dado
    ↓
default do MAME
```

O ListXML é sempre a fonte preferencial quando possuir a informação.

## 2. Dados persistidos por máquina

Mesmo dados sem efeito direto na emulação devem ser armazenados quando tiverem valor para apresentação:

- resolução nativa;
- refresh nativo;
- pixel aspect ratio;
- physical/display aspect ratio quando disponível;
- orientação;
- características da tela;
- disponibilidade de artwork;
- origem/proveniência de cada dado.

Esses dados sustentam a geometria de saída e os ajustes de artwork.

## 3. Display

Regra geral:

- tela cheia;
- resolução nativa física do monitor;
- aspecto original da máquina preservado;
- pixel-perfect como objetivo;
- maior ocupação possível da área disponível;
- integer scaling quando a geometria permitir;
- bordas ou artwork quando a escala inteira não ocupar toda a tela;
- escala não inteira somente quando necessária para maximizar a área sem violar o aspecto;
- orientação da máquina deve ser considerada.

O SERM não deve criar resoluções artificiais do monitor para simular a resolução interna da máquina.

## 4. Artwork

Artwork é parte do modelo de apresentação, não mero recurso cosmético. O perfil por máquina deve permitir associar geometria e artwork específicos.

A área da tela emulada deve manter suas proporções reais dentro da composição final.

## 5. VRR e sincronização

O hardware do usuário deve ser detectado. O perfil de hardware registra resolução, refresh físico e capacidades de VRR/G-Sync/FreeSync quando detectáveis.

Quando VRR estiver disponível, o SERM deve preferir adaptação ao refresh físico dentro da faixa suportada. Quando VRR não estiver disponível, o MAME deve permanecer responsável pelo timing de apresentação, com frame pacing preservado.

Não serão criados perfis por jogo no driver NVIDIA/AMD. Perfis específicos são gerados no SERM/MAME.

## 6. Timing Advisor

O Timing Advisor é responsável por transformar fatos da máquina + fatos do hardware + política de usuário em uma decisão de execução.

Entrada:

```text
Machine Profile
Hardware Profile
MAME defaults/capabilities
User timing policy
```

Saída:

```text
Timing Profile
Display Geometry Profile
MAME execution configuration
Decision/provenance
```

Objetivo principal:

> menor input lag possível sem degradar frame pacing, mantendo a maior fidelidade possível de sincronização entre imagem, som e controles.

## 7. Opções MAME

O SERM deve deixar o MAME decidir por default quando não existir evidência de que uma alteração melhora o resultado.

As opções abaixo são atuadores do Advisor, não regras universais:

- `waitvsync`;
- `syncrefresh`;
- `refreshspeed`;
- `lowlatency`;
- `triplebuffer`;
- `audio_latency`;
- `samples`;
- `switchres`;
- `resolution`;
- `keepaspect` e parâmetros de aspecto.

Para sistemas fora das recomendações normais do MAME, o Advisor poderá gerar perfis específicos por jogo.

## 8. Áudio

Samples devem ser utilizados quando disponíveis e apropriados. Latência de áudio deve ser determinada em conformidade com o hardware e backend disponível, evitando valores universais arbitrários.

## 9. Perfis

Existe um perfil SERM/MAME gerado por jogo quando necessário. Não existe a exigência de perfil de driver GPU por jogo.

Os perfis devem ser reproduzíveis e explicáveis: cada decisão importante deve registrar o fato que a motivou.

## 10. Modos de política

A arquitetura deve comportar políticas adaptativas, sem duplicar o motor de decisão:

- Fidelity;
- Balanced;
- Low Latency;
- Compatibility.

A política muda a prioridade do Advisor; não muda a fonte factual dos dados da máquina.

## 11. Regra de conservadorismo

Se o SERM não tiver evidência suficiente para melhorar uma configuração, deve preservar o comportamento padrão do MAME.

Isso vale especialmente para sistemas em que determinada opção não produz benefício real ou em que o MAME já possui uma estratégia interna adequada.

## 12. Testes obrigatórios antes de considerar a implementação estável

Cada alteração relevante deve ser validada em pelo menos:

1. sistema horizontal 4:3;
2. sistema vertical;
3. sistema com refresh não igual ao monitor;
4. sistema dentro da faixa VRR;
5. sistema fora da faixa VRR;
6. máquina com artwork;
7. máquina sem artwork;
8. escala inteira possível;
9. escala inteira impossível;
10. áudio com samples;
11. caso sem samples;
12. execução com perfil gerado e com default MAME.

As medições devem priorizar geometria, estabilidade do frame pacing, sincronização A/V, latência percebida e ausência de regressões.
