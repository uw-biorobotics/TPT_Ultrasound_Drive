#ifndef US_TST2_H
#define US_TST2_H

#include <stdint.h>

#include "driver/gpio.h"   /* gpio_num_t, GPIO_NUM_*, GPIO_NUM_MAX */

/* ---- Pin configuration ----
 * These feed cfg_default; every preset carries its own pair, so a preset can
 * move the signals to different pins. */
#define GPIO_BURST_DRIVE   GPIO_NUM_9   /* RMT ch A: burst of pulses @ ~1.818 MHz */
#define GPIO_HIZ_DRIVE     GPIO_NUM_10  /* RMT ch B: gate/envelope, low during burst */

/* GPIO STATES
 */
#define STATE_HI_Z  1
#define STATE_LO_Z  0

/* ---- Hardware limits (not test knobs) ---- */

/* Symbols of channel memory to reserve per channel. 48 = exactly one S3 block.
 * Raising this to 64 would force a 2-block allocation per channel, which for two
 * channels consumes all four TX blocks in the group. */
#define RMT_MEM_BLOCK_SYMBOLS   48

/* One symbol of the block is spent on the driver's end-of-transmission marker,
 * so this is the longest waveform that still fits without a refill ISR. It is
 * the real ceiling on pulse count: one symbol per cycle, minus whatever the
 * lead-in and post-burst hold consume. */
#define BURST_SYMBOLS_MAX       (RMT_MEM_BLOCK_SYMBOLS - 1)

/* An RMT symbol carries two 15-bit duration fields, so one symbol spans at most
 * 2 * 32767 ticks. Any longer steady level is emitted as a run of symbols. */
#define RMT_SYMBOL_MAX_TICKS    65534U

/* Every pulse is 1 tick high + 1 tick low, so the burst frequency is always
 * resolution_hz / 2. */
#define RMT_TICKS_PER_CYCLE     2U

/* ---- Default tunables ----
 * These feed cfg_default, the first preset in US_TST.c. Edit them for a one-off
 * experiment; add a named preset for a set of values worth keeping.
 *
 * RMT tick resolution: 80 MHz APB / 22 = 3,636,364 Hz. With 1 tick high + 1 tick
 * low per cycle, this yields ~1.818182 MHz (+1.01% vs. the 1.8 MHz target --
 * closest achievable with an integer APB clock divider; confirmed acceptable for
 * this application). */
#define N                       22         // can change to closeby values for freq tuning.
// #define RMT_RESOLUTION_HZ       3636364U
#define RMT_RESOLUTION_HZ       80000000U/N    // magic number for RMT output freq.
#define PULSE_COUNT_PER_BURST   8     /* number of full square-wave cycles per burst */

/* Post-burst hold: after the last pulse the burst line can either drop straight
 * to 0 (POST_BURST_HOLD_TICKS == 0) or be parked at POST_BURST_HOLD_LEVEL for
 * POST_BURST_HOLD_TICKS before returning to the resting level. The hold is
 * emitted as extra symbols at the tail of the burst waveform, and the Hi-Z gate
 * stays in the Lo-Z state for its whole duration (a level the driver is not
 * actually driving would be pointless). */
#define POST_BURST_HOLD_LEVEL   1     /* level parked on the burst pin */
#define POST_BURST_HOLD_TICKS   4U    /* 0 = no hold; the line drops low at once */

/* Hi-Z envelope guard bands. The gate is driven low for the whole burst and any
 * post-burst hold, plus these optional bands before and after. A non-zero lead
 * also inserts a matching idle symbol at the head of the burst waveform, so the
 * two channels stay tick-aligned. */
#define HIZ_LEAD_TICKS          0U    /* ticks the gate leads the first pulse */
#define HIZ_TAIL_TICKS          0U    /* ticks the gate lags the end of the hold */

/* Convenience for writing presets: express a duration in microseconds instead of
 * RMT ticks. Takes the rate explicitly so it cannot silently disagree with the
 * resolution_hz of the preset it appears in. */
#define TICKS_FROM_US_AT(us, hz) ((uint32_t)(((uint64_t)(us) * (hz)) / 1000000U))

/* ---- Runtime configuration ----
 * Everything that varies between test runs lives here rather than in #defines,
 * so a set of values can be named, kept as one of the cfg_* presets in US_TST.c,
 * and selected with a single edit to ACTIVE_CONFIG there.
 *
 * Every *_ticks field must be 0 or >= 2: a duration field of 0 is the RMT
 * end-of-transmission marker, so each emitted symbol half must be non-zero.
 * validate_config() enforces this at startup along with the memory-block limit. */
typedef struct {
    const char *name;            /* shown in the boot log */
    gpio_num_t  burst_gpio;      /* pin carrying the pulse train */
    gpio_num_t  hiz_gpio;        /* pin carrying the Hi-Z gate */
    uint32_t    resolution_hz;   /* RMT tick rate; pulse freq = this / RMT_TICKS_PER_CYCLE */
    uint16_t    pulse_count;     /* full square-wave cycles per burst */
    uint8_t     hold_level;      /* level parked on the burst pin after the pulses */
    uint32_t    hold_ticks;      /* duration of that hold; 0 = none */
    uint32_t    hiz_lead_ticks;  /* gate leads the first pulse by this much */
    uint32_t    hiz_tail_ticks;  /* gate lags the end of the hold by this much */
} burst_config_t;

/* The live configuration: a copy of the selected preset, taken by
 * rmt_burst_init(). Exposed so it can be inspected from a debugger; changing it
 * after init has no effect, since the symbol tables and the channels are built
 * from it once. */
extern burst_config_t g_burst_cfg;

/* ---- Function prototypes ---- */
void rmt_burst_init(void);
void rmt_burst_task(void *arg);

#endif /* US_TST2_H */
