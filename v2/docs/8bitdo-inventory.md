# Inventário consolidado 8BitDo — SERM V2

O SERM V2 passa a tratar o inventário 8BitDo como uma família de hardware
independente da configuração específica usada pelo emulador.

## Controles físicos consolidados

| Modelo | SERM ID | VID | PIDs principais | Face | Eixos | Extras | Movimento |
|---|---|---:|---|---:|---:|---:|---|
| 8BitDo M30 | `8bitdo-m30` | `2DC8` | `5006`, `0651` | 6 | 2 | 0 | Não |
| 8BitDo Ultimate 2C | `8bitdo-ultimate-2c` | `2DC8` | `310A`, `301B`, `3013` | 4 | 4 | 2 | Não |
| 8BitDo Ultimate 2 Wireless | `8bitdo-ultimate-2-wireless` | `2DC8` | `310B`, `6012`, `6013` | 4 | 4 | 2 | Sim |

Os números de face/eixos são **layout esperado**, não substituem a leitura
física. O diagnóstico deve sempre comparar o catálogo com os elementos
realmente expostos por HIDAPI/SDL3.

## M30

O M30 é tratado como um controle de seis botões frontais. O SERM não deve
reduzi-lo a um gamepad genérico de quatro faces.

Assinaturas próprias confirmadas:

- `2DC8:5006` — D-Input / USB;
- `2DC8:0651` — D-Input / Bluetooth.

Assinaturas XInput, Switch e DS4 podem ser compartilhadas com outros
controladores. Portanto, o serviço de modo mantém essas apresentações como
compatíveis/conservadoras quando não existe evidência adicional.

## Ultimate 2C

O Ultimate 2C possui layout convencional de quatro face buttons, sticks,
triggers, bumpers, D-pad e dois controles extras traseiros.

Assinaturas cadastradas:

- `2DC8:310A` — XInput / USB ou 2.4G;
- `2DC8:301B` — Bluetooth/HID;
- `2DC8:3013` — variante Bluetooth/HID.

O SERM não usa IDs XInput genéricos como identidade definitiva do modelo.

## Ultimate 2 Wireless

O Ultimate 2 Wireless foi consolidado a partir dos scans físicos realizados
no SERM sem outro controle conectado.

- `2DC8:310B` — apresentação XInput ativa, observada via USB/XInput e 2.4G;
- `2DC8:6012` — apresentação D-Input, observada em USB, 2.4G e Bluetooth;
- `2DC8:6013` — receptor 2.4G em estado inativo;
- `057E:2009` — apresentação Switch/HID compartilhada; **não** é usada como
  identidade permanente do Ultimate 2.

O último ponto é deliberado. `057E:2009` também é usado por controles Switch
Pro de terceiros. A base SERM deve preservar a evidência observada sem
transformar uma assinatura compartilhada em falsa identificação de modelo.

## Arquitetura de consolidação

A identificação ocorre em quatro níveis:

1. **Identidade física:** HIDAPI registra VID, PID, revisão, fabricante,
   produto, serial, caminho, usage e conexão.
2. **Apresentação/mode:** `ControllerModeService` interpreta a assinatura
   específica de transporte/modo.
3. **Modelo:** `ControllerCatalogService` consolida o hardware em um dos três
   modelos 8BitDo conhecidos.
4. **Layout real:** SDL3/HIDAPI mede os elementos efetivamente expostos e o
   `SystemControlMapper` compara o hardware com os requisitos do sistema
   emulado.

Assim, um mesmo Ultimate 2 pode reaparecer com PIDs diferentes sem virar três
controles físicos diferentes no catálogo.

## Regra para novos controles 8BitDo

Quando um novo 8BitDo for conectado:

1. registrar o inventário físico;
2. registrar todos os PIDs observados em cada transporte;
3. comparar o nome/produto com o catálogo;
4. medir botões, face buttons, eixos, hats e recursos especiais;
5. somente então adicionar uma entrada definitiva ao catálogo;
6. manter assinaturas compartilhadas como genéricas quando não houver prova
   suficiente.

A expansão do catálogo não deve alterar o backend SDL3/HIDAPI nem criar um
mapeamento específico para um emulador. O mesmo modelo físico deve poder ser
reutilizado por MAME, RetroArch e pelos demais backends do SERM.
