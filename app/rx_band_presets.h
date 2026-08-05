#ifndef APP_RX_BAND_PRESETS_H
#define APP_RX_BAND_PRESETS_H

#include <stdbool.h>
#include <stdint.h>

#include "driver/keyboard.h"

enum {
    RX_BAND_PRESET_COUNT = 8,
};

typedef struct {
    const char *name;
    uint32_t lower;
    uint32_t upper;
    uint16_t step;
    uint8_t modulation;
    uint8_t bandwidth;
} RX_BandPreset_t;

extern const RX_BandPreset_t gRxBandPresets[RX_BAND_PRESET_COUNT];

void RX_BAND_PRESETS_Open(void);
void RX_BAND_PRESETS_Reset(void);
bool RX_BAND_PRESETS_IsOpen(void);
bool RX_BAND_PRESETS_IsApplied(void);
bool RX_BAND_PRESETS_HandleKey(KEY_Code_t key, bool pressed, bool held);
void RX_BAND_PRESETS_Draw(void);

#endif
