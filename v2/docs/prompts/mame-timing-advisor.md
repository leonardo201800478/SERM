# SERM V2 — Prompt de Continuidade: MAME, Timing e Display

Use este prompt como contexto de continuidade em sessões futuras de desenvolvimento.

---

Você está desenvolvendo o SERM V2 no repositório `leonardo201800478/SERM`.

A V2 em `v2/` é a linha ativa. A V1 é somente referência histórica e não pode ser importada, executada ou usada como dependência de runtime.

## Objetivo

Construir uma Data Foundation e um Timing Advisor para gerar perfis MAME por jogo, maximizando fidelidade de emulação e apresentação.

## Regras consolidadas

1. MAME ListXML obtido pelo próprio executável é a fonte primária e deve ser sempre preferido quando fornecer a informação.
2. `folders/resolution.ini` e `folders/Vsync.ini` são fallbacks quando o ListXML não possuir o dado.
3. Dados de resolução, refresh, aspect ratio, orientação e tela devem ser persistidos por máquina mesmo quando não alterarem a emulação, pois alimentam artwork e geometria.
4. O monitor deve operar em sua resolução nativa e, em regra, em tela cheia.
5. Preservar o aspecto original da máquina.
6. Priorizar pixel-perfect e escala inteira; usar bordas/artwork quando necessário.
7. Usar escala não inteira somente quando necessária para maximizar a área sem violar proporções.
8. Detectar hardware e capacidades de display, incluindo refresh físico e VRR quando possível.
9. Usar VRR quando disponível e apropriado; sem VRR, preservar o timing/frame pacing controlado pelo MAME.
10. Não criar perfis por jogo no driver NVIDIA/AMD.
11. Perfis específicos por jogo são perfis SERM/MAME.
12. O refresh nativo da máquina deve ser preservado; o MAME é a autoridade de timing da emulação.
13. O Timing Advisor escolhe configurações adaptativamente.
14. Objetivo de latência: menor input lag sem degradar frame pacing.
15. Imagem, áudio e controles devem permanecer temporalmente coerentes.
16. Usar samples quando disponíveis e apropriados.
17. Configurar latência de áudio conforme hardware/backend, evitando números universais arbitrários.
18. Quando não houver benefício comprovado, manter defaults do MAME.
19. Alterações devem ser explicáveis e reproduzíveis.

## Atuadores que podem ser considerados

`waitvsync`, `syncrefresh`, `refreshspeed`, `lowlatency`, `triplebuffer`, `audio_latency`, `samples`, `switchres`, `resolution`, `keepaspect` e parâmetros de aspecto.

Eles são decisões do Advisor, não regras universais.

## Antes de programar

1. Leia o código atual da V2 no GitHub.
2. Verifique os contratos existentes e não duplique serviços.
3. Confirme a versão atual do MAME e sua documentação quando a decisão depender de comportamento atual.
4. Preserve a separação entre fatos da máquina, fatos do hardware, decisão do Advisor e configuração derivada.
5. Escreva testes antes de introduzir comportamento não trivial.
6. Não copie código da V1; reimplemente contra os contratos V2.

## Primeiro domínio implementado

O scraper MAME deve chamar:

```text
mame.exe -listxml
```

O XML retornado é a fonte factual inicial para alimentar a Data Foundation.

Depois do scraper, implemente incrementalmente parser, proveniência, persistência e Timing Advisor.

## Critério de parada

Não declare a implementação pronta sem testes reais com o executável MAME do ambiente do usuário para validar a saída, a versão do MAME e a quantidade de máquinas extraídas.
