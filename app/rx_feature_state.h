#ifndef RX_FEATURE_STATE_H
#define RX_FEATURE_STATE_H

#include <stdbool.h>
#include <stdint.h>

#define RX_FEATURE_BANK_ALL 0u
#define RX_FEATURE_BANK_MAX 8u

void RX_FEATURE_STATE_Init(void);
void RX_FEATURE_STATE_Save(void);
void RX_FEATURE_STATE_Reset(void);

bool    RX_FEATURE_STATE_IsSingleVfo(void);
void    RX_FEATURE_STATE_SetSingleVfo(bool enabled);
uint8_t RX_FEATURE_STATE_GetSelectedBank(void);
void    RX_FEATURE_STATE_SetSelectedBank(uint8_t bank);
uint8_t RX_FEATURE_STATE_GetChannelBank(uint16_t channel);
void    RX_FEATURE_STATE_SetChannelBank(uint16_t channel, uint8_t bank);
bool    RX_FEATURE_STATE_IsBankFilterActive(void);
bool    RX_FEATURE_STATE_ChannelMatchesBank(uint16_t channel);
bool    RX_FEATURE_STATE_GetWidePlus(uint16_t channel);
void    RX_FEATURE_STATE_SetWidePlus(uint16_t channel, bool enabled);

bool RX_FEATURE_STATE_IsAutoSquelch(void);
void RX_FEATURE_STATE_SetAutoSquelch(bool enabled);
void RX_FEATURE_STATE_RequestAutoSquelch(void);
bool RX_FEATURE_STATE_ConsumeAutoSquelchRequest(void);

/* The output order is open RSSI, close RSSI, open noise, close noise,
 * close glitch, open glitch.  This is kept separate from the BK4819 I/O so
 * the threshold policy can be characterized without a radio attached. */
void RX_FEATURE_STATE_ComputeSquelch(
    uint8_t rssi, uint8_t noise, uint8_t glitch, uint8_t thresholds[6]);

struct VFO_Info_t;
void RX_FEATURE_STATE_CalibrateSquelch(struct VFO_Info_t *pInfo);
void RX_FEATURE_STATE_ProcessAgcGuard(void);

#endif
