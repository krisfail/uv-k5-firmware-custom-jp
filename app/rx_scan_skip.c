#include "app/rx_scan_skip.h"
#include "app/rx_feature_state.h"

static uint32_t sSkippedFrequencies[RX_SCAN_SKIP_MAX];
static uint8_t  sSkippedFrequencyCount;

RX_SCAN_SKIP_Result_t RX_SCAN_SKIP_Add(const uint32_t frequency)
{
    if (!RX_FEATURE_STATE_IsEnabled())
        return RX_SCAN_SKIP_FULL;

    for (uint8_t i = 0; i < sSkippedFrequencyCount; ++i) {
        if (sSkippedFrequencies[i] == frequency)
            return RX_SCAN_SKIP_DUPLICATE;
    }

    if (sSkippedFrequencyCount >= RX_SCAN_SKIP_MAX)
        return RX_SCAN_SKIP_FULL;

    sSkippedFrequencies[sSkippedFrequencyCount++] = frequency;
    return RX_SCAN_SKIP_ADDED;
}

bool RX_SCAN_SKIP_Contains(const uint32_t frequency)
{
    if (!RX_FEATURE_STATE_IsEnabled())
        return false;

    for (uint8_t i = 0; i < sSkippedFrequencyCount; ++i) {
        if (sSkippedFrequencies[i] == frequency)
            return true;
    }

    return false;
}

uint8_t RX_SCAN_SKIP_Count(void)
{
    return RX_FEATURE_STATE_IsEnabled() ? sSkippedFrequencyCount : 0;
}
