# UV-K5 Japanese receive-only firmware

[日本語版README](README.ja.md) | [操作・ビルドcheatsheet](CHEATSHEET.ja.md) | [Developer guide](DEVELOPMENT.md) | [CHIRP driver](tools/chirp/README.ja.md) | [Technical feature details](docs/FEATURES_TECHNICAL.ja.md)

This repository is the downstream fork [krisfail/uv-k5-firmware-custom-jp](https://github.com/krisfail/uv-k5-firmware-custom-jp), with [armel/uv-k5-firmware-custom](https://github.com/armel/uv-k5-firmware-custom) as its upstream. The upstream work builds on [Egzumer custom firmware](https://github.com/egzumer/uv-k5-firmware-custom), [OneOfEleven custom firmware](https://github.com/OneOfEleven/uv-k5-firmware-custom), the [fagci spectrum analyzer](https://github.com/fagci/uv-k5-firmware-fagci-mod/tree/refactor), and the original open firmware by [DualTachyon](https://github.com/DualTachyon/uv-k5-firmware).

## Scope and safety

This fork targets Japanese-language, receive-only use on the UV-K5 family. It is not an official Quansheng, F4HWN, or armel release.

The code analysis, implementation, test support, and documentation were partly AI-assisted and were reviewed against the source, static tests, builds, and available hardware results. AI assistance does not replace maintainer review or user testing.

The firmware is provided **as is**, without warranty. The maintainers are not responsible for radio damage, failed flashing, loss of EEPROM, calibration data or configuration, recovery failure, or use that violates local radio regulations. Back up EEPROM and calibration data before flashing, use an image for the exact hardware model, and keep a recovery method available.

## What this fork provides

- Japanese menu labels and Japanese glyphs in the large and small display paths.
- Receive-only operation: TX paths and TX-related menus are removed, and PTT operates as monitor control.
- Domestic FM broadcast reception limited to `76.0–95.0 MHz`.
- Receive band presets, `W+`/`W`/`N`/`N-` bandwidths (25/20/12.5/6.25 kHz), `MAIN ONLY`/`DUAL RX`/`SINGLE`, memory banks, automatic squelch, AGC protection, and temporary scan skipping.
- The `RXExt` radio menu item enables or disables those added receive features as a group; it defaults to enabled.
- The Japanese font data is based on the work in [rainy-knight/uv-k5-jp](https://github.com/rainy-knight/uv-k5-jp).

The detailed operation guide is in [README.ja.md](README.ja.md). The button and build command quick reference is in [CHEATSHEET.ja.md](CHEATSHEET.ja.md). Technical implementation details are in [docs/FEATURES_TECHNICAL.ja.md](docs/FEATURES_TECHNICAL.ja.md). CHIRP-specific memory-map and upload guidance is in [tools/chirp/README.ja.md](tools/chirp/README.ja.md); legal attribution remains in `tools/chirp/NOTICE.md` and `tools/chirp/LICENSE.txt`.

Development-specific source layout, change boundaries, atlas generation, validation, and release handling are collected in [DEVELOPMENT.md](DEVELOPMENT.md). `README.md` intentionally keeps only the general usage and build information needed to get started.

## Upstream feature summary

This fork retains selected upstream improvements in the radio driver, scanning, spectrum and display handling, audio controls, memory operation, and user interface. The complete upstream feature catalogue is intentionally not duplicated here; see the [armel project Wiki](https://github.com/armel/uv-k5-firmware-custom/wiki) and the [upstream repository](https://github.com/armel/uv-k5-firmware-custom) for background and general documentation.

## Building

Run these commands from the repository root. The host build requires `arm-none-eabi-gcc`; Python and `crcmod` are additionally needed for the packed image and the full static test workflow.

```powershell
make test
make -j2
```

The build produces:

- `wrx-jp.bin`: raw firmware image.
- `wrx-jp.packed.bin`: packed image, when Python and `crcmod` are available.
- `wrx-jp`: ELF image for debugging.

Run the host regression tests separately with `make test` or the equivalent Python command in [DEVELOPMENT.md](DEVELOPMENT.md).

To rebuild from a clean state:

```powershell
make clean
make -j2
```

Back up the radio before flashing. The upstream [Flashing the firmware](https://github.com/armel/uv-k5-firmware-custom/wiki/Flashing-the-firmware) page describes the general procedure; use only an image for the exact radio model.

## CHIRP driver

Copy `tools/chirp/wrx_jp.py` into the CHIRP driver directory and select `UV-K5 (wrx-jp RX-only)` for this legacy DP32G030 radio. The same module contains a separate UV-K1 / UV-K5 V3 profile; do not use that profile for the legacy UV-K5. The driver is RX-only and its upload whitelist excludes calibration data. Read the [CHIRP guide](tools/chirp/README.ja.md) before writing.

## Other references

- [armel/uv-k5-firmware-custom Wiki](https://github.com/armel/uv-k5-firmware-custom/wiki)
- [armel/uv-k5-chirp-driver](https://github.com/armel/uv-k5-chirp-driver)
- [ludwich66 Quansheng UV-K5 Wiki](https://github.com/ludwich66/Quansheng_UV-K5_Wiki/wiki)
- [amnemonic tools and firmware information](https://github.com/amnemonic/Quansheng_UV-K5_Firmware)

## Acknowledgements / 謝辞

This project is possible because of the open-source work and review by the upstream projects and contributors listed below.

### Donations

Special thanks to Jean-Cyrille F6IWW (2 times), Fabrice 14RC123, David F4BPP, Olivier 14RC206, Frédéric F4ESO, Stéphane F5LGW, Jorge Ornelas (4 times), Laurent F4AXK, Christophe Morel, Clayton W0LED, Pierre Antoine F6FWB, Jean-Claude 14FRS3306, Thierry F4GVO, Eric F1NOU, PricelessToolkit, Ady M6NYJ, Tom McGovern (4 times), Joseph Roth, Pierre-Yves Colin, Frank DJ7FG, Marcel Testaz, Brian Frobisher, Yannick F4JFO, Paolo Bussola, Dirk DL8DF, Levente Szőke (2 times), Bernard-Michel Herrera, Jérôme Saintespes, Paul Davies, RS (3 times), Johan F4WAT, Robert Wörle, Rafael Sundorf, Paul Harker, Peter Fintl, Pascal F4ICR (2 times), Mike DL2MF, Eric KI1C (2 times), Phil G0ELM, Jérôme Lambert, Meinhard Frank Günther, Eliot Vedel, Alfonso EA7KDF, Jean-François F1EVM, Robert DC1RDB, Ian KE2CHJ, Daryl VK3AWA, Roberto Brunelli, Robert Boardman, Stephen Oliver, Nicolas F4INE and William Bruno for their [donations](https://www.paypal.com/paypalme/F4HWN). That’s so kind of them. Thanks so much 🙏🏻

### Credits

Many thanks to:

- [Egzumer](https://github.com/egzumer)
- [OneOfEleven](https://github.com/OneOfEleven)
- [DualTachyon](https://github.com/DualTachyon)
- UV-K5-RX-JP: receive-only and wideband receiver feature ideas were used as a partial reference.
- [Mikhail / fagci](https://github.com/fagci)
- [Andrej](https://github.com/Tunas1337)
- [Manuel](https://github.com/manujedi)
- @wagner
- @Lohtse Shar
- [@Matoz](https://github.com/spm81)
- @Davide
- @Ismo OH2FTG
- @d1ced95
- and the other contributors to the upstream projects.

## License

Copyright 2023 Dual Tachyon
https://github.com/DualTachyon

Licensed under the Apache License, Version 2.0 (the "License"); you may not use this file except in compliance with the License. You may obtain a copy of the License at

https://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the specific language governing permissions and limitations under the License.
