# Arquitetura da GUI — SERM V2

## Padrões obrigatórios de interface

Estas regras são obrigatórias para toda nova tela, painel, botão ou controle interativo da GUI V2 e devem ser aplicadas também ao corrigir ou ampliar telas existentes.

### Ajuda contextual por mouse

Todo botão, ação ou controle interativo que não tenha sua finalidade inequívoca pelo próprio texto deve possuir **tooltip/ajuda contextual ao passar o cursor do mouse**. A ajuda deve explicar de forma curta e objetiva o que a ação faz, seu efeito e, quando relevante, suas condições ou consequências.

Como regra de consistência, novos controles devem receber o tooltip no mesmo ponto em que são criados, evitando controles sem ajuda contextual. Ícones ou botões cuja finalidade dependa apenas de um símbolo devem obrigatoriamente possuir tooltip descritivo.

### Salvar e restaurar padrões

Toda tela relacionada a **Diretórios** ou **Configurações de Emuladores** deve disponibilizar, quando houver estado configurável persistente, as ações **Salvar** e **Restaurar Padrões**.

- **Salvar** aplica e persiste somente as configurações suportadas pela tela, respeitando o formato nativo do emulador e as regras de backup existentes.
- **Restaurar Padrões** retorna os campos editáveis aos valores padrão definidos pelo contrato do emulador/SERM, sem alterar silenciosamente outras chaves ou arquivos não administrados pela tela.
- As duas ações devem possuir tooltip explicativo.
- A restauração deve ser explícita e não deve ocorrer automaticamente ao abrir a tela.
- Quando o formato nativo não possuir um conceito seguro de valor padrão, a tela deve definir/documentar o comportamento de restauração antes de expor a ação.

Essas regras complementam a política de configuração de emuladores em [`emulator-config-policy.md`](emulator-config-policy.md) e são parte do padrão visual e funcional da V2.

## Implementação dos padrões

A implementação atual aplica os padrões de interface diretamente na GUI: a central de Diretórios possui **Salvar** e **Restaurar Padrões** para o emulador selecionado; as configurações suportadas possuem **Salvar configurações** e **Restaurar Padrões**; e a janela principal aplica tooltip mínimo aos botões que não declararam uma ajuda própria. Telas específicas devem continuar declarando tooltips mais descritivos e, quando administrarem estado persistente próprio, manter suas ações de salvar e restauração coerentes com o formato nativo.

## Navegação principal

A aplicação separa a Home, a central de Configuração e os fluxos de trabalho de catálogo e reconstrução. A Home organiza a gestão de instalações por grupos de sistemas; a central de Configuração reúne as preferências do ambiente em uma navegação própria.

## Central de Configuração

A página `ConfigurationPage` apresenta oito áreas, nesta ordem:

1. **Diretórios** — pastas e arquivos de configuração dos emuladores.
2. **Ferramentas** — executáveis auxiliares utilizados pelo SERM.
3. **Emuladores** — opções suportadas e configuração de cada emulador.
4. **Vídeo** — todas as configurações de vídeo dos emuladores, shaders e bezels.
5. **Drivers** — backends e drivers de vídeo, áudio e entrada.
6. **Som** — todas as configurações de áudio dos emuladores.
7. **Controles** — configurações de entrada dos emuladores e diagnóstico de dispositivos.
8. **Aparência e idioma** — tema, idioma e preferências da interface.

A navegação lateral seleciona a área e o painel de conteúdo mostra a página correspondente. A seleção de Controles não inicia descoberta de dispositivos automaticamente; a leitura deve ser uma ação explícita do usuário.

### Diretórios e editores nativos

Diretórios compartilha o catálogo e o agrupamento dos emuladores. As páginas especializadas ficam incorporadas à guia do respectivo emulador:

- **WinUAE** edita diretórios da seção `[WinUAE]` em `winuae.ini`. `configuration.cache` é exibido apenas como referência e não é alterado.
- **Amiberry** e **Altirra** têm páginas próprias para os caminhos e arquivos de configuração de cada ferramenta.
- **ares** mantém o executável, `settings.bml` e diretórios de recursos (`Database`, `hiro`, `Nintendo 64`, `Shaders` e `Systems`) registrados; suas opções suportadas são editadas preservando a estrutura BML. `librashader.dll` e `SDL3.dll` ficam como dependências da instalação, junto ao executável.
- **Azahar** permite registrar o executável e `user/config/qt-config.ini`; suas opções disponíveis são agrupadas por categoria.

Os seletores de Azahar usam os enums/ranges do projeto: API gráfica (Software, OpenGL, Vulkan), escala de resolução (Auto, nativa e 2×–18×), filtros de textura, amostragem, layout, proporção e região. Para ares, as listas fechadas de foco e rewind seguem as escolhas da própria GUI. Drivers, monitores, formatos e dispositivos detectados dependem do backend/hardware; esses valores são somente para leitura quando a lista de opções não é documentada. Se o arquivo contiver valor fora das escolhas documentadas, ele permanece selecionado como valor atual até que o usuário escolha explicitamente outro.

O ares também é listado nas áreas compartilhadas de **Som**, **Controles**, **Emuladores**, **Diretórios** e **Drivers**. Som edita volume e balanço como porcentagens convertidas aos valores reais de `Audio/Volume` e `Audio/Balance`. Controles edita comportamento ao perder foco e conversão digital-analógica, além das atribuições dos cinco Virtual Gamepads gravadas em `VirtualPadN/...`; as células de mapeamento mantêm os valores de atribuição do BML. Emuladores reúne rewind, run-ahead, autosave, opções de desenvolvimento e opções próprias de N64, GBA e Mega Drive. Diretórios inclui as pastas de recursos e os caminhos `Home`, `Firmware`, `Saves`, `Screenshots`, `Debugging` e `ArcadeRoms` do `settings.bml`. Drivers oferece seletores para os backends de vídeo, áudio e entrada documentados na configuração fornecida do ares. Essas mudanças são gravadas no BML e passam a valer quando o ares carregar as configurações. Cada editor altera somente chaves existentes e mantém backup do arquivo.

Referências primárias: [Azahar settings.h](https://github.com/azahar-emu/azahar/blob/master/src/common/settings.h), [Azahar default_ini.h](https://github.com/azahar-emu/azahar/blob/master/src/android/app/src/main/jni/default_ini.h), [ares settings.hpp](https://github.com/ares-emulator/ares/blob/master/desktop-ui/settings/settings.hpp), [ares options.cpp](https://github.com/ares-emulator/ares/blob/master/desktop-ui/settings/options.cpp) e [ares input.cpp](https://github.com/ares-emulator/ares/blob/master/desktop-ui/settings/input.cpp).
- Para MAME, a página permite selecionar separadamente o executável e o diretório de instalação.
- Os demais emuladores usam os campos comuns de diretório e referência ao arquivo de configuração quando disponíveis.

### Configurações de emuladores

A página Emuladores também usa grupos e guias por emulador, e reúne as opções gerais. Opções de vídeo, áudio, drivers e controles são encaminhadas às respectivas áreas. Salvar altera somente chaves suportadas e cria um backup. WinUAE, Amiberry e Altirra usam páginas específicas para seus formatos, separadas por área. Emuladores ainda sem mapeamento específico mostram uma guia de preparação, com o estado do executável e do arquivo de configuração.

### Vídeo, shaders e bezels

As opções visuais e de renderização de cada emulador ficam nesta seção, separadas das configurações gerais do emulador. Cada emulador tem uma única guia com subguias **Vídeo**, **Shaders** e **Bezels**, evitando uma lista global de vídeo que repetia opções. A subguia Vídeo mostra somente as opções daquele emulador. Uma opção nativa aparece em apenas uma subguia; por exemplo, GLSL e recorte de artwork ficam na subguia Vídeo do MAME, enquanto Bezels mantém apenas caminhos e layouts.

### Som e controles dos emuladores

A página Som edita as opções de áudio suportadas nos arquivos dos emuladores; ela não controla áudio da interface do SERM. Controles reúne opções de entrada dos emuladores e mantém o diagnóstico de dispositivos em uma guia separada. A detecção de hardware continua sendo iniciada explicitamente pelo usuário.

#### Menus de vídeo do ares

A guia **ares** fica em Vídeo, no grupo Multi-sistema, junto às opções visuais dos demais emuladores. Ela contém as subguias **Vídeo**, **Shaders** e **Bezels**. Vídeo reproduz os controles nativos: sliders de luminância, saturação e gama; opções de emulação e renderização; e resolução interna do Nintendo 64 (1×, 2× e 4× nativa). O menu **Window Size** oferece as dimensões NTSC, PAL, SVGA, qHD, XGA, XGA+, HD, SXGA, WXGA e HD+, além de tamanho personalizado e centralização. **Output** agrupa escala (melhor ajuste, inteiro automático, inteiro fixo de 1× a 7× e preencher), correção de proporção e comportamento da janela. Os menus gravam os valores BML correspondentes no `settings.bml`; as opções N64 são lidas tanto da seção `Video` quanto de `Nintendo64`, conforme a versão do arquivo.

Shaders percorre os presets `.slangp` da pasta `Shaders` registrada (ou da pasta `Shaders` ao lado de `ares.exe`) e organiza os arquivos em submenus conforme suas pastas. O caminho relativo do preset selecionado é escrito em `Video.Shader`. A lista acompanha a estrutura instalada do [libretro/slang-shaders](https://github.com/libretro/slang-shaders); shaders e valores de saída são gravados apenas quando as chaves correspondentes já existem no BML. Bezels informa que o ares não tem configuração nativa de molduras. Ares documenta a qualidade N64 `SD`, `HD` e `UHD` como 1×, 2× e 4× nativa; as opções de supersampling e processamento da interface de vídeo também são oferecidas pelo núcleo N64 ([fonte](https://github.com/ares-emulator/ares/blob/master/ares/n64/system/system.cpp)).

### Drivers dos emuladores

A seção Drivers reúne seletores de backend/API de vídeo, áudio e entrada e valores dinâmicos que dependem do dispositivo. No ares, os seletores usam os valores documentados em sua configuração nativa; em outros emuladores, listas de hardware não documentadas permanecem somente para leitura ou preservam o valor atual desconhecido. As configurações editáveis gravam somente chaves já presentes no arquivo do emulador.

O catálogo compartilhado em `emulator_catalog.py` define os grupos de interface usados pela Home e pelas áreas de Diretórios, Emuladores, Vídeo e Drivers. Ele organiza a apresentação; não unifica formatos de configuração nem regras próprias dos emuladores.

### Configuração do Amiberry

Amiberry usa `Settings/amiberry.conf` para preferências globais e caminhos; `Settings/amiberry.ini` contém estado da janela/navegação e a lista de Kickstarts detectadas. O painel separa Geral, Vídeo, Áudio, Drivers, Controles e WHDLoad, ativando apenas chaves presentes no arquivo. Seletores de escala gravam `-1` Auto, `0` Nearest, `1` Linear ou `2` Integer; modo de tela grava `0` Windowed, `1` Fullscreen exclusivo ou `2` Full-window; modo de linhas grava `0` Single, `1` Double ou `2` Scanlines. Shaders incluem os nomes integrados e arquivos `.glsl`/`.glslp` encontrados no diretório configurado, preservando o valor atual desconhecido. Consulte a [referência oficial das opções globais do Amiberry](https://github.com/BlitterStudio/amiberry/wiki/Amiberry.conf-options).

Play, Quickstart e CPU configuram conteúdo e perfis de máquina UAE em arquivos próprios, não em `amiberry.conf`; o editor global não os altera. A página Diretórios exibe o executável, marcador portátil, pastas e DLLs quando encontrados na raiz registrada e edita somente caminhos cujas chaves já existem em `amiberry.conf`. `amiberry.ini` e os itens do inventário são referências, não arquivos de preferências editáveis.

## Home de emuladores

A Home apresenta os emuladores em guias por grupo de sistemas e mantém uma guia própria para RetroArch. As ações de instalação e atualização ficam junto ao log operacional. A configuração detalhada permanece na central de Configuração.

## MAME Studio

O fluxo operacional deve ser linear:

**Catálogo → Scan → Filtros → Reconstrução**

As páginas de fase são as implementações canônicas. Interfaces antigas embutidas em páginas de catálogo não devem duplicar operações de filtro ou reconstrução.

## Regra de organização

- Uma operação deve ter uma única tela canônica.
- Componentes visuais compartilhados devem ser públicos e reutilizáveis.
- Serviços concentram regras de negócio; páginas concentram composição da GUI.
- A organização por grupos é compartilhada, mas configuração e edição de arquivos permanecem específicas a cada emulador.
- Páginas legadas podem permanecer durante a migração V1 → V2, mas não devem ser expostas simultaneamente na navegação V2.
