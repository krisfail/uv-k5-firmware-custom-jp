#include "app/rx_band_presets.h"

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "app/action.h"
#include "app/app.h"
#include "app/chFrScanner.h"
#include "app/rx_feature_state.h"
#include "audio.h"
#include "driver/bk4819.h"
#include "external/printf/printf.h"
#include "frequencies.h"
#include "misc.h"
#include "radio.h"
#include "settings.h"
#include "ui/helper.h"
#include "ui/ui.h"

const RX_BandPreset_t gRxBandPresets[RX_BAND_PRESET_COUNT] = {
    {"AIR VHF",   11800000u, 13700000u,  2500u, MODULATION_AM, BANDWIDTH_NARROW},
    {"AIR UHF",   22500000u, 40000000u, 10000u, MODULATION_AM, BANDWIDTH_NARROW},
    {"TOKUSHO",   42205000u, 42230000u,  1250u, MODULATION_FM, BANDWIDTH_NARROW},
    {"FIRE",      46635000u, 46655000u,  1250u, MODULATION_FM, BANDWIDTH_NARROW},
    {"140 HAM",   14400000u, 14600000u,  2000u, MODULATION_FM, BANDWIDTH_WIDE},
    {"430 HAM",   43000000u, 44000000u,  2000u, MODULATION_FM, BANDWIDTH_WIDE},
    {"MAR SHIP",  15602500u, 15742500u,  2500u, MODULATION_FM, BANDWIDTH_WIDE},
    {"MAR SHORE", 16062500u, 16202500u,  2500u, MODULATION_FM, BANDWIDTH_WIDE},
};

static bool   sOpen;
static bool   sApplied;
static uint8_t sSelection;
static uint8_t sAppliedPreset;

static bool RX_BAND_PRESETS_IsValid(const RX_BandPreset_t *preset)
{
    if (preset == NULL || preset->lower >= preset->upper || preset->step == 0)
        return false;

    if (RX_freq_check(preset->lower) < 0 || RX_freq_check(preset->upper) < 0)
        return false;

    return ((preset->upper - preset->lower) % preset->step) == 0;
}

static void RX_BAND_PRESETS_Beep(const bool error)
{
    gBeepToPlay = error ? BEEP_500HZ_60MS_DOUBLE_BEEP_OPTIONAL : BEEP_1KHZ_60MS_OPTIONAL;
}

static void RX_BAND_PRESETS_Reject(const char *message)
{
    RX_BAND_PRESETS_Beep(true);
    UI_DisplayUnavailable(message);
    /* The popup is already on the LCD; do not immediately replace it with
     * the normal main-screen redraw requested by the rejected action. */
    gUpdateDisplay = false;
}

static const char *RX_BAND_PRESETS_OpenError(void)
{
    if (!RX_FEATURE_STATE_IsEnabled())
        return "RXExt OFF";
    if (!IS_FREQ_CHANNEL(gTxVfo->CHANNEL_SAVE))
        return "VFO ONLY";
    if (gScanStateDir != SCAN_OFF || gScanRangeStart != 0)
        return "SCAN ACTIVE";
    if (gTxVfo->FrequencyReverse)
        return "REV ON";
    if (gEeprom.DUAL_WATCH != DUAL_WATCH_OFF)
        return "DUAL RX ON";
    if (gEeprom.CROSS_BAND_RX_TX != CROSS_BAND_OFF)
        return "CROSS ON";
    return NULL;
}

static void RX_BAND_PRESETS_Close(void)
{
    sOpen = false;
    gUpdateDisplay = true;
}

static void RX_BAND_PRESETS_Apply(const bool startScan)
{
    const RX_BandPreset_t *preset = &gRxBandPresets[sSelection];

    if (!RX_FEATURE_STATE_IsEnabled() ||
        gEeprom.DUAL_WATCH != DUAL_WATCH_OFF ||
        gEeprom.CROSS_BAND_RX_TX != CROSS_BAND_OFF ||
        !RX_BAND_PRESETS_IsValid(preset))
    {
        RX_BAND_PRESETS_Close();
        RX_BAND_PRESETS_Reject(!RX_FEATURE_STATE_IsEnabled() ? "RXExt OFF" :
            gEeprom.DUAL_WATCH != DUAL_WATCH_OFF ? "DUAL RX ON" :
            gEeprom.CROSS_BAND_RX_TX != CROSS_BAND_OFF ? "CROSS ON" : "PRESET ERROR");
        return;
    }

    RADIO_SelectVfos();

    // This is deliberately runtime-only. Do not set any gRequestSave* flag.
    gTxVfo->freq_config_RX.Frequency = preset->lower;
    gTxVfo->freq_config_TX.Frequency = preset->lower;
    gTxVfo->Band                     = FREQUENCY_GetBand(preset->lower);
    gTxVfo->Modulation               = (ModulationMode_t)preset->modulation;
    /* A preset is a complete receive profile.  Do not carry a per-channel
     * WIDE+ choice from the previous memory channel into a VFO preset. */
    gTxVfo->WIDE_PLUS                = false;
    gTxVfo->STEP_SETTING              = STEP_12_5kHz;
    for (uint8_t i = 0; i < STEP_N_ELEM; i++) {
        if (gStepFrequencyTable[i] == preset->step) {
            gTxVfo->STEP_SETTING = (STEP_Setting_t)i;
            break;
        }
    }
    gTxVfo->StepFrequency            = preset->step;
    gTxVfo->CHANNEL_BANDWIDTH        = preset->bandwidth;

    gScanRangeStart = preset->lower;
    gScanRangeStop  = preset->upper;
    sApplied         = true;
    sAppliedPreset   = sSelection;

    RADIO_ConfigureSquelchAndOutputPower(gRxVfo);
    RADIO_SetModulation(gRxVfo->Modulation);
    RADIO_SetupRegisters(true);

    RX_BAND_PRESETS_Beep(false);
    RX_BAND_PRESETS_Close();

    if (startScan)
        ACTION_Scan(false);
}

void RX_BAND_PRESETS_Open(void)
{
    const char *error = RX_BAND_PRESETS_OpenError();
    if (error != NULL)
    {
        RX_BAND_PRESETS_Reject(error);
        return;
    }

    sSelection = 0;
    sOpen      = true;
    RX_BAND_PRESETS_Beep(false);
    gUpdateDisplay = true;
}

void RX_BAND_PRESETS_Reset(void)
{
    sOpen     = false;
    sApplied  = false;
    gUpdateDisplay = true;
}

bool RX_BAND_PRESETS_IsOpen(void)
{
    return sOpen;
}

bool RX_BAND_PRESETS_IsApplied(void)
{
    if (!RX_FEATURE_STATE_IsEnabled() ||
        !sApplied || gScanRangeStart == 0 || sAppliedPreset >= RX_BAND_PRESET_COUNT)
        return false;

    return gScanRangeStart == gRxBandPresets[sAppliedPreset].lower &&
           gScanRangeStop  == gRxBandPresets[sAppliedPreset].upper;
}

bool RX_BAND_PRESETS_HandleKey(const KEY_Code_t key, const bool pressed, const bool held)
{
    if (!sOpen)
        return false;

    switch (key) {
        case KEY_UP:
            if (pressed) {
                sSelection = (sSelection + 1u) % RX_BAND_PRESET_COUNT;
                RX_BAND_PRESETS_Beep(false);
                gUpdateDisplay = true;
            }
            return true;

        case KEY_DOWN:
            if (pressed) {
                sSelection = (sSelection == 0) ? RX_BAND_PRESET_COUNT - 1u : sSelection - 1u;
                RX_BAND_PRESETS_Beep(false);
                gUpdateDisplay = true;
            }
            return true;

        case KEY_MENU:
            if (!pressed && !held)
                RX_BAND_PRESETS_Apply(false);
            return true;

        case KEY_STAR:
            if (!pressed && !held)
                RX_BAND_PRESETS_Apply(true);
            return true;

        case KEY_EXIT:
            if (!pressed && !held) {
                RX_BAND_PRESETS_Beep(false);
                RX_BAND_PRESETS_Close();
            }
            return true;

        default:
            return true;
    }
}

void RX_BAND_PRESETS_Draw(void)
{
    const RX_BandPreset_t *preset = &gRxBandPresets[sSelection];
    char range[22];
    char details[22];

    UI_DisplayClear();
    UI_PrintStringSmallBold("RX BAND PRESET", 0, 0, 0);
    sprintf(range, "%3u.%05u-%3u.%05u",
            preset->lower / 100000u, preset->lower % 100000u,
            preset->upper / 100000u, preset->upper % 100000u);
    UI_PrintStringSmallBold(preset->name, 0, 0, 1);
    UI_PrintStringSmallNormal(range, 0, 0, 2);
    sprintf(details, "%s %s STEP %u.%u",
            preset->modulation == MODULATION_AM ? "AM" : "FM",
            preset->bandwidth == BANDWIDTH_NARROW ? "NARROW" : "WIDE",
            preset->step / 100u, (preset->step / 10u) % 10u);
    UI_PrintStringSmallNormal(details, 0, 0, 3);
    sprintf(details, "%u/8  UP/DOWN SELECT", sSelection + 1u);
    UI_PrintStringSmallNormal(details, 0, 0, 5);
    UI_PrintStringSmallNormal("M APPLY  * SCAN", 0, 0, 6);
    UI_PrintStringSmallNormal("EXIT CANCEL", 0, 0, 7);
}
