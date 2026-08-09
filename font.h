/* Copyright 2023 Dual Tachyon
 * https://github.com/DualTachyon
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 *     Unless required by applicable law or agreed to in writing, software
 *     distributed under the License is distributed on an "AS IS" BASIS,
 *     WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 *     See the License for the specific language governing permissions and
 *     limitations under the License.
 */

#ifndef FONT_H
#define FONT_H

#include <stdint.h>


#define FONT_CODE_MAX 0xDF

/* Large glyphs occupy two 8-row OLED pages.  The editor and the renderer
 * use the same display-coordinate contract: rows 0-1 are top padding, rows
 * 2-11 are the normal glyph area, and rows 12-15 are bottom padding. */
#define FONT_BIG_CELL_ROWS 16u
#define FONT_BIG_TOP_PADDING 2u
#define FONT_BIG_BOTTOM_PADDING 4u
#define FONT_JP_EXTRA_LARGE_WIDTH 10u
#define FONT_JP_EXTRA_LARGE_PAGES 2u
#define FONT_JP_EXTRA_LARGE_BYTES (FONT_JP_EXTRA_LARGE_WIDTH * FONT_JP_EXTRA_LARGE_PAGES)
#define FONT_JP_EXTRA_LARGE_GLYPHS 4u

extern const uint8_t gFontBig[191][16 - 2];
extern const uint8_t gFontBigDigits[11][26 - 6];
extern const uint8_t gFontJapaneseExtraLargeCodes[FONT_JP_EXTRA_LARGE_GLYPHS];
extern const uint8_t gFontJapaneseExtraLarge[FONT_JP_EXTRA_LARGE_GLYPHS][FONT_JP_EXTRA_LARGE_BYTES];
extern const uint8_t gFont3x5[96][3];
extern const uint8_t gFontSmall[95 - 1][6];
extern const uint8_t gFontSmallJapanese[FONT_CODE_MAX - 0x7F + 1][6];
#ifdef ENABLE_SMALL_BOLD
    extern const uint8_t gFontSmallBold[95 - 1][6];
#endif

#endif

