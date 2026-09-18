# Auditoria do banco MAME — SERM V2

**Banco:** `C:\Users\leost\SERM\v2\data\database\serm.db`

Este documento é gerado a partir do banco real. Ele descreve o que foi efetivamente persistido, sem inferir campos que não estejam presentes.

**Tabelas MAME encontradas:** 31

## `mame_adjuster`

**Registros:** 2,050

**Colunas:** `id`, `machine_id`, `name`, `default_value`, `min_value`, `max_value`

### Amostra

| id | machine_id | name | default_value | min_value | max_value |
| --- | --- | --- | --- | --- | --- |
| 1 | 83 | Pot: Master Volume | 50 | NULL | NULL |
| 2 | 84 | Pot: Master Volume | 50 | NULL | NULL |
| 3 | 226 | VR2 - DAC Volume | 90 | NULL | NULL |

## `mame_biosset`

**Registros:** 40,611

**Colunas:** `id`, `machine_id`, `name`, `description`, `default_flag`

### Amostra

| id | machine_id | name | description | default_flag |
| --- | --- | --- | --- | --- |
| 1 | 4 | au-nsw1 | Aristocrat MK6 Base (24013001, NSW/ACT) | no |
| 2 | 4 | au-nsw2 | Aristocrat MK6 Base (21012901, NSW/ACT) | no |
| 3 | 4 | au-nsw3 | Aristocrat MK6 Base (19012801, NSW/ACT) | no |

## `mame_chip`

**Registros:** 198,113

**Colunas:** `id`, `machine_id`, `type`, `tag`, `name`, `clock`

### Amostra

| id | machine_id | type | tag | name | clock |
| --- | --- | --- | --- | --- | --- |
| 1 | 1 | cpu | maincpu | Zilog Z80 | 3867120 |
| 2 | 1 | audio | speaker | Speaker | NULL |
| 3 | 1 | audio | samples | Samples | NULL |

## `mame_classification`

**Registros:** 37,995

**Colunas:** `id`, `machine_id`, `source_document_id`, `machine_name`, `section_raw`, `category`, `subcategory`, `flags_raw`, `resolved_status`, `imported_at`

### Amostra

| id | machine_id | source_document_id | machine_name | section_raw | category | subcategory | flags_raw | resolved_status | imported_at |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 126361 | 11180 | 4 | hkuranai | Arcade: Arcade / Fortune Teller | Arcade | Fortune Teller | NULL | resolved | 2026-08-30T18:59:25.770498+00:00 |
| 126362 | 2722 | 4 | blnctry | Arcade: Arcade / Physical Ability | Arcade | Physical Ability | NULL | resolved | 2026-08-30T18:59:25.770498+00:00 |
| 126363 | 3063 | 4 | brkball | Arcade: Arcade / Pinball | Arcade | Pinball | NULL | resolved | 2026-08-30T18:59:25.770498+00:00 |

## `mame_configuration`

**Registros:** 36,808

**Colunas:** `id`, `machine_id`, `name`, `tag`, `mask`, `value`, `default_value`

### Amostra

| id | machine_id | name | tag | mask | value | default_value |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 12 | Treat Joystick as... | CONFIG | 1 | NULL | NULL |
| 2 | 13 | Treat Joystick as... | CONFIG | 1 | NULL | NULL |
| 3 | 18 | Bilinear Filtering | powervr2:PVR_DEBUG | 1 | NULL | NULL |

## `mame_confsetting`

**Registros:** 343,901

**Colunas:** `id`, `configuration_id`, `name`, `value`

### Amostra

| id | configuration_id | name | value |
| --- | --- | --- | --- |
| 1 | 1 | Buttons | 0 |
| 2 | 1 | Paddle | 1 |
| 3 | 2 | Buttons | 0 |

## `mame_control`

**Registros:** 57,793

**Colunas:** `id`, `input_id`, `type`, `player`, `buttons`, `minimum`, `maximum`, `sensitivity`, `keydelta`, `reverse`, `ways`

### Amostra

| id | input_id | type | player | buttons | minimum | maximum | sensitivity | keydelta | reverse | ways |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 1 | joy | 1 | 1 | NULL | NULL | NULL | NULL | no | 4 |
| 2 | 1 | joy | 2 | 1 | NULL | NULL | NULL | NULL | no | 4 |
| 3 | 2 | joy | 1 | 1 | NULL | NULL | NULL | NULL | no | 4 |

## `mame_device`

**Registros:** 12,482

**Colunas:** `id`, `machine_id`, `type`, `tag`, `name`, `clock`

### Amostra

| id | machine_id | type | tag | name | clock |
| --- | --- | --- | --- | --- | --- |
| 1 | 12 | quickload | quickload | NULL | NULL |
| 2 | 12 | cartridge | cartslot | NULL | NULL |
| 3 | 13 | quickload | quickload | NULL | NULL |

## `mame_device_ref`

**Registros:** 781,216

**Colunas:** `id`, `machine_id`, `name`, `tag`, `mandatory`

### Amostra

| id | machine_id | name | tag | mandatory |
| --- | --- | --- | --- | --- |
| 1 | 1 | z80 | :maincpu | NULL |
| 2 | 1 | gfxdecode | :gfxdecode | NULL |
| 3 | 1 | palette | :palette | NULL |

## `mame_dipswitch`

**Registros:** 572,398

**Colunas:** `id`, `machine_id`, `name`, `tag`, `mask`, `value`, `default_value`

### Amostra

| id | machine_id | name | tag | mask | value | default_value |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 1 | Coin A | D1D0 | 15 | NULL | NULL |
| 2 | 1 | Coin B | D1D0 | 240 | NULL | NULL |
| 3 | 1 | Lives | D3D2 | 3 | NULL | NULL |

## `mame_dipvalue`

**Registros:** 1,439,502

**Colunas:** `id`, `dipswitch_id`, `name`, `value`, `description`

### Amostra

| id | dipswitch_id | name | value | description |
| --- | --- | --- | --- | --- |
| 1 | 1 | 4 Coins/1 Credit | 0 | NULL |
| 2 | 1 | 3 Coins/1 Credit | 1 | NULL |
| 3 | 1 | 2 Coins/1 Credit | 2 | NULL |

## `mame_disk`

**Registros:** 1,402

**Colunas:** `id`, `machine_id`, `name`, `md5`, `sha1`, `merge`, `region`, `index_value`, `writable`, `status`, `optional`

### Amostra

| id | machine_id | name | md5 | sha1 | merge | region | index_value | writable | status | optional |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 87 | mda-c0004a_revb_lindyellow_v2.4.20_mvl31a_boot_2.01 | NULL | e13da5f827df852e742b594729ee3f933b387410 | mda-c0004a_revb_lindyellow_v2.4.20_mvl31a_boot_2.01 | cf | 0 | no | good | no |
| 2 | 87 | dvp-0027a | NULL | da1aacee9e32e813844f4d434981e69cc5c80682 | NULL | dvd | 0 | no | good | no |
| 3 | 232 | 99bottles | NULL | 0b874178c8dd3cfc451deb53dc7936dc4ad5a04f | NULL | pci:07.1:ide1:0:xm3301 | 0 | no | baddump | no |

## `mame_display`

**Registros:** 24,365

**Colunas:** `id`, `machine_id`, `tag`, `type`, `rotate`, `width`, `height`, `refresh_hz`, `refresh_raw`, `pixclock`, `htotal`, `hbend`, `hbstart`, `vtotal`, `vbend`, `vbstart`, `hsync`, `vsync`, `xaspect`, `yaspect`, `orientation_raw`, `source`, `confidence`

### Amostra

| id | machine_id | tag | type | rotate | width | height | refresh_hz | refresh_raw | pixclock | htotal | hbend | hbstart | vtotal | vbend | vbstart | hsync | vsync | xaspect | yaspect | orientation_raw | source | confidence |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 1 | screen | raster | 270 | 256 | 224 | 60.0 | 60.000000 | 5156160 | 328 | 0 | 256 | 262 | 0 | 224 | NULL | NULL | NULL | NULL | 270 | listxml | authoritative |
| 2 | 2 | screen | raster | 270 | 256 | 224 | 60.0 | 60.000000 | 5156160 | 328 | 0 | 256 | 262 | 0 | 224 | NULL | NULL | NULL | NULL | 270 | listxml | authoritative |
| 3 | 3 | screen | lcd | 0 | 320 | 240 | 60.0 | 60.000000 | NULL | NULL | NULL | NULL | NULL | NULL | NULL | NULL | NULL | NULL | NULL | 0 | listxml | authoritative |

## `mame_driver`

**Registros:** 43,050

**Colunas:** `id`, `machine_id`, `status`, `emulation`, `color`, `sound`, `graphic`, `cocktail`, `protection`, `savestate`, `requires_artwork`, `unofficial`, `incomplete`, `notes`

### Amostra

| id | machine_id | status | emulation | color | sound | graphic | cocktail | protection | savestate | requires_artwork | unofficial | incomplete | notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 1 | imperfect | good | NULL | NULL | NULL | NULL | NULL | unsupported | NULL | no | no | NULL |
| 2 | 2 | preliminary | preliminary | NULL | NULL | NULL | NULL | NULL | unsupported | NULL | no | no | NULL |
| 3 | 3 | preliminary | preliminary | NULL | NULL | NULL | NULL | NULL | unsupported | NULL | no | no | NULL |

## `mame_feature`

**Registros:** 24,143

**Colunas:** `id`, `machine_id`, `type`, `status`

### Amostra

| id | machine_id | type | status |
| --- | --- | --- | --- |
| 1 | 1 | sound | imperfect |
| 2 | 2 | sound | imperfect |
| 3 | 3 | sound | unemulated |

## `mame_ingestion_run`

**Registros:** 0

**Colunas:** `id`, `import_id`, `started_at`, `finished_at`, `status`, `stage`, `executable`, `mame_build`, `source_hash`, `byte_length`, `machine_count`, `elapsed_seconds`, `error_type`, `error_message`

_Tabela sem registros._

## `mame_input`

**Registros:** 43,656

**Colunas:** `id`, `machine_id`, `players`, `coins`, `service`, `tilt`

### Amostra

| id | machine_id | players | coins | service | tilt |
| --- | --- | --- | --- | --- | --- |
| 1 | 1 | 2 | 2 | NULL | NULL |
| 2 | 2 | 2 | 2 | NULL | NULL |
| 3 | 3 | 0 | NULL | NULL | NULL |

## `mame_listxml_document`

**Registros:** 1

**Colunas:** `id`, `import_id`, `source_hash`, `byte_length`, `encoding`, `xml_text`, `stored_at`

### Amostra

| id | import_id | source_hash | byte_length | encoding | xml_text | stored_at |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 1 | 72ce1d31349f947c03477fe54eba641fc646d35d91067b06323f39acba352b6d | 319966164 | utf-8 | <?xml version="1.0"?> <!DOCTYPE mame [ <!ELEMENT mame (machine+)> 	<!ATTLIST mame build CDATA #IMPLIED> 	<!ATTLIST mame debug (yes\|no) "no"> 	<!ATTLIST mame mameconfig CDATA #REQUIRED> 	<!ELEMENT machine (description, year?, manufacturer?, biosset*, rom*, disk*, device_ref*, sample*, chip*, display*, sound?, input?, dipswitch*, configuration*, port*, adjuster*, driver?, feature*, device*, slot*, softwarelist*, ramoption*)> 		<!ATTLIST machine name CDATA #REQUIRED> 		<!ATTLIST machine sourcefile | 2026-08-30T17:38:40.276842+00:00 |

## `mame_listxml_import`

**Registros:** 1

**Colunas:** `id`, `emulator_id`, `executable`, `mame_build`, `mame_config`, `debug`, `imported_at`, `source_hash`, `xml_path`, `machine_count`, `byte_length`, `parser_version`, `status`

### Amostra

| id | emulator_id | executable | mame_build | mame_config | debug | imported_at | source_hash | xml_path | machine_count | byte_length | parser_version | status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 1 | G:\LaunchBox\emulators\mame\mame.exe | 0.289 (mame0289) | 10 | no | 2026-08-30T17:38:40.276842+00:00 | 72ce1d31349f947c03477fe54eba641fc646d35d91067b06323f39acba352b6d | C:\Users\leost\SERM\v2\data\mame\listxml\listxml-72ce1d31349f947c.xml | 50368 | 319966164 | catalog-2.0 | completed |

## `mame_machine`

**Registros:** 50,368

**Colunas:** `id`, `import_id`, `name`, `sourcefile`, `isbios`, `isdevice`, `ismechanical`, `runnable`, `cloneof`, `romof`, `sampleof`, `description`, `year`, `manufacturer`, `xml_node_id`, `ingested_at`

### Amostra

| id | import_id | name | sourcefile | isbios | isdevice | ismechanical | runnable | cloneof | romof | sampleof | description | year | manufacturer | xml_node_id | ingested_at |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 1 | 005 | sega/segag80r.cpp | no | no | no | yes | NULL | NULL | 005 | 005 | 1981 | Sega | NULL | 2026-08-30 17:38:41 |
| 2 | 1 | 005a | sega/segag80r.cpp | no | no | no | yes | 005 | 005 | 005 | 005 (earlier version?) | 1981 | Sega | NULL | 2026-08-30 17:38:41 |
| 3 | 1 | 100in1rg | handheld/generalplus_gp3x_unknown.cpp | no | no | no | yes | NULL | NULL | NULL | 100-in-1 Retro Gaming Console (SY-909) | 202? | <unknown> | NULL | 2026-08-30 17:38:41 |

## `mame_machine_metadata`

**Registros:** 50,368

**Colunas:** `machine_id`, `emulation_status`, `driver_status`, `savestate`, `requires_artwork`, `unofficial`, `nosoundhardware`, `incomplete`

### Amostra

| machine_id | emulation_status | driver_status | savestate | requires_artwork | unofficial | nosoundhardware | incomplete |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | imperfect | imperfect | unsupported | NULL | no | no | no |
| 2 | preliminary | preliminary | unsupported | NULL | no | no | no |
| 3 | preliminary | preliminary | unsupported | NULL | no | no | no |

## `mame_port`

**Registros:** 349,028

**Colunas:** `id`, `machine_id`, `tag`, `type`, `mask`, `defvalue`, `condition`

### Amostra

| id | machine_id | tag | type | mask | defvalue | condition |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 1 | :D1D0 | NULL | NULL | NULL | NULL |
| 2 | 1 | :D3D2 | NULL | NULL | NULL | NULL |
| 3 | 1 | :D5D4 | NULL | NULL | NULL | NULL |

## `mame_ramoption`

**Registros:** 6,649

**Colunas:** `id`, `machine_id`, `name`, `default_value`

### Amostra

| id | machine_id | name | default_value |
| --- | --- | --- | --- |
| 1 | 97 | 2M | NULL |
| 2 | 97 | 4M | NULL |
| 3 | 97 | 8M | NULL |

## `mame_resolution`

**Registros:** 23,598

**Colunas:** `id`, `source_document_id`, `machine_id`, `machine_name`, `resolution_raw`, `width`, `height`, `resolved_status`, `imported_at`

### Amostra

| id | source_document_id | machine_id | machine_name | resolution_raw | width | height | resolved_status | imported_at |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 5 | 23862 | microvsn | 16x16 | 16 | 16 | resolved | 2026-08-30T18:59:26.423526+00:00 |
| 2 | 5 | 40595 | ttwistbq | 64x8 | 64 | 8 | resolved | 2026-08-30T18:59:26.423526+00:00 |
| 3 | 5 | 40596 | ttwistfb | 64x8 | 64 | 8 | resolved | 2026-08-30T18:59:26.423526+00:00 |

## `mame_rom`

**Registros:** 371,752

**Colunas:** `id`, `machine_id`, `name`, `bios`, `size`, `crc`, `sha1`, `md5`, `merge`, `region`, `offset`, `status`, `optional`, `dispose`

### Amostra

| id | machine_id | name | bios | size | crc | sha1 | md5 | merge | region | offset | status | optional | dispose |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 1 | 1346b.cpu-u25 | NULL | 2048 | 8e68533e | a257c556d31691068ed5c991f1fb2b51da4826db | NULL | NULL | maincpu | 0 | good | no | NULL |
| 2 | 1 | 5092.prom-u1 | NULL | 2048 | 29e10a81 | c4b4e6c75bcf276e53f39a456d8d633c83dcf485 | NULL | NULL | maincpu | 800 | good | no | NULL |
| 3 | 1 | 5093.prom-u2 | NULL | 2048 | e1edc3df | 4f593546bbb0f50850dc6286cb514af6831c27a7 | NULL | NULL | maincpu | 1000 | good | no | NULL |

## `mame_sample`

**Registros:** 28,735

**Colunas:** `id`, `machine_id`, `name`

### Amostra

| id | machine_id | name |
| --- | --- | --- |
| 1 | 1 | lexplode |
| 2 | 1 | sexplode |
| 3 | 1 | dropbomb |

## `mame_slot`

**Registros:** 26,111

**Colunas:** `id`, `machine_id`, `name`

### Amostra

| id | machine_id | name |
| --- | --- | --- |
| 1 | 12 | cartslot |
| 2 | 13 | cartslot |
| 3 | 65 | cslot1 |

## `mame_slot_option`

**Registros:** 544,952

**Colunas:** `id`, `slot_id`, `name`, `devname`, `is_default`

### Amostra

| id | slot_id | name | devname | is_default |
| --- | --- | --- | --- | --- |
| 1 | 6 | terminal | serial_terminal | no |
| 2 | 6 | swtpc8212 | swtpc8212_terminal | no |
| 3 | 6 | sunkbd | sunkbd_adaptor | no |

## `mame_softwarelist`

**Registros:** 7,924

**Colunas:** `id`, `machine_id`, `tag`, `name`, `status`, `filter`

### Amostra

| id | machine_id | tag | name | status | filter |
| --- | --- | --- | --- | --- | --- |
| 1 | 12 | cart_list | vc4000 | original | NULL |
| 2 | 13 | cart_list | vc4000 | original | NULL |
| 3 | 89 | cart_list | 32x | original | NTSC-U |

## `mame_source_document`

**Registros:** 3

**Colunas:** `id`, `source_type`, `source_name`, `source_path`, `source_hash`, `byte_length`, `imported_at`, `status`

### Amostra

| id | source_type | source_name | source_path | source_hash | byte_length | imported_at | status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 4 | catlist | catlist.ini | G:\LaunchBox\emulators\mame\folders\catlist.ini | 72c535650b4e1cec80e80783a7be1b6b3317419b37db5a7269bbb4535939ceac | 551049 | 2026-08-30T18:59:25.770498+00:00 | completed |
| 5 | resolution_ini | resolution.ini | G:\LaunchBox\emulators\mame\folders\resolution.ini | 746f227fb6535d6a038f840402105ecb7579af711bc10e4d852dccd1e5b1aa42 | 238656 | 2026-08-30T18:59:26.423526+00:00 | completed |
| 6 | vsync_ini | Vsync.ini | G:\LaunchBox\emulators\mame\folders\Vsync.ini | efe252cb1657b5e86a5a7522812959b0f787c570e0c82c8ed2d2f4b000d31fcb | 184539 | 2026-08-30T19:23:25.320935+00:00 | completed |

## `mame_vsync`

**Registros:** 18,376

**Colunas:** `id`, `source_document_id`, `machine_id`, `machine_name`, `vsync_enabled`, `value_raw`, `resolved_status`, `imported_at`

### Amostra

| id | source_document_id | machine_id | machine_name | vsync_enabled | value_raw | resolved_status | imported_at |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 6 | NULL | RootFolderIcon mame | 1 | 1 | unresolved | 2026-08-30T19:23:25.320935+00:00 |
| 2 | 6 | NULL | SubFolderIcon folder | 1 | 1 | unresolved | 2026-08-30T19:23:25.320935+00:00 |
| 3 | 6 | 39985 | tmosh | 1 | 1 | resolved | 2026-08-30T19:23:25.320935+00:00 |
