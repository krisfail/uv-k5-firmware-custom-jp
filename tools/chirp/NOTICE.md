# wrx-jp CHIRP driver notice

`wrx_jp.py` is an RX-only adaptation for the Japanese `wrx-jp` firmware.
It contains one CHIRP module with separate profiles for:

- UV-K1 / UV-K5 V3 (PY32F071, external-flash map)
- Original UV-K5 (DP32G030, EEPROM map)

The protocol and memory-layout work is adapted from
`armel/uv-k5-chirp-driver`, distributed under CC BY-SA 4.0. The upstream
attribution chain includes Jacek Lipkowski, EGZUMER, JOC2, F4HWN, and the
CHIRP template by Dan Smith. See `LICENSE.txt` for the license text.

This driver is provided as-is. Keep a complete download from the exact radio
before uploading, and do not use the driver to enable or configure
transmission.
