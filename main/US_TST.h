#ifndef US_TST2_H
#define US_TST2_H

#include <stdint.h>

#include "esp_err.h"       /* esp_err_t */
#include "driver/gpio.h"   /* gpio_num_t, GPIO_NUM_*, GPIO_NUM_MAX */

/* ---- The two output signals ----
 * BURST - a series of pulses, primarily at one frequency (~1.818 MHz).
 * GATE  - an enabling signal, an envelope around the burst with options to
 *         extend it at either end.
 *
 * In the usual wiring BURST feeds the data input of a digital line driver and
 * GATE feeds that driver's tri-state control, which acts like a switch in
 * series with the driver output: the gate is asserted for its window, closing
 * the switch and driving the crystal, and rests otherwise, opening the switch and
 * letting the crystal ring on its own instead of being clamped to a logic level.
 * The roles can also be swapped (GATE held at a steady level into the data input
 * while BURST toggles the tri-state control) for a pulsed-impedance mode.
 *
 * Neither signal has a built-in preference for a logic level. Each is described
 * in terms of an *active* level and its complement, the *idle* level, and each
 * signal's polarity is chosen independently by its preset -- see polarity_t. The
 * active level is what the pulses drive to and what the gate holds for its
 * window; the idle level is what the line idles at from channel creation, sits
 * at between pulses, and rests at after the burst. */

/* ---- Pin configuration ----
 * These feed cfg_default; every preset carries its own pair, so a preset can
 * move the signals to different pins. */
#define GPIO_BURST   GPIO_NUM_9    /* RMT ch A: burst of pulses @ ~1.818 MHz */
#define GPIO_GATE    GPIO_NUM_10   /* RMT ch B: gate/envelope, active during the burst */

/* ---- Output levels ----
 * Used for the *_active_level flags in signals_config_t: the logic level a signal
 * is driven to while it is active. The idle level -- what the line sits at from
 * channel creation, between pulses, and after the burst -- is always the
 * complement, so setting the active level sets both.
 *
 * Note GPIO_LOW is 0, so a preset that leaves an active-level flag out gets
 * active low. Every preset spells both flags out for that reason; do the same in
 * any new one. */
typedef enum {
    GPIO_LOW  = 0,
    GPIO_HIGH = 1,
} output_level_t;

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

/* Post-burst hold: after the last pulse both lines can either go straight back
 * to their idle levels (HOLD_TICKS == 0) or be held at a chosen level for
 * HOLD_TICKS first. One duration covers both signals, so they stay tick-aligned;
 * the hold is emitted as extra symbols at the tail of each waveform.
 *
 * Each signal has its own hold level, and both are *absolute* logic levels -- a
 * hold level of GPIO_HIGH means the pin is driven high during the hold no matter
 * what that signal's active level is. They are independent of *_ACTIVE_LEVEL, so
 * changing a polarity leaves the hold exactly where it was written. To keep a
 * signal at its active level through the hold (what the gate does by default),
 * give it the same level as its *_ACTIVE_LEVEL. */
#define BURST_HOLD_LEVEL        GPIO_HIGH  /* burst pin during the hold */
#define GATE_HOLD_LEVEL         GPIO_LOW   /* gate pin during the hold; == GATE_ACTIVE_LEVEL */
#define HOLD_TICKS              4U         /* 0 = no hold; both lines go idle at once */

/* Gate guard bands. The gate is active for the whole burst plus these optional
 * bands before and after it; during the hold in between it sits at
 * GATE_HOLD_LEVEL. A non-zero lead also inserts a matching idle symbol at the
 * head of the burst waveform, so the two channels stay tick-aligned. */
#define GATE_LEAD_TICKS         0U    /* ticks the gate leads the first pulse */
#define GATE_TAIL_TICKS         0U    /* ticks the gate lags the end of the hold */

/* Active level of each signal; see output_level_t. These are the traditional
 * polarities: the pulses drive high, the gate is asserted low. */
#define BURST_ACTIVE_LEVEL      GPIO_HIGH
#define GATE_ACTIVE_LEVEL       GPIO_LOW

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
    const char     *name;               /* shown in the boot log */
    gpio_num_t      burst_gpio;         /* pin carrying the pulse train */
    gpio_num_t      gate_gpio;          /* pin carrying the gate */
    uint32_t        resolution_hz;      /* RMT tick rate; pulse freq = this / RMT_TICKS_PER_CYCLE */
    uint16_t        pulse_count;        /* full square-wave cycles per burst */
    output_level_t  burst_active_level; /* level the pulses drive to */
    output_level_t  gate_active_level;  /* level the gate holds for the lead-in, pulses and tail */
    output_level_t  burst_hold_level;   /* level the burst pin is driven to during the hold */
    output_level_t  gate_hold_level;    /* level the gate pin is driven to during the hold */
    uint32_t        hold_ticks;         /* duration of that hold; 0 = none */
    uint32_t        gate_lead_ticks;    /* gate leads the first pulse by this much */
    uint32_t        gate_tail_ticks;    /* gate lags the end of the hold by this much */
} signals_config_t;

/* The live configuration: a copy of the selected preset, taken by
 * rmt_burst_init(). Exposed so it can be inspected from a debugger; changing it
 * after init has no effect, since the symbol tables and the channels are built
 * from it once. */
extern signals_config_t g_burst_cfg;

/* ---- Fault reporting ----
 * Nothing in this project calls ESP_ERROR_CHECK any more. A rejected preset or a
 * failing driver call used to panic and reboot, which put the reason in a boot
 * loop and left the pins dead with no explanation. Now the first failure is
 * recorded, every task that drives a waveform stops, and a reporting task
 * repeats the reason on the console this often, indefinitely. */
#define FAULT_REPORT_PERIOD_MS  3000U

/* ---- Function prototypes ---- */

/* Returns ESP_OK, or the error that stopped it -- in which case the fault
 * reporting task has already been started and no waveform is being generated.
 * The caller does not need to log anything itself. */
esp_err_t rmt_burst_init(void);

void rmt_burst_task(void *arg);

#endif /* US_TST2_H */
