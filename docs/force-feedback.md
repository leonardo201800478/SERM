# Force Feedback

Force Feedback é uma capacidade de hardware dependente do dispositivo, driver e emulador/runtime.

## Arquitetura

```text
Input device
   ↓
OS / driver
   ↓
Emulator / runtime
   ↓
Game
```

O SERM pode administrar profiles e parâmetros quando o backend oferecer uma interface estável. Não deve presumir que todo dispositivo suporta os mesmos efeitos.

## Regras

- detectar capacidades antes de configurar;
- separar profile de hardware de identidade do jogo;
- preservar configurações externas desconhecidas;
- registrar falhas sem impedir o restante da configuração do emulador.
