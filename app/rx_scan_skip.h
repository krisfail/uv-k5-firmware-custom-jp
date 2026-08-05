#ifndef APP_RX_SCAN_SKIP_H
#define APP_RX_SCAN_SKIP_H

#include <stdbool.h>
#include <stdint.h>

#define RX_SCAN_SKIP_MAX 16U

typedef enum {
    RX_SCAN_SKIP_ADDED,
    RX_SCAN_SKIP_DUPLICATE,
    RX_SCAN_SKIP_FULL,
} RX_SCAN_SKIP_Result_t;

RX_SCAN_SKIP_Result_t RX_SCAN_SKIP_Add(uint32_t frequency);
bool                  RX_SCAN_SKIP_Contains(uint32_t frequency);
uint8_t               RX_SCAN_SKIP_Count(void);

#endif
