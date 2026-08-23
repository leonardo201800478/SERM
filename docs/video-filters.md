# ARCADE MANAGER — Filtros CRT / Scanlines

## Objetivo

O ARCADE MANAGER poderá fornecer uma camada de apresentação CRT para emuladores que não possuam internamente um sistema de shaders suficientemente adequado.

O objetivo não é alterar a emulação. O filtro será uma etapa de renderização/pós-processamento.

Casos prioritários:

- Flycast Standalone;
- Supermodel;
- outros runtimes sem solução CRT satisfatória.

## Arquitetura

```text
Emulador
   ↓
Framebuffer / janela
   ↓
Filtro CRT
   ├── Scanlines
   ├── Phosphor / grille
   ├── Mask
   ├── Bloom
   ├── Curvature
   ├── Geometry
   └── Preset
   ↓
Display
```

## Prioridade tecnológica

A implementação deve priorizar soluções reais de pós-processamento compatíveis com o renderer disponível no runtime. Não devemos aplicar simplesmente um filtro de imagem 2D que destrua a geometria ou introduza artefatos desnecessários.

Para RetroArch, o sistema nativo de shaders deve ser preferido quando o jogo estiver sendo executado por um core compatível.

Para Flycast Standalone e Supermodel, a camada externa somente deve ser usada quando houver uma implementação tecnicamente estável para o renderer/versão suportados.

## Perfis

O usuário deverá poder selecionar presets, por exemplo:

- CRT — Light;
- CRT — Arcade;
- CRT — Scanlines;
- CRT — Aperture Grille;
- CRT — Shadow Mask;
- CRT — Curvature;
- CRT — High Resolution.

Também poderá haver perfil por:

- emulador;
- sistema;
- jogo;
- resolução;
- monitor.

## Regras

- não alterar ROMs;
- não alterar dados de emulação;
- não depender de uma resolução fixa;
- respeitar aspect ratio;
- evitar processamento duplicado quando o emulador/core já possui shader adequado;
- permitir desligamento global;
- permitir override por jogo.

## RetroArch

Quando executado pelo RetroArch, o ARCADE MANAGER deve preferir os shaders/presets do próprio RetroArch em vez de adicionar uma camada externa.

A seleção deverá ser representada como metadado do perfil de apresentação:

```text
Presentation Profile
  backend = retroarch
  shader = CRT preset
```

## Flycast / Supermodel

Para runtimes standalone, o projeto deverá separar:

```text
Emulation Backend
Presentation Backend
```

Assim, a ausência de um shader nativo não altera a implementação do emulador.

## Estado

### Planejado

- sistema de Presentation Profiles;
- biblioteca de presets CRT;
- integração RetroArch shaders;
- avaliação técnica de overlay/post-process para Flycast Standalone;
- avaliação técnica para Supermodel;
- perfis por jogo.

Não considerar o filtro implementado até que exista uma solução testada no renderer e na versão de cada emulador suportado.
