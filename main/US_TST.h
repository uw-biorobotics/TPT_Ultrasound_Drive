#ifndef US_TST2_H
#define US_TST2_H

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

/* ---- Hi-Z envelope timing ----
 * The gate is driven low for the whole burst, plus optional guard bands before
 * and after. A non-zero lead also inserts a matching idle symbol at the head of
 * the burst waveform, so the two channels stay tick-aligned.
 * Guard values must be 0 or >= 2 ticks (a duration field of 0 is the RMT
 * end-of-transmission marker, so each emitted half must be non-zero). */
#define HIZ_LEAD_TICKS          0U    /* ticks the gate leads the first pulse */
#define HIZ_TAIL_TICKS          0U    /* ticks the gate lags the last pulse */

#define BURST_TICKS     (PULSE_COUNT_PER_BURST * RMT_TICKS_PER_CYCLE)
#define HIZ_LOW_TICKS   (HIZ_LEAD_TICKS + BURST_TICKS + HIZ_TAIL_TICKS)

/* ---- Function prototypes ---- */
void rmt_burst_init(void);
void rmt_burst_task(void *arg);

#endif /* US_TST2_H */
