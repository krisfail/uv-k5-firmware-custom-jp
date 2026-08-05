#include "rx_feature_state.h"

#include <string.h>

#include "app/chFrScanner.h"
#ifdef ENABLE_FMRADIO
    #include "app/fm.h"
#endif
#include "driver/bk4819.h"
#include "driver/eeprom.h"
#include "driver/system.h"
#include "functions.h"
#include "misc.h"
#include "radio.h"

/* 0x1E00..0x1EBF is the stock squelch calibration table.  The receive-only
 * state therefore uses one otherwise-unused 8-byte page after the stock
 * 0x1F88 settings block.  Per-channel bits use reserved high bits in the
 * receive-only channel records, so no calibration data is shadowed. */
#define RX_FEATURE_EEPROM_BASE       0x1F90u
#define RX_FEATURE_GLOBAL_BYTES      8u
#define RX_FEATURE_GLOBAL_CRC_OFFSET 6u
#define RX_FEATURE_MAGIC0            0x52u
#define RX_FEATURE_MAGIC1            0x58u
#define RX_FEATURE_VERSION           1u

#define RX_FEATURE_FLAG_SINGLE_VFO  (1u << 0)
#define RX_FEATURE_FLAG_AUTO_SQL    (1u << 1)

static uint8_t sChannelBank[MR_CHANNEL_LAST + 1u];
static uint8_t sWidePlus[(MR_CHANNEL_LAST + 1u + 7u) / 8u];
static uint8_t sChannelLoaded[(MR_CHANNEL_LAST + 1u + 7u) / 8u];
static uint8_t sChannelDirty[(MR_CHANNEL_LAST + 1u + 7u) / 8u];
static uint8_t sFlags;
static uint8_t sSelectedBank;
static bool    sReady;
static bool    sGlobalDirty;
static bool    sAutoSquelchRequest;

static uint8_t ClampU8(const int value, const int maximum)
{
    if (value <= 0)
        return 0;
    if (value >= maximum)
        return (uint8_t)maximum;
    return (uint8_t)value;
}

static uint16_t CRC16(const uint8_t *data, const uint16_t length)
{
    uint16_t crc = 0xFFFFu;

    for (uint16_t i = 0; i < length; i++)
    {
        crc ^= (uint16_t)data[i] << 8;
        for (uint8_t bit = 0; bit < 8; bit++)
            crc = (crc & 0x8000u) ? (uint16_t)((crc << 1) ^ 0x1021u) : (uint16_t)(crc << 1);
    }

    return crc;
}

static bool GetBit(const uint8_t *bits, const uint16_t channel)
{
    return (bits[channel >> 3] & (1u << (channel & 7u))) != 0;
}

static void SetBit(uint8_t *bits, const uint16_t channel, const bool value)
{
    const uint8_t mask = 1u << (channel & 7u);
    if (value)
        bits[channel >> 3] |= mask;
    else
        bits[channel >> 3] &= (uint8_t)~mask;
}

static void SetDefaults(void)
{
    memset(sChannelBank, 0, sizeof(sChannelBank));
    /* WIDE+ preserves the existing AM_FIX weak-signal bandwidth behavior. */
    memset(sWidePlus, 0xFF, sizeof(sWidePlus));
    memset(sChannelLoaded, 0, sizeof(sChannelLoaded));
    memset(sChannelDirty, 0, sizeof(sChannelDirty));
    sFlags = 0;
    sSelectedBank = RX_FEATURE_BANK_ALL;
    sAutoSquelchRequest = false;
}

static void LoadChannelMetadata(const uint16_t channel)
{
    if (channel > MR_CHANNEL_LAST || GetBit(sChannelLoaded, channel))
        return;

    uint8_t data[8];
    EEPROM_ReadBuffer((uint16_t)(channel * 16u + 8u), data, sizeof(data));

    sChannelBank[channel] = data[5] >> 4;
    if (sChannelBank[channel] > RX_FEATURE_BANK_MAX)
        sChannelBank[channel] = RX_FEATURE_BANK_ALL;

    /* Bit 7 of the legacy channel mode byte was unused.  A zero bit is the
     * old AM_FIX-compatible WIDE+ default; setting it selects explicit WIDE. */
    sWidePlus[channel >> 3] &= (uint8_t)~(1u << (channel & 7u));
    if (data[4] == 0xFFu || (data[4] & 0x80u) == 0)
        sWidePlus[channel >> 3] |= (uint8_t)(1u << (channel & 7u));

    SetBit(sChannelLoaded, channel, true);
}

static void SaveChannelMetadata(const uint16_t channel)
{
    if (channel > MR_CHANNEL_LAST)
        return;

    LoadChannelMetadata(channel);

    uint8_t data[8];
    EEPROM_ReadBuffer((uint16_t)(channel * 16u + 8u), data, sizeof(data));

    /* Bit 7 of byte 4 and the high nibble of byte 5 are unused by RX-only
     * operation; preserve every stock field while writing only our bits. */
    data[4] = (uint8_t)((data[4] & 0x7Fu) | (GetBit(sWidePlus, channel) ? 0u : 0x80u));
    data[5] = (uint8_t)((data[5] & 0x0Fu) | (sChannelBank[channel] << 4));
    EEPROM_WriteBuffer((uint16_t)(channel * 16u + 8u), data);
    SetBit(sChannelDirty, channel, false);
}

void RX_FEATURE_STATE_Init(void)
{
    uint8_t block[RX_FEATURE_GLOBAL_BYTES];
    EEPROM_ReadBuffer(RX_FEATURE_EEPROM_BASE, block, sizeof(block));
    SetDefaults();

    if (block[0] == RX_FEATURE_MAGIC0 && block[1] == RX_FEATURE_MAGIC1 &&
        block[2] == RX_FEATURE_VERSION &&
        CRC16(block, RX_FEATURE_GLOBAL_CRC_OFFSET) ==
            ((uint16_t)block[RX_FEATURE_GLOBAL_CRC_OFFSET] |
             ((uint16_t)block[RX_FEATURE_GLOBAL_CRC_OFFSET + 1u] << 8)))
    {
        sFlags = block[3] & (RX_FEATURE_FLAG_SINGLE_VFO | RX_FEATURE_FLAG_AUTO_SQL);
        sSelectedBank = block[4] <= RX_FEATURE_BANK_MAX ? block[4] : RX_FEATURE_BANK_ALL;
    }

    sReady = true;
    sGlobalDirty = false;
    sAutoSquelchRequest = (sFlags & RX_FEATURE_FLAG_AUTO_SQL) != 0;
}

void RX_FEATURE_STATE_Save(void)
{
    if (!sReady)
        return;

    if (sGlobalDirty)
    {
        uint8_t block[RX_FEATURE_GLOBAL_BYTES];
        memset(block, 0xFF, sizeof(block));
        block[0] = RX_FEATURE_MAGIC0;
        block[1] = RX_FEATURE_MAGIC1;
        block[2] = RX_FEATURE_VERSION;
        block[3] = sFlags & (RX_FEATURE_FLAG_SINGLE_VFO | RX_FEATURE_FLAG_AUTO_SQL);
        block[4] = sSelectedBank;
        block[5] = 0;

        const uint16_t crc = CRC16(block, RX_FEATURE_GLOBAL_CRC_OFFSET);
        block[RX_FEATURE_GLOBAL_CRC_OFFSET] = (uint8_t)crc;
        block[RX_FEATURE_GLOBAL_CRC_OFFSET + 1u] = (uint8_t)(crc >> 8);
        EEPROM_WriteBuffer(RX_FEATURE_EEPROM_BASE, block);
        sGlobalDirty = false;
    }

    for (uint16_t channel = MR_CHANNEL_FIRST; channel <= MR_CHANNEL_LAST; channel++)
        if (GetBit(sChannelDirty, channel))
            SaveChannelMetadata(channel);
}

void RX_FEATURE_STATE_Reset(void)
{
    SetDefaults();
    sReady = true;
    sGlobalDirty = true;
    RX_FEATURE_STATE_Save();
}

bool RX_FEATURE_STATE_IsSingleVfo(void)
{
    return (sFlags & RX_FEATURE_FLAG_SINGLE_VFO) != 0;
}

void RX_FEATURE_STATE_SetSingleVfo(const bool enabled)
{
    const uint8_t flags = enabled ? (sFlags | RX_FEATURE_FLAG_SINGLE_VFO) :
                                    (sFlags & (uint8_t)~RX_FEATURE_FLAG_SINGLE_VFO);
    if (flags != sFlags)
    {
        sFlags = flags;
        sGlobalDirty = true;
    }
}

uint8_t RX_FEATURE_STATE_GetSelectedBank(void)
{
    return sSelectedBank;
}

void RX_FEATURE_STATE_SetSelectedBank(uint8_t bank)
{
    if (bank > RX_FEATURE_BANK_MAX)
        bank = RX_FEATURE_BANK_ALL;
    if (bank != sSelectedBank)
    {
        sSelectedBank = bank;
        sGlobalDirty = true;
    }
}

uint8_t RX_FEATURE_STATE_GetChannelBank(const uint16_t channel)
{
    if (channel > MR_CHANNEL_LAST)
        return RX_FEATURE_BANK_ALL;
    LoadChannelMetadata(channel);
    return sChannelBank[channel];
}

void RX_FEATURE_STATE_SetChannelBank(const uint16_t channel, uint8_t bank)
{
    if (channel > MR_CHANNEL_LAST)
        return;
    if (bank > RX_FEATURE_BANK_MAX)
        bank = RX_FEATURE_BANK_ALL;
    LoadChannelMetadata(channel);
    if (sChannelBank[channel] != bank)
    {
        sChannelBank[channel] = bank;
        SetBit(sChannelDirty, channel, true);
    }
}

bool RX_FEATURE_STATE_IsBankFilterActive(void)
{
    return sSelectedBank != RX_FEATURE_BANK_ALL;
}

bool RX_FEATURE_STATE_ChannelMatchesBank(const uint16_t channel)
{
    if (!RX_FEATURE_STATE_IsBankFilterActive())
        return true;
    if (channel > MR_CHANNEL_LAST)
        return false;
    LoadChannelMetadata(channel);
    return sChannelBank[channel] == sSelectedBank;
}

bool RX_FEATURE_STATE_GetWidePlus(const uint16_t channel)
{
    if (channel > MR_CHANNEL_LAST)
        return true;
    LoadChannelMetadata(channel);
    return GetBit(sWidePlus, channel);
}

void RX_FEATURE_STATE_SetWidePlus(const uint16_t channel, const bool enabled)
{
    if (channel > MR_CHANNEL_LAST)
        return;
    LoadChannelMetadata(channel);
    if (GetBit(sWidePlus, channel) != enabled)
    {
        SetBit(sWidePlus, channel, enabled);
        SetBit(sChannelDirty, channel, true);
    }
}

bool RX_FEATURE_STATE_IsAutoSquelch(void)
{
    return (sFlags & RX_FEATURE_FLAG_AUTO_SQL) != 0;
}

void RX_FEATURE_STATE_SetAutoSquelch(const bool enabled)
{
    const uint8_t flags = enabled ? (sFlags | RX_FEATURE_FLAG_AUTO_SQL) :
                                    (sFlags & (uint8_t)~RX_FEATURE_FLAG_AUTO_SQL);
    if (flags != sFlags)
    {
        sFlags = flags;
        sGlobalDirty = true;
    }
    if (enabled)
        sAutoSquelchRequest = true;
}

void RX_FEATURE_STATE_RequestAutoSquelch(void)
{
    sAutoSquelchRequest = true;
}

bool RX_FEATURE_STATE_ConsumeAutoSquelchRequest(void)
{
    const bool requested = sAutoSquelchRequest && RX_FEATURE_STATE_IsAutoSquelch();
    sAutoSquelchRequest = false;
    return requested;
}

void RX_FEATURE_STATE_ComputeSquelch(
    const uint8_t rssi, const uint8_t noise, const uint8_t glitch, uint8_t thresholds[6])
{
    thresholds[0] = ClampU8((int)rssi + 8, 255);
    thresholds[1] = ClampU8((int)rssi + 4, 255);
    thresholds[2] = noise > 8 ? (uint8_t)(noise - 8) : 0;
    thresholds[3] = noise > 4 ? (uint8_t)(noise - 4) : 0;
    thresholds[4] = ClampU8((int)glitch + 4, 255);
    thresholds[5] = ClampU8((int)glitch + 8, 255);
}

void RX_FEATURE_STATE_CalibrateSquelch(struct VFO_Info_t *pInfo)
{
    uint32_t rssi = 0;
    uint32_t noise = 0;
    uint32_t glitch = 0;
    uint8_t thresholds[6];

    for (uint8_t i = 0; i < 8; i++)
    {
        SYSTEM_DelayMs(2);
        rssi += BK4819_GetRSSI();
        noise += BK4819_GetExNoiceIndicator();
        glitch += BK4819_GetGlitchIndicator();
    }

    RX_FEATURE_STATE_ComputeSquelch((uint8_t)((rssi / 8u) >> 1),
                                    (uint8_t)(noise / 8u),
                                    (uint8_t)(glitch / 8u), thresholds);

    pInfo->SquelchOpenRSSIThresh = thresholds[0];
    pInfo->SquelchCloseRSSIThresh = thresholds[1];
    pInfo->SquelchOpenNoiseThresh = thresholds[2];
    pInfo->SquelchCloseNoiseThresh = thresholds[3];
    pInfo->SquelchCloseGlitchThresh = thresholds[4];
    pInfo->SquelchOpenGlitchThresh = thresholds[5];

    BK4819_SetupSquelch(
        pInfo->SquelchOpenRSSIThresh, pInfo->SquelchCloseRSSIThresh,
        pInfo->SquelchOpenNoiseThresh, pInfo->SquelchCloseNoiseThresh,
        pInfo->SquelchCloseGlitchThresh, pInfo->SquelchOpenGlitchThresh);
}

#ifdef ENABLE_RX_AGC_GUARD
static uint32_t sAgcFrequency;
static int16_t  sAgcRssi;
static int8_t   sAgcGain;
static uint8_t  sAgcHold;
static bool     sAgcSampleValid;

void RX_FEATURE_STATE_ProcessAgcGuard(void)
{
    if (gRxVfo == NULL || !FUNCTION_IsRx() || gRxVfo->Modulation != MODULATION_FM ||
        gScanStateDir != SCAN_OFF
#ifdef ENABLE_FMRADIO
        || gFmRadioMode
#endif
    )
    {
        /* The radio reconfiguration path owns AGC outside ordinary FM.  Do
         * not re-enable it here: AM_FIX may have deliberately disabled it. */
        sAgcHold = 0;
        sAgcSampleValid = false;
        return;
    }

    const uint32_t frequency = gRxVfo->pRX->Frequency;
    if (frequency != sAgcFrequency)
    {
        sAgcFrequency = frequency;
        sAgcHold = 0;
        sAgcSampleValid = false;
    }

    const int16_t rssi = BK4819_GetRSSI_dBm();
    const int8_t gain = BK4819_GetRxGain_dB();

    if (!sAgcSampleValid)
    {
        sAgcRssi = rssi;
        sAgcGain = gain;
        sAgcSampleValid = true;
        return;
    }

    if (sAgcHold != 0)
    {
        if (--sAgcHold == 0)
            BK4819_SetAGC(true);
        sAgcRssi = rssi;
        sAgcGain = gain;
        return;
    }

    const int16_t rssiDelta = rssi > sAgcRssi ? rssi - sAgcRssi : sAgcRssi - rssi;
    const int8_t gainDelta = gain > sAgcGain ? gain - sAgcGain : sAgcGain - gain;
    if (rssiDelta >= 12 || gainDelta >= 8)
    {
        BK4819_SetAGC(false);
        sAgcHold = 30; /* 300 ms at the 10 ms scheduler cadence. */
    }

    sAgcRssi = rssi;
    sAgcGain = gain;
}
#else
void RX_FEATURE_STATE_ProcessAgcGuard(void)
{
}
#endif
