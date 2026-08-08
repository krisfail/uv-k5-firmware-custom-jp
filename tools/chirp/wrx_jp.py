# Copyright 2026 wrx-jp contributors
#
# This driver is adapted from the Quansheng UV-K5 CHIRP driver published by
# armel/uv-k5-chirp-driver.  See LICENSE.txt and NOTICE.md for attribution.
# The armel repository is distributed under CC BY-SA 4.0.
#
# wrx-jp is an RX-only Japanese firmware.  This driver deliberately does not
# expose transmit frequency, transmit tone, PTT, or power controls.

"""CHIRP driver for the wrx-jp RX-only firmware family.

Two hardware profiles are intentionally kept in this one module:

* ``UV-K1 / UV-K5 V3``: PY32F071 and the external-flash EEPROM map.
* ``UV-K5``: the original DP32G030 and the 0x2000-byte EEPROM map.

K1 and K5 V3 are one hardware/protocol family.  They must not be treated as
the legacy UV-K5, even though the serial protocol is compatible.
"""

import logging
import struct

from chirp import chirp_common, directory, errors, memmap
from chirp.settings import (
    InvalidValueError,
    RadioSetting,
    RadioSettingGroup,
    RadioSettings,
    RadioSettingValueInteger,
)


LOG = logging.getLogger(__name__)

MEM_BLOCK = 0x80
FM_MIN = 760  # 76.0 MHz, stored in 0.1 MHz units
FM_MAX = 950  # 95.0 MHz, Japanese FM broadcast limit

BANDS_WIDE = (
    (18.0, 108.0),
    (108.0, 136.9999),
    (137.0, 173.9999),
    (174.0, 349.9999),
    (350.0, 399.9999),
    (400.0, 469.9999),
    (470.0, 1300.0),
)

STEPS = (
    2.5, 5, 6.25, 10, 12.5, 25, 8.33, 0.01, 0.05, 0.1, 0.25, 0.5,
    1, 1.25, 9, 15, 20, 30, 50, 100, 125, 200, 250, 500,
)

CTCSS_TONES = (
    67.0, 69.3, 71.9, 74.4, 77.0, 79.7, 82.5, 85.4, 88.5, 91.5,
    94.8, 97.4, 100.0, 103.5, 107.2, 110.9, 114.8, 118.8, 123.0,
    127.3, 131.8, 136.5, 141.3, 146.2, 151.4, 156.7, 159.8, 162.2,
    165.5, 167.9, 171.3, 173.8, 177.3, 179.9, 183.5, 186.2, 189.9,
    192.8, 196.6, 199.5, 203.5, 206.5, 210.7, 218.1, 225.7, 229.1,
    233.6, 241.8, 250.3, 254.1,
)

DTCS_CODES = (
    23, 25, 26, 31, 32, 36, 43, 47, 51, 53, 54, 65, 71, 72, 73, 74,
    114, 115, 116, 122, 125, 131, 132, 134, 143, 145, 152, 155, 156,
    162, 165, 172, 174, 205, 212, 223, 225, 226, 243, 244, 245, 246,
    251, 252, 255, 261, 263, 265, 266, 271, 274, 306, 311, 315, 325,
    331, 332, 343, 346, 351, 356, 364, 365, 371, 411, 412, 413, 423,
    431, 432, 445, 446, 452, 454, 455, 462, 464, 465, 466, 503, 506,
    516, 523, 526, 532, 546, 565, 606, 612, 624, 627, 631, 632, 654,
    662, 664, 703, 712, 723, 731, 732, 734, 743, 754,
)


class _Profile:
    def __init__(self, name, image_size, memory_channels, special_base,
                 name_base, attr_base, attr_width, attr_limit, fm_cfg,
                 fm_channels, fm_count, upload_ranges):
        self.name = name
        self.image_size = image_size
        self.memory_channels = memory_channels
        self.special_base = special_base
        self.name_base = name_base
        self.attr_base = attr_base
        self.attr_width = attr_width
        self.attr_limit = attr_limit
        self.fm_cfg = fm_cfg
        self.fm_channels = fm_channels
        self.fm_count = fm_count
        self.upload_ranges = upload_ranges

    @property
    def special_count(self):
        return len(BANDS_WIDE) * 2

    @property
    def attr_scanlist_max(self):
        return 0xFF if self.attr_width == 2 else 0x07


# K1 and K5 V3 use the same map.  The 0xB000-0xB1FF area is a mapped
# calibration backup; the RX feature state is at a different physical flash
# address and is intentionally not exposed through this clone driver.
PY32_PROFILE = _Profile(
    "PY32F071 / external flash",
    0xB200,
    1024,
    0x9000,
    0x4000,
    0x8000,
    2,
    1031,
    0xA020,
    0xA028,
    48,
    ((0x0000, 0x886E), (0x9000, 0x90E7), (0xA000, 0xA170)),
)

# Original UV-K5 / DP32G030 map.
LEGACY_PROFILE = _Profile(
    "DP32G030 / EEPROM",
    0x2000,
    200,
    0x0C80,
    0x0F50,
    0x0D60,
    1,
    207,
    0x0E88,
    0x0E40,
    20,
    ((0x0000, 0x1D00),),
)


def xorarr(data):
    table = (22, 108, 20, 230, 46, 145, 13, 64, 33, 53, 213, 64,
             19, 3, 233, 128)
    return bytes(byte ^ table[index % len(table)]
                 for index, byte in enumerate(data))


def _crc16_xmodem(data):
    crc = 0
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            crc <<= 1
            if crc & 0x10000:
                crc = (crc ^ 0x1021) & 0xFFFF
    return crc & 0xFFFF


def _send_command(serport, data):
    packet = data + struct.pack("<H", _crc16_xmodem(data))
    command = struct.pack(">HBB", 0xABCD, len(data), 0)
    command += xorarr(packet) + struct.pack(">H", 0xDCBA)
    try:
        return serport.write(command)
    except Exception as exc:
        raise errors.RadioError("Error writing data to radio") from exc


def _receive_reply(serport):
    header = serport.read(4)
    if len(header) != 4 or header[:2] != b"\xAB\xCD" or header[3] != 0:
        raise errors.RadioError("Bad response header")
    body = serport.read(header[2])
    if len(body) != header[2]:
        raise errors.RadioError("Command body short read")
    footer = serport.read(4)
    if len(footer) != 4 or footer[2:] != b"\xDC\xBA":
        raise errors.RadioError("Bad response footer")
    return xorarr(body)


def _get_string(data, begin, maxlen):
    result = []
    for byte in data[begin:begin + maxlen]:
        if byte < 0x20 or byte > 0x7E:
            break
        result.append(chr(byte))
    return "".join(result)


def _say_hello(serport):
    hello = b"\x14\x05\x04\x00\x6a\x39\x57\x64"
    for _ in range(5):
        _send_command(serport, hello)
        reply = _receive_reply(serport)
        if reply:
            if reply.startswith(b"\x18\x05"):
                raise errors.RadioError("Radio is in programming mode")
            return _get_string(reply, 4, 24)
    raise errors.RadioError("Failed to initialize radio")


def _read_memory(serport, offset, length):
    command = b"\x1b\x05\x08\x00"
    command += struct.pack("<HBB", offset, length, 0)
    command += b"\x6a\x39\x57\x64"
    _send_command(serport, command)
    reply = _receive_reply(serport)
    data = reply[8:]
    if len(data) != length:
        raise errors.RadioError("Memory read length mismatch")
    return data


def _write_memory(serport, offset, data):
    if len(data) == 0 or len(data) % 8:
        raise errors.RadioError("Memory writes must be a multiple of 8 bytes")
    command = b"\x1d\x05"
    command += struct.pack("<BBHBB", len(data) + 8, 0, offset,
                           len(data), 1)
    command += b"\x6a\x39\x57\x64" + data
    _send_command(serport, command)
    reply = _receive_reply(serport)
    if len(reply) < 6 or reply[0] != 0x1E or reply[4:6] != struct.pack(
            "<H", offset):
        raise errors.RadioError("Bad response to memory write")


def _reset_radio(serport):
    _send_command(serport, b"\xDD\x05\x00\x00")


def _download(radio):
    serport = radio.pipe
    serport.timeout = 0.5
    status = chirp_common.Status()
    status.cur = 0
    status.max = radio.PROFILE.image_size
    status.msg = "Downloading RX-only image"
    radio.status_fn(status)
    firmware = _say_hello(serport)
    if firmware:
        radio.FIRMWARE_VERSION = firmware

    image = bytearray(radio.PROFILE.image_size)
    for offset in range(0, radio.PROFILE.image_size, MEM_BLOCK):
        data = _read_memory(serport, offset, min(
            MEM_BLOCK, radio.PROFILE.image_size - offset))
        image[offset:offset + len(data)] = data
        status.cur = offset + len(data)
        radio.status_fn(status)
    return memmap.MemoryMapBytes(bytes(image))


def _rounded_upload_end(end):
    return (end + 7) & ~7


def _upload(radio):
    serport = radio.pipe
    serport.timeout = 0.5
    status = chirp_common.Status()
    status.cur = 0
    status.max = sum(_rounded_upload_end(end) - start
                     for start, end in radio.PROFILE.upload_ranges)
    status.msg = "Uploading RX-only image"
    radio.status_fn(status)
    firmware = _say_hello(serport)
    if firmware:
        radio.FIRMWARE_VERSION = firmware

    done = 0
    for start, end in radio.PROFILE.upload_ranges:
        offset = start
        limit = _rounded_upload_end(end)
        while offset < limit:
            length = min(MEM_BLOCK, limit - offset)
            if length % 8:
                length -= length % 8
            data = bytes(radio.get_mmap()[offset:offset + length])
            _write_memory(serport, offset, data)
            offset += length
            done += length
            status.cur = done
            radio.status_fn(status)
    status.msg = "Uploaded RX-only image"
    radio.status_fn(status)
    _reset_radio(serport)


def _u16(data, offset):
    return struct.unpack_from("<H", data, offset)[0]


def _put_u16(data, offset, value):
    struct.pack_into("<H", data, offset, value & 0xFFFF)


class _WRXJPBase(chirp_common.CloneModeRadio):
    BAUD_RATE = 38400
    NEEDS_COMPAT_SERIAL = False
    FIRMWARE_VERSION = ""
    PROFILE = None

    @classmethod
    def get_prompts(cls):
        prompts = chirp_common.RadioPrompts()
        prompts.experimental = (
            "wrx-jp RX-only driver. Keep a complete download as backup before "
            "uploading. This driver never enables transmission."
        )
        prompts.pre_download = (
            "Turn the radio on, connect the programming cable, and keep the "
            "cable firmly inserted. Download and save the image first."
        )
        prompts.pre_upload = (
            "Upload only an image made for this exact hardware profile. A "
            "wrong profile can make the radio unusable."
        )
        return prompts

    def _special_names(self):
        result = []
        for index, (low, high) in enumerate(BANDS_WIDE):
            label = "F%d(%g-%gM)" % (index + 1, low, high)
            result.extend((label + "A", label + "B"))
        return result

    def _find_band(self, frequency):
        mhz = frequency / 1000000.0
        for index, (low, high) in enumerate(BANDS_WIDE):
            if low <= mhz <= high:
                return index
        return None

    def _resolve_memory(self, number):
        if isinstance(number, str):
            try:
                return True, self._special_names().index(number)
            except ValueError as exc:
                raise errors.RadioError("Unknown special channel") from exc
        if number < 1 or number > self.PROFILE.memory_channels + self.PROFILE.special_count:
            raise errors.RadioError("Channel number out of range")
        if number <= self.PROFILE.memory_channels:
            return False, number - 1
        return True, number - self.PROFILE.memory_channels - 1

    def _channel_offset(self, special, index):
        if special:
            return self.PROFILE.special_base + index * 16
        return index * 16

    def _attribute_offset(self, special, index):
        attr_index = (self.PROFILE.memory_channels + index // 2
                      if special else index)
        if attr_index >= self.PROFILE.attr_limit:
            raise errors.RadioError("Channel attribute out of range")
        return self.PROFILE.attr_base + attr_index * self.PROFILE.attr_width

    def _name_offset(self, index):
        return self.PROFILE.name_base + index * 16

    def _get_scanlists(self, special, index):
        offset = self._attribute_offset(special, index)
        raw = bytes(self._mmap[offset:offset + self.PROFILE.attr_width])
        if self.PROFILE.attr_width == 2:
            return _u16(raw, 0) >> 8
        return raw[0] >> 5

    def _set_scanlists(self, special, index, value):
        offset = self._attribute_offset(special, index)
        raw = bytearray(self._mmap[offset:offset + self.PROFILE.attr_width])
        value = max(0, min(self.PROFILE.attr_scanlist_max, int(value)))
        if self.PROFILE.attr_width == 2:
            _put_u16(raw, 0, (int.from_bytes(raw, "little") & 0x00FF) |
                     (value << 8))
        else:
            raw[0] = (raw[0] & 0x1F) | (value << 5)
        self._mmap[offset:offset + self.PROFILE.attr_width] = bytes(raw)

    def _set_band(self, special, index, band):
        offset = self._attribute_offset(special, index)
        raw = bytearray(self._mmap[offset:offset + self.PROFILE.attr_width])
        if self.PROFILE.attr_width == 2:
            value = int.from_bytes(raw, "little")
            _put_u16(raw, 0, (value & ~0x07) | (band & 0x07))
        else:
            raw[0] = (raw[0] & ~0x07) | (band & 0x07)
        self._mmap[offset:offset + self.PROFILE.attr_width] = bytes(raw)

    def _extra_group(self, special, index):
        extra = RadioSettingGroup("extra", "RX-only")
        current = self._get_scanlists(special, index)
        value = RadioSettingValueInteger(
            0, self.PROFILE.attr_scanlist_max, current)
        setting = RadioSetting("scanlists", "RX scan-list mask", value)
        setting.set_doc(
            "RX-only scan-list mask. K1/K5 V3 uses 8 bits; legacy UV-K5 "
            "uses the original 3 scan lists.")
        extra.append(setting)
        return extra

    def _decode_tone(self, memory, raw):
        flag = raw[10] & 0x0F
        code = raw[8]
        if flag == 1 and code < len(CTCSS_TONES):
            rx = ("Tone", CTCSS_TONES[code], "N")
        elif flag in (2, 3) and code < len(DTCS_CODES):
            rx = ("DTCS", DTCS_CODES[code], "R" if flag == 3 else "N")
        else:
            rx = ("", None, "N")
        chirp_common.split_tone_decode(memory, ("", None, "N"), rx)

    def _encode_tone(self, memory, raw):
        flag = 0
        code = 0
        mode = getattr(memory, "tmode", "")
        if mode in ("Tone", "TSQL"):
            tone = getattr(memory, "ctone", None)
            if tone is None:
                tone = getattr(memory, "rtone", None)
            if tone in CTCSS_TONES:
                code = CTCSS_TONES.index(tone)
                flag = 1
        elif mode == "DTCS":
            tone = getattr(memory, "dtcs", None)
            if tone in DTCS_CODES:
                code = DTCS_CODES.index(tone)
                polarity = getattr(memory, "rx_dtcs_polarity", "N")
                flag = 3 if polarity == "R" else 2
        # Keep the upper nibble free of TX tone configuration.
        raw[8] = code
        raw[9] = 0
        raw[10] = (raw[10] & 0xF0) | flag

    def _get_mode(self, raw):
        mode_index = ((raw[11] >> 4) & 0x0F) * 2 + ((raw[12] >> 1) & 1)
        modes = ("FM", "NFM", "AM", "NAM", "USB", "USB")
        return modes[mode_index] if mode_index < len(modes) else "FM"

    def _set_mode(self, raw, mode):
        modes = {"FM": 0, "NFM": 1, "AM": 2, "NAM": 3, "USB": 5}
        mode_index = modes.get(mode, 0)
        raw[11] = (raw[11] & 0x0F) | ((mode_index // 2) << 4)
        raw[12] = (raw[12] & 0xFD) | ((mode_index & 1) << 1)

    def get_features(self):
        features = chirp_common.RadioFeatures()
        features.has_bank = False
        features.has_settings = True
        features.has_comment = False
        features.has_rx_dtcs = True
        features.has_ctone = True
        features.valid_name_length = 10
        features.valid_special_chans = self._special_names()
        features.valid_bands = [
            (int(low * 1000000), int(high * 1000000))
            for low, high in BANDS_WIDE
        ]
        features.valid_duplexes = [""]
        features.valid_modes = ["FM", "NFM", "AM", "NAM", "USB"]
        features.valid_tuning_steps = sorted(STEPS)
        features.valid_tmodes = ["", "TSQL", "DTCS"]
        features.valid_cross_modes = []
        features.valid_characters = chirp_common.CHARSET_ASCII
        features.valid_skips = [""]
        features.memory_bounds = (1, self.PROFILE.memory_channels)
        features.valid_power_levels = []
        return features

    def sync_in(self):
        self._mmap = _download(self)

    def sync_out(self):
        _upload(self)

    def get_raw_memory(self, number):
        special, index = self._resolve_memory(number)
        offset = self._channel_offset(special, index)
        return repr(bytes(self._mmap[offset:offset + 16]))

    def get_memory(self, number):
        special, index = self._resolve_memory(number)
        memory = chirp_common.Memory()
        memory.number = (self.PROFILE.memory_channels + index + 1
                         if special else index + 1)
        if special:
            memory.extd_number = self._special_names()[index]
            memory.name = memory.extd_number
            memory.immutable = ["name", "scanlists"]
        else:
            raw_name = bytes(self._mmap[self._name_offset(index):
                                        self._name_offset(index) + 16])
            memory.name = raw_name.split(b"\x00", 1)[0].split(
                b"\xFF", 1)[0].decode("ascii", errors="ignore").rstrip()

        offset = self._channel_offset(special, index)
        raw = bytes(self._mmap[offset:offset + 16])
        frequency = struct.unpack_from("<I", raw, 0)[0]
        memory.offset = 0
        memory.duplex = ""
        memory.mode = self._get_mode(raw)
        memory.tuning_step = (STEPS[raw[14]] if raw[14] < len(STEPS)
                              else 12.5)
        self._decode_tone(memory, raw)
        memory.extra = self._extra_group(special, index)
        memory.empty = frequency in (0, 0xFFFFFFFF)
        memory.freq = 0 if memory.empty else frequency * 10
        if memory.empty:
            memory.name = "" if not special else memory.name
        return memory

    def _scanlist_value(self, memory, current):
        try:
            for setting in memory.extra:
                if setting.get_name() == "scanlists":
                    return int(setting.value)
        except (AttributeError, TypeError, ValueError):
            pass
        return current

    def set_memory(self, memory):
        special, index = self._resolve_memory(
            memory.extd_number if getattr(memory, "extd_number", None)
            else memory.number)
        offset = self._channel_offset(special, index)
        raw = bytearray(self._mmap[offset:offset + 16])
        if memory.empty:
            raw[:] = b"\xFF" * 16
            self._mmap[offset:offset + 16] = bytes(raw)
            if not special:
                self._mmap[self._name_offset(index):
                           self._name_offset(index) + 16] = b"\x00" * 16
            return memory

        band = self._find_band(memory.freq)
        if band is None:
            raise errors.RadioError("Receive frequency is outside wrx-jp bands")
        struct.pack_into("<I", raw, 0, int(memory.freq // 10))
        # RX-only: never retain a duplex or a transmit tone.
        struct.pack_into("<I", raw, 4, 0)
        raw[11] &= 0xF0
        self._set_mode(raw, getattr(memory, "mode", "FM"))
        self._encode_tone(memory, raw)
        if memory.tuning_step in STEPS:
            raw[14] = STEPS.index(memory.tuning_step)
        else:
            raw[14] = STEPS.index(12.5)
        # The RX-only firmware ignores TX fields, but keeping TXLock set in
        # every channel also protects images shared with non-RX-only tools.
        raw[12] |= 0x40
        self._mmap[offset:offset + 16] = bytes(raw)

        if not special:
            name = str(getattr(memory, "name", "")).encode(
                "ascii", errors="ignore")[:10]
            self._mmap[self._name_offset(index):
                       self._name_offset(index) + 16] = name.ljust(16, b"\x00")

        self._set_band(special, index, band)
        self._set_scanlists(special, index,
                            self._scanlist_value(memory,
                                                 self._get_scanlists(special,
                                                                     index)))
        return memory

    def get_settings(self):
        group = RadioSettingGroup("fm", "FM放送受信")
        cfg = bytes(self._mmap[self.PROFILE.fm_cfg:
                               self.PROFILE.fm_cfg + 4])
        current = _u16(cfg, 0)
        if not FM_MIN <= current <= FM_MAX:
            current = FM_MIN
        setting = RadioSetting(
            "fm_current", "現在周波数 (0.1 MHz)",
            RadioSettingValueInteger(FM_MIN, FM_MAX, current))
        group.append(setting)
        for channel in range(self.PROFILE.fm_count):
            value = _u16(self._mmap, self.PROFILE.fm_channels + channel * 2)
            if value == 0xFFFF or not FM_MIN <= value <= FM_MAX:
                value = 0
            group.append(RadioSetting(
                "fm_%02d" % (channel + 1),
                "FM %02d (0=空き, 0.1 MHz)" % (channel + 1),
                RadioSettingValueInteger(0, FM_MAX, value)))
        return RadioSettings(group)

    def set_settings(self, settings):
        for element in settings:
            if not isinstance(element, RadioSetting):
                self.set_settings(element)
                continue
            try:
                value = int(element.value)
            except (TypeError, ValueError, InvalidValueError) as exc:
                raise errors.RadioError("Invalid FM setting") from exc
            if element.get_name() == "fm_current":
                if not FM_MIN <= value <= FM_MAX:
                    raise errors.RadioError("FM frequency must be 76.0-95.0 MHz")
                _put_u16(self._mmap, self.PROFILE.fm_cfg, value)
                cfg = bytearray(self._mmap[self.PROFILE.fm_cfg:
                                           self.PROFILE.fm_cfg + 4])
                cfg[3] = (cfg[3] & 0xF9) | 0x02  # hardware band 76-108 MHz
                self._mmap[self.PROFILE.fm_cfg:self.PROFILE.fm_cfg + 4] = bytes(cfg)
            elif element.get_name().startswith("fm_"):
                channel = int(element.get_name()[3:]) - 1
                if not 0 <= channel < self.PROFILE.fm_count:
                    raise errors.RadioError("Invalid FM channel")
                if value != 0 and not FM_MIN <= value <= FM_MAX:
                    raise errors.RadioError("FM channel must be 76.0-95.0 MHz")
                _put_u16(self._mmap, self.PROFILE.fm_channels + channel * 2,
                         0xFFFF if value == 0 else value)


@directory.register
class WRXJPUVK1K5V3(_WRXJPBase):
    """UV-K1 and UV-K5 V3 (same PY32F071 profile)."""

    VENDOR = "Quansheng"
    MODEL = "UV-K1 / UV-K5 V3 (wrx-jp RX-only)"
    PROFILE = PY32_PROFILE


@directory.register
class WRXJPUVK5(_WRXJPBase):
    """Original UV-K5 / DP32G030 profile."""

    VENDOR = "Quansheng"
    MODEL = "UV-K5 (wrx-jp RX-only)"
    PROFILE = LEGACY_PROFILE
