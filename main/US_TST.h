#ifndef US_TST2_H
#define US_TST2_H

#include <stdint.h>

#include "driver/gpio.h"
#include "soc/gpio_reg.h"

/* ---- Pin configuration ---- */
#define GPIO_BURST_DRIVE   GPIO_NUM_9   /* RMT ch A: burst of pulses @ ~1.818 MHz */
#define GPIO_HIZ_DRIVE     GPIO_NUM_10  /* RMT ch B: gate/envelope, low during burst */

/* GPIO STATES
 */
#define STATE_HI_Z  1
#define STATE_LO_Z  0

#define GPIO_HIZ_DRIVE_BITMASK     (1UL << GPIO_HIZ_DRIVE)

/* ---- Burst / RMT configuration ---- */
#define PULSE_COUNT_PER_BURST   8     /* number of full square-wave cycles per burst */
#define PULSE_COUNT_MAX        32     /* headroom: raise PULSE_COUNT_PER_BURST up to this
                                       * with no other change. One ESP32-S3 RMT memory
                                       * block is 48 symbols, so a 32-pulse burst still
                                       * fits entirely in hardware memory (no refill ISR). */

/* RMT tick resolution. 80 MHz APB / 22 = 3,636,364 Hz.
 * With 1 tick high + 1 tick low per cycle, this yields ~1.818182 MHz
 * (+1.01% vs. the 1.8 MHz target -- closest achievable with an integer
 * APB clock divider; confirmed acceptable for this application). */
#define RMT_RESOLUTION_HZ       3636364U
#define RMT_TICKS_PER_CYCLE     2U

/* Symbols of channel memory to reserve per channel. 48 = exactly one S3 block;
 * holds PULSE_COUNT_MAX symbols plus the driver's end-of-transmission marker.
 * Raising this to 64 would force a 2-block allocation per channel, which for two
 * channels consumes all four TX blocks in the group. */
#define RMT_MEM_BLOCK_SYMBOLS   48

/* An RMT symbol carries two 15-bit duration fields, so one symbol spans at most
 * 2 * 32767 ticks. Any longer steady level is emitted as a run of symbols. */
#define RMT_SYMBOL_MAX_TICKS    65534U
#define TICKS_TO_SYMBOLS(t)     (((t) + RMT_SYMBOL_MAX_TICKS - 1U) / RMT_SYMBOL_MAX_TICKS)

/* Convenience: express a duration in microseconds instead of RMT ticks. */
#define TICKS_FROM_US(us)       ((uint32_t)(((uint64_t)(us) * RMT_RESOLUTION_HZ) / 1000000U))

/* ---- Post-burst hold ----
 * After the last pulse the burst line can either drop straight to 0 (set
 * BURST_HOLD_TICKS to 0 -- the original behaviour) or be parked at
 * BURST_HOLD_LEVEL for BURST_HOLD_TICKS before returning to the resting level.
 * The hold is emitted as extra symbols at the tail of the burst waveform, and
 * the Hi-Z gate is held in the Lo-Z state for its whole duration (a level the
 * driver is not actually driving would be pointless).
 * Ticks must be 0 or >= 2 (a duration field of 0 is the RMT end-of-transmission
 * marker, so each emitted half must be non-zero).
 * e.g. TICKS_FROM_US(50) for a 50 us hold. */
#define BURST_HOLD_LEVEL        1     /* level parked on GPIO_BURST_DRIVE */
#define BURST_HOLD_TICKS        4U    /* 0 = no hold; the line drops low at once */

/* ---- Hi-Z envelope timing ----
 * The gate is driven low for the whole burst and any post-burst hold, plus
 * optional guard bands before and after. A non-zero lead also inserts a matching
 * idle symbol at the head of the burst waveform, so the two channels stay
 * tick-aligned. Same 0-or->=2 rule as above. */
#define HIZ_LEAD_TICKS          0U    /* ticks the gate leads the first pulse */
#define HIZ_TAIL_TICKS          0U    /* ticks the gate lags the end of the hold */

#define BURST_TICKS     (PULSE_COUNT_PER_BURST * RMT_TICKS_PER_CYCLE)
#define HIZ_LOW_TICKS   (HIZ_LEAD_TICKS + BURST_TICKS + BURST_HOLD_TICKS + HIZ_TAIL_TICKS)

/* Symbol budget per channel, checked against RMT_MEM_BLOCK_SYMBOLS in US_TST.c. */
#define HIZ_LEAD_SYMBOLS    TICKS_TO_SYMBOLS(HIZ_LEAD_TICKS)
#define BURST_HOLD_SYMBOLS  TICKS_TO_SYMBOLS(BURST_HOLD_TICKS)
#define HIZ_LOW_SYMBOLS     TICKS_TO_SYMBOLS(HIZ_LOW_TICKS)

/* Fault timeout for rmt_tx_wait_all_done(): the waveform's own length (ticks/ms
 * = RMT_RESOLUTION_HZ/1000) plus 10 ms of slack. */
#define BURST_WAIT_TIMEOUT_MS \
    ((int)(HIZ_LOW_TICKS / (RMT_RESOLUTION_HZ / 1000U)) + 10)

/* ---- Function prototypes ---- */
void rmt_burst_init(void);
void rmt_burst_task(void *arg);

#endif /* US_TST2_H */
