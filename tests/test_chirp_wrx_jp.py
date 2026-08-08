import importlib.util
import sys
import types
import unittest
from pathlib import Path


def _install_chirp_stub():
    """Allow the pure driver mapping tests to run without CHIRP installed."""
    if "chirp" in sys.modules:
        return

    chirp = types.ModuleType("chirp")
    common = types.ModuleType("chirp.chirp_common")
    directory = types.ModuleType("chirp.directory")
    errors = types.ModuleType("chirp.errors")
    memmap = types.ModuleType("chirp.memmap")
    settings = types.ModuleType("chirp.settings")

    class RadioError(Exception):
        pass

    class CloneModeRadio:
        def status_fn(self, _status):
            pass

        def get_mmap(self):
            return self._mmap

    class RadioFeatures:
        pass

    class RadioPrompts:
        pass

    class Status:
        pass

    class Memory:
        def __init__(self):
            self.extra = []

    class RadioSettingValueInteger:
        def __init__(self, minimum, maximum, value):
            self.minimum = minimum
            self.maximum = maximum
            self.value = value

        def __int__(self):
            return int(self.value)

    class RadioSetting:
        def __init__(self, name, _label, value):
            self._name = name
            self.value = value

        def get_name(self):
            return self._name

        def set_doc(self, _doc):
            pass

    class RadioSettingGroup(list):
        def __init__(self, _name, _label):
            super().__init__()

    class RadioSettings(list):
        def __init__(self, *groups):
            super().__init__(groups)

    class MemoryMapBytes(bytearray):
        pass

    common.CloneModeRadio = CloneModeRadio
    common.RadioFeatures = RadioFeatures
    common.RadioPrompts = RadioPrompts
    common.Status = Status
    common.Memory = Memory
    common.CHARSET_ASCII = "ASCII"
    common.split_tone_decode = lambda *_args: None
    directory.register = lambda cls: cls
    errors.RadioError = RadioError
    memmap.MemoryMapBytes = MemoryMapBytes
    settings.InvalidValueError = ValueError
    settings.RadioSetting = RadioSetting
    settings.RadioSettingGroup = RadioSettingGroup
    settings.RadioSettings = RadioSettings
    settings.RadioSettingValueInteger = RadioSettingValueInteger

    chirp.chirp_common = common
    chirp.directory = directory
    chirp.errors = errors
    chirp.memmap = memmap
    sys.modules.update({
        "chirp": chirp,
        "chirp.chirp_common": common,
        "chirp.directory": directory,
        "chirp.errors": errors,
        "chirp.memmap": memmap,
        "chirp.settings": settings,
    })


_install_chirp_stub()
DRIVER_PATH = Path(__file__).parents[1] / "tools" / "chirp" / "wrx_jp.py"
SPEC = importlib.util.spec_from_file_location("wrx_jp", DRIVER_PATH)
DRIVER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DRIVER)


class TestWRXJPDriver(unittest.TestCase):
    def test_profiles_keep_k1_k5v3_separate_from_legacy_k5(self):
        py32 = DRIVER.WRXJPUVK1K5V3()
        legacy = DRIVER.WRXJPUVK5()

        self.assertEqual(py32.PROFILE.memory_channels, 1024)
        self.assertEqual(py32.PROFILE.name_base, 0x4000)
        self.assertEqual(py32.PROFILE.attr_width, 2)
        self.assertEqual(py32._channel_offset(False, 1023), 0x3FF0)
        self.assertEqual(py32._name_offset(1023), 0x7FF0)
        self.assertEqual(py32._channel_offset(True, 0), 0x9000)

        self.assertEqual(legacy.PROFILE.memory_channels, 200)
        self.assertEqual(legacy.PROFILE.name_base, 0x0F50)
        self.assertEqual(legacy.PROFILE.attr_width, 1)
        self.assertEqual(legacy._channel_offset(True, 13), 0x0D50)

    def test_rx_only_tone_and_mode_encoding(self):
        radio = DRIVER.WRXJPUVK1K5V3()
        raw = bytearray(16)
        memory = types.SimpleNamespace(
            tmode="TSQL", ctone=88.5, rtone=88.5, dtcs=None,
            rx_dtcs_polarity="N")

        radio._encode_tone(memory, raw)
        self.assertEqual(raw[8], DRIVER.CTCSS_TONES.index(88.5))
        self.assertEqual(raw[9], 0)
        self.assertEqual(raw[10] & 0x0F, 1)
        self.assertEqual(raw[10] & 0xF0, 0)

        radio._set_mode(raw, "AM")
        self.assertEqual(radio._get_mode(raw), "AM")
        self.assertEqual(raw[11] & 0x0F, 0)

    def test_set_memory_forces_rx_lock_and_uses_profile_map(self):
        radio = DRIVER.WRXJPUVK1K5V3()
        radio._mmap = bytearray(radio.PROFILE.image_size)
        memory = types.SimpleNamespace(
            number=1, extd_number=None, empty=False, freq=145500000,
            offset=0, duplex="+", mode="NFM", tmode="", tuning_step=12.5,
            name="呼出", extra=[])

        radio.set_memory(memory)
        raw = radio._mmap[:16]
        self.assertEqual(int.from_bytes(raw[0:4], "little"), 14550000)
        self.assertEqual(int.from_bytes(raw[4:8], "little"), 0)
        self.assertEqual(raw[12] & 0x40, 0x40)
        self.assertEqual(raw[12] & 0x02, 0x02)
        self.assertEqual(radio._mmap[0x4000:0x4006], b"\x00\x00\x00\x00\x00\x00")
        self.assertEqual(radio._mmap[0x8000] & 0x07, 2)

    def test_fm_settings_use_japanese_76_to_95_range(self):
        radio = DRIVER.WRXJPUVK1K5V3()
        radio._mmap = bytearray(radio.PROFILE.image_size)
        DRIVER._put_u16(radio._mmap, radio.PROFILE.fm_cfg, 800)
        DRIVER._put_u16(radio._mmap, radio.PROFILE.fm_channels, 950)
        settings = radio.get_settings()
        self.assertEqual(len(settings[0]), 49)
        self.assertEqual(settings[0][0].value.value, 800)
        self.assertEqual(settings[0][1].value.value, 950)
        self.assertEqual(settings[0][48].get_name(), "fm_48")
        self.assertEqual(DRIVER._rounded_upload_end(0x886E), 0x8870)
        self.assertEqual(DRIVER._rounded_upload_end(0x90E7), 0x90E8)


if __name__ == "__main__":
    unittest.main()
