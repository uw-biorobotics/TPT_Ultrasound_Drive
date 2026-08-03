#!/usr/bin/env python3
"""Build docs/US_TST_Documentation.odt from the prose below.

An .odt is a zip of XML parts, so this needs nothing beyond the standard
library -- no LibreOffice, no odfpy.

    python3 docs/make_doc.py

Figure 1 is taken from docs/figure1.png if it exists, otherwise from
docs/timing_guarded.png as a stand-in.  Drop the real crop in as
docs/figure1.png and re-run; nothing else needs to change.
"""

import os
import struct
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "US_TST_Documentation.odt")

FIGURE_CANDIDATES = ["figure1.png", "timing_guarded.png"]

APB_HZ = 80_000_000          # RMT_CLK_SRC_DEFAULT on the ESP32-S3
TICKS_PER_CYCLE = 2          # 1 tick high + 1 tick low per pulse
TARGET_HZ = 1_800_000        # nominal transducer resonance
ACTIVE_DIV = 22              # what RMT_RESOLUTION_HZ in US_TST.h works out to


# ---------------------------------------------------------------- helpers --
def esc(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace('"', "&quot;"))


def png_size(path):
    """(width, height) in pixels, straight out of the IHDR chunk."""
    with open(path, "rb") as f:
        head = f.read(24)
    if head[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"{path} is not a PNG")
    return struct.unpack(">II", head[16:24])


def p(text, style="Text_20_body"):
    return f'<text:p text:style-name="{style}">{text}</text:p>'


def raw_p(markup, style="Text_20_body"):
    """Paragraph whose content is already XML (for inline spans)."""
    return f'<text:p text:style-name="{style}">{markup}</text:p>'


def h(text, level, style=None):
    style = style or f"Heading_20_{level}"
    return (f'<text:h text:style-name="{style}" text:outline-level="{level}">'
            f'{esc(text)}</text:h>')


def bullet(items):
    out = ['<text:list text:style-name="Bullets">']
    for it in items:
        out.append(f'<text:list-item>{raw_p(it, "List_20_Bullet")}</text:list-item>')
    out.append("</text:list>")
    return "".join(out)


def code(block):
    """Monospace listing; leading blanks preserved with <text:s/>."""
    out = []
    for line in block.strip("\n").split("\n"):
        stripped = line.lstrip(" ")
        pad = len(line) - len(stripped)
        lead = f'<text:s text:c="{pad}"/>' if pad else ""
        body = esc(stripped) if stripped else ""
        out.append(f'<text:p text:style-name="Code">{lead}{body}</text:p>')
    return "".join(out)


def mono(s):
    return f'<text:span text:style-name="Mono">{esc(s)}</text:span>'


def bold(s):
    return f'<text:span text:style-name="Bold">{esc(s)}</text:span>'


def table(name, headers, rows, widths, note=None):
    """widths are relative; rendered against a 17 cm text width."""
    total = sum(widths)
    cols = "".join(
        f'<table:table-column table:style-name="{name}.c{i}"/>'
        for i in range(len(headers)))

    def cell(content, style, para):
        return (f'<table:table-cell table:style-name="{style}" '
                f'office:value-type="string">'
                f'<text:p text:style-name="{para}">{content}</text:p>'
                f"</table:table-cell>")

    body = [f'<table:table table:name="{name}" table:style-name="{name}">', cols]
    body.append("<table:table-header-rows><table:table-row>")
    for hd in headers:
        body.append(cell(esc(hd), "CellHead", "TblHead"))
    body.append("</table:table-row></table:table-header-rows>")
    for r_i, row in enumerate(rows):
        style = "CellA" if r_i % 2 == 0 else "CellB"
        body.append("<table:table-row>")
        for c in row:
            body.append(cell(c, style, "TblCell"))
        body.append("</table:table-row>")
    body.append("</table:table>")
    if note:
        body.append(p(note, "Caption"))
    else:
        body.append(p("", "Spacer"))

    col_styles = "".join(
        f'<style:style style:name="{name}.c{i}" style:family="table-column">'
        f'<style:table-column-properties style:column-width="'
        f'{17.0 * w / total:.3f}cm"/></style:style>'
        for i, w in enumerate(widths))
    return "".join(body), col_styles


# ------------------------------------------------------------- the figure --
def find_figure():
    for cand in FIGURE_CANDIDATES:
        path = os.path.join(HERE, cand)
        if os.path.exists(path):
            return path, cand != FIGURE_CANDIDATES[0]
    raise SystemExit("no figure found in docs/")


FIG_PATH, FIG_IS_PLACEHOLDER = find_figure()
FIG_W_PX, FIG_H_PX = png_size(FIG_PATH)
FIG_W_CM = 17.0
FIG_H_CM = FIG_W_CM * FIG_H_PX / FIG_W_PX


def figure(caption):
    return (
        '<text:p text:style-name="Figure">'
        f'<draw:frame draw:style-name="FrameStyle" draw:name="Figure1" '
        f'text:anchor-type="as-char" svg:width="{FIG_W_CM:.3f}cm" '
        f'svg:height="{FIG_H_CM:.3f}cm" draw:z-index="0">'
        '<draw:image xlink:href="Pictures/figure1.png" xlink:type="simple" '
        'xlink:show="embed" xlink:actuate="onLoad"/>'
        "</draw:frame></text:p>"
        + p(caption, "Caption"))


# --------------------------------------------------------- computed facts --
TICK_US = 1e6 / (APB_HZ / ACTIVE_DIV)
ACTIVE_RES = round(APB_HZ / ACTIVE_DIV)
ACTIVE_PULSE_HZ = APB_HZ / (ACTIVE_DIV * TICKS_PER_CYCLE)

FREQ_ROWS = []
for n in range(20, 26):
    res = round(APB_HZ / n)
    f = APB_HZ / (n * TICKS_PER_CYCLE)
    err = 100.0 * (f - TARGET_HZ) / TARGET_HZ
    marker = "  <- current" if n == ACTIVE_DIV else ""
    FREQ_ROWS.append([
        esc(f"{n}{marker}"),
        mono(f"{res:,}"),
        esc(f"{f/1e6:.4f}"),
        esc(f"{err:+.2f} %"),
        esc(f"{1e6/res:.4f}"),
    ])

PRESET_ROWS = [
    [mono("cfg_default"), "8", "1", "4", "0", "0",
     esc("takes its numbers from the #defines in US_TST.h")],
    [mono("cfg_no_hold"), "8", "-", "0", "0", "0",
     esc("BURST drops low immediately after the last pulse")],
    [mono("cfg_long_hold"), "8", "1", "181", "0", "0",
     esc("50 us hold; visible on a slow timebase. ACTIVE_CONFIG")],
    [mono("cfg_max_burst"), "46", "1", "4", "0", "0",
     esc("longest burst that fits one RMT memory block")],
    [mono("cfg_guarded"), "8", "1", "2", "4", "4",
     esc("guard bands both ends, for checking GATE alignment")],
]

PARAM_ROWS = [
    [mono("burst_gpio"), esc("GPIO number"), esc("GPIO 9"),
     esc("must differ from gate_gpio")],
    [mono("gate_gpio"), esc("GPIO number"), esc("GPIO 10"),
     esc("must differ from burst_gpio")],
    [mono("resolution_hz"), esc("Hz"), esc(f"{ACTIVE_RES:,}"),
     esc("at least 1 kHz; see section 3")],
    [mono("pulse_count"), esc("full cycles"), esc("8"),
     esc("at least 1; upper bound set by RMT memory, see 5")],
    [mono("hold_level"), esc("0 or 1"), esc("1"), esc("-")],
    [mono("hold_ticks"), esc("ticks"), esc("181"), esc("0, or 2 and above")],
    [mono("gate_lead_ticks"), esc("ticks"), esc("0"), esc("0, or 2 and above")],
    [mono("gate_tail_ticks"), esc("ticks"), esc("0"), esc("0, or 2 and above")],
]


# ------------------------------------------------------------- the prose --
STRUCT_LISTING = """
typedef struct {
    const char *name;            /* shown in the boot log */

    gpio_num_t  burst_gpio;      /* pin carrying the BURST pulse train */
    gpio_num_t  gate_gpio;       /* pin carrying the GATE envelope */

    uint32_t    resolution_hz;   /* RMT tick rate; BURST frequency = this / 2 */
    uint16_t    pulse_count;     /* full square-wave cycles in the burst */

    uint8_t     hold_level;      /* level parked on BURST after the last pulse */
    uint32_t    hold_ticks;      /* duration of that hold; 0 = none */

    uint32_t    gate_lead_ticks; /* GATE asserts this many ticks early */
    uint32_t    gate_tail_ticks; /* GATE releases this many ticks late */

    /* ---- planned, not yet implemented ---- */
    bool        burst_invert;    /* invert the BURST output polarity */
    bool        gate_invert;     /* invert the GATE output polarity */
} burst_config_t;
"""


def build_body():
    auto = []
    parts = []
    A = parts.append

    A('<text:p text:style-name="Title">Driving a 1 mm Ultrasound Crystal</text:p>')
    A('<text:p text:style-name="Subtitle">BURST and GATE signal generation on the '
      'ESP32-S3 RMT peripheral</text:p>')
    A(p(esc("TPT_Ultrasound_Drive  ·  firmware in main/US_TST.c and main/US_TST.h"),
        "Byline"))

    # ---- 1 -------------------------------------------------------------
    A(h("1.  Purpose of the code", 1))
    A(p(esc("This firmware produces the two outputs needed to drive a tiny (1 mm) "
            "ultrasound crystal:")))
    A(bullet([
        bold("BURST") + esc(" - a series of pulses, primarily at one frequency."),
        bold("GATE") + esc(" - an enabling signal, typically an envelope around the "
                           "pulse burst, with options to extend beyond the burst."),
    ]))
    A(p(esc("In use, the two signals are inputs to a digital line driver chip whose "
            "output drives the crystal. The line driver has two inputs: the output "
            "signal, and the tri-state output drive. The tri-state output drive can "
            "be thought of as a switch in series with the driver output. When the "
            "tri-state input is high, the switch is open and the crystal is "
            "disconnected.")))
    A(p(esc("The line-driver chip strongly clamps the output voltage - and hence the "
            "displacement - of the transducer to its logic level. For this reason we "
            "need to disconnect the driver from the crystal to allow it to resonate "
            "naturally.")))
    A(p(esc("Because of the low drive voltage (5 V, low for an ultrasound transducer "
            "crystal) we build up oscillation amplitude by sending a series of pulses "
            "of energy at the crystal's resonant frequency, rather than by driving a "
            "single large excursion.")))

    A(h("1.1  Two wiring modes", 2))
    A(p(esc("Two modes are possible, and they are a wiring choice rather than a "
            "firmware setting - the same two output signals serve both:")))
    A(bullet([
        bold("Mode A. ") + esc("BURST drives the driver's output signal, and GATE "
                               "drives the tri-state input. The crystal is driven "
                               "during the burst and released afterwards."),
        bold("Mode B. ") + esc("GATE is applied to the driver's output signal (held "
                               "like a constant logic 1) and BURST rapidly opens and "
                               "closes the tri-state switch."),
    ]))

    A(h("1.2  GATE polarity", 2))
    A(raw_p(esc("As currently built, GATE is ") + bold("active low") + esc(
        ": the pin sits at 0 for the whole window in which the driver is connected, "
        "and rests at 1 - the high-impedance state, crystal disconnected - before and "
        "after. The pin is also initialised high when the channel is created, so the "
        "crystal is disconnected from power-up onward, before the first burst is ever "
        "transmitted.")))
    A(raw_p(esc("A planned revision will make this a per-signal option; see section "
                "2.2.")))

    # ---- 2 -------------------------------------------------------------
    A(h("2.  Signal models and parameters", 1))
    A(p(esc("All of the settings that vary between runs live in one struct. A named "
            "instance of this struct is a preset, and selecting a preset is the "
            "single edit that configures a build.")))
    A(h("2.1  The output settings struct", 2))
    A(code(STRUCT_LISTING))
    A(p(esc("Durations are given in RMT ticks. One tick is the period of the RMT "
            "clock, so its length in microseconds follows from resolution_hz "
            f"(section 3). At the current setting one tick is {TICK_US:.4f} us."),
        "Caption"))

    A(h("2.2  Planned: selectable output polarity", 2))
    A(raw_p(esc("The last two fields above are ") + bold("not yet implemented") + esc(
        ". A later revision will let each output be inverted independently, so that "
        "either signal can be matched to a line driver of either polarity without "
        "rewiring or adding an external inverter:")))
    A(bullet([
        mono("burst_invert") + esc(" - when true, the BURST pin emits the complement "
                                   "of the waveform described here. The resting level "
                                   "inverts with it."),
        mono("gate_invert") + esc(" - when true, GATE is asserted high during the "
                                  "enabled window and rests low, instead of the "
                                  "active-low behaviour described in section 1.2."),
    ]))
    A(p(esc("Until those flags exist, the polarities are fixed as drawn in Figure 1.")))

    A(h("2.3  The parameters in time", 2))
    A(p(esc("Figure 1 shows every parameter against the two waveforms. Both channels "
            "are released on the same clock edge by the RMT hardware, so t = 0 is "
            "common to both pins and the alignment shown is exact.")))
    A(figure("Figure 1.  BURST and GATE with all timing parameters marked. Drawn with "
             "small lead and tail values, as in the “guarded” preset. Edges "
             "are ideal; no propagation delay is shown."))

    A(p(esc("Reading the figure left to right, one round consists of:")))
    A(bullet([
        mono("gate_lead_ticks") + esc(" - GATE asserts, connecting the driver, while "
                                      "BURST is still idle."),
        mono("pulse_count") + esc(" full square-wave cycles on BURST, each one tick "
                                  "high and one tick low, so the burst occupies "
                                  "2 x pulse_count ticks."),
        mono("hold_ticks") + esc(" at ") + mono("hold_level") + esc(
            " - BURST is parked at a steady level after the last pulse. This is what "
            "makes a pulsed-impedance mode possible; set hold_ticks to 0 and the line "
            "drops straight to 0."),
        mono("gate_tail_ticks") + esc(" - the driver stays connected after the hold "
                                      "ends, then GATE releases and the crystal is "
                                      "disconnected to ring freely."),
    ]))

    tbl, cs = table("Params",
                    ["Field", "Units", "Value in the active preset", "Constraint"],
                    PARAM_ROWS, [3, 2.2, 3, 5],
                    "Table 1.  Parameters, with the values of the currently selected "
                    "preset (cfg_long_hold).")
    A(tbl)
    auto.append(cs)

    A(h("2.4  Supplied presets", 2))
    A(raw_p(esc("The presets live at the top of ") + mono("main/US_TST.c") + esc(
        ". Exactly one is compiled into a build, chosen by the ") + mono(
        "ACTIVE_CONFIG") + esc(" line just below the last preset; changing "
                               "configuration is that one edit.")))
    tbl, cs = table("Presets",
                    ["Preset", "pulses", "hold level", "hold ticks", "lead", "tail",
                     "Purpose"],
                    PRESET_ROWS, [3.2, 1.4, 1.6, 1.6, 1.1, 1.1, 6.2],
                    "Table 2.  The presets as shipped. cfg_long_hold is the one "
                    "currently selected.")
    A(tbl)
    auto.append(cs)

    # ---- 3 -------------------------------------------------------------
    A(h("3.  Setting the frequency", 1))
    A(p(esc("Although the transducer has a nominal resonant frequency of 1.8 MHz, we "
            "may need to tune our output to be as close as possible to a true "
            "resonance near that value. The resolution of the RMT clock is very high, "
            "but it yields only discrete frequencies in the neighbourhood of "
            "1.8 MHz.")))

    A(h("3.1  How the frequency is derived", 2))
    A(raw_p(esc("Every pulse is built as one tick high followed by one tick low, so a "
                "full cycle is always two ticks and the output frequency is exactly "
                "half the tick rate:")))
    A(code("""
    f_BURST  =  resolution_hz / 2

    resolution_hz  =  80 MHz / N          (N an integer divider)

    so    f_BURST  =  40 MHz / N
    """))
    A(raw_p(esc("The 80 MHz is the APB clock, which is what ") + mono(
        "RMT_CLK_SRC_DEFAULT") + esc(" selects on the ESP32-S3. To pick a frequency, "
                                     "choose the divider nearest your target and then "
                                     "write the corresponding tick rate:")))
    A(code("""
    N              =  round(40 MHz / f_target)
    resolution_hz  =  round(80 MHz / N)
    """))
    A(raw_p(esc("For the nominal 1.8 MHz that gives N = 22 and ") + mono(
        "RMT_RESOLUTION_HZ = 3,636,364") + esc(f", producing "
                                               f"{ACTIVE_PULSE_HZ/1e6:.4f} MHz. That "
                                               "is 1.01 % above target, which has "
                                               "been confirmed acceptable for this "
                                               "application.")))

    A(h("3.2  Making the change", 2))
    A(p(esc("To retune, edit one number:")))
    A(bullet([
        esc("For a quick one-off, change ") + mono("RMT_RESOLUTION_HZ") + esc(
            " in main/US_TST.h. This feeds cfg_default only."),
        esc("For a value worth keeping, set ") + mono("resolution_hz") + esc(
            " in a preset in main/US_TST.c, or add a new preset, and point ") + mono(
            "ACTIVE_CONFIG") + esc(" at it."),
    ]))
    A(raw_p(esc("Rebuild and flash. The boot log prints the resulting pulse frequency, "
                "so the value actually achieved can be confirmed against the table "
                "below rather than assumed.")))
    A(raw_p(esc("One caution when changing ") + mono("resolution_hz") + esc(
        ": every duration in the preset is expressed in ticks, so changing the tick "
        "rate changes the real length of every hold and guard band. The ") + mono(
        "TICKS_FROM_US_AT(us, hz)") + esc(" macro exists for this reason - it converts "
                                          "a duration in microseconds to ticks and "
                                          "takes the rate explicitly, so it cannot "
                                          "silently disagree with the resolution_hz "
                                          "of the preset it appears in.")))

    A(h("3.3  Frequencies available near 1.8 MHz", 2))
    tbl, cs = table("Freq",
                    ["Divider N", "resolution_hz", "f_BURST (MHz)",
                     "Error vs 1.8 MHz", "Tick (us)"],
                    FREQ_ROWS, [2.4, 3.2, 3.0, 3.0, 2.4],
                    "Table 3.  Output frequencies obtainable with an integer divider "
                    "from the 80 MHz APB clock.")
    A(tbl)
    A(raw_p(bold("Note the coarseness. ") + esc(
        "Near 1.8 MHz, consecutive dividers are roughly 5 % apart - 1.9048, 1.8182 and "
        "1.7391 MHz are the only choices in the immediate neighbourhood. For a "
        "transducer whose resonance is sharp, this grid may be too coarse to land on "
        "the peak, and the planned frequency search (below) would be choosing among "
        "these three rather than sweeping continuously. If finer steps prove necessary, "
        "the fractional group-clock divider on the ESP32-S3 RMT is the thing to "
        "investigate; whether the IDF driver exposes it through resolution_hz has not "
        "been verified here.")))

    A(h("3.4  Planned: automatic frequency search", 2))
    A(p(esc("A future revision of the code will include a means to search a set of "
            "neighbouring frequencies and return the one with the highest response.")))

    # ---- 4 -------------------------------------------------------------
    A(h("4.  Repetition rate", 1))
    A(raw_p(esc("The firmware transmits one round, waits for both channels to finish, "
                "and then blocks for exactly one FreeRTOS tick before the next round. "
                "At the default ") + mono("CONFIG_FREERTOS_HZ = 100") + esc(
        " that tick is 10 ms, giving roughly 100 bursts per second. The burst itself is "
        "only a few microseconds, so the duty cycle is very low; a long post-burst hold "
        "is the only thing that materially extends a round.")))
    A(raw_p(esc("To change the repetition rate, change the ") + mono("vTaskDelay(1)") +
            esc(" at the end of the transmit loop, or the FreeRTOS tick rate in "
                "menuconfig.")))

    # ---- 5 -------------------------------------------------------------
    A(h("5.  Limits and startup checks", 1))
    A(p(esc("Both waveforms are held entirely in the RMT peripheral's own memory, "
            "which avoids any refill interrupt and is what keeps the timing exact. "
            "That memory is the binding constraint on burst length:")))
    A(bullet([
        esc("One RMT memory block holds 48 symbols, one of which is spent on the "
            "end-of-transmission marker, leaving 47."),
        esc("The BURST waveform costs one symbol per pulse, plus one for a lead-in "
            "and one for a hold if either is used. With both in use the ceiling is "
            "45 pulses; with neither it is 47. The cfg_max_burst preset sits at 46."),
        esc("Every duration field must be either 0 or at least 2 ticks. A duration of "
            "0 is the hardware's end-of-transmission marker, and a steady level is "
            "emitted as two non-zero halves, so a single tick cannot be expressed."),
    ]))
    A(raw_p(esc("These are checked at startup by ") + mono("validate_config()") + esc(
        ", whose result is error-checked, so a bad preset halts the boot with a named "
        "reason in the log rather than emitting a malformed waveform. Pin numbers are "
        "range-checked and tested for collision there too; the RMT driver itself "
        "rejects a pin that cannot drive an output.")))

    A(h("5.1  Why both signals come from the same peripheral", 2))
    A(p(esc("BURST and GATE must be aligned in time precisely. An earlier version drove "
            "the gate from a general-purpose timer, which could not hold the required "
            "synchronisation against the pulses. Both signals now come from two "
            "channels of the RMT peripheral, tied together by its transmit sync "
            "manager: neither channel starts until both have been armed, so they leave "
            "the peripheral on the same clock edge regardless of the software latency "
            "between the two transmit calls. This is a hardware guarantee, not a "
            "best-effort one, and it is the reason the alignment in Figure 1 can be "
            "taken literally.")))

    if FIG_IS_PLACEHOLDER:
        A(h("Note on this draft", 1))
        A(raw_p(bold("Figure 1 is a placeholder. ") + esc(
            "The image embedded above is docs/" + os.path.basename(FIG_PATH) +
            ", which includes the three small side panels. Save the cropped main panel "
            "as docs/figure1.png and re-run docs/make_doc.py to replace it.")))

    return "".join(parts), "".join(auto)


# ------------------------------------------------------------ XML wrappers --
NS = (
    'xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
    'xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0" '
    'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" '
    'xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0" '
    'xmlns:draw="urn:oasis:names:tc:opendocument:xmlns:drawing:1.0" '
    'xmlns:fo="urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0" '
    'xmlns:xlink="http://www.w3.org/1999/xlink" '
    'xmlns:svg="urn:oasis:names:tc:opendocument:xmlns:svg-compatible:1.0" '
    'xmlns:meta="urn:oasis:names:tc:opendocument:xmlns:meta:1.0" '
    'xmlns:dc="http://purl.org/dc/elements/1.1/" '
    'xmlns:number="urn:oasis:names:tc:opendocument:xmlns:datastyle:1.0"'
)

FONTS = (
    "<office:font-face-decls>"
    '<style:font-face style:name="Source Sans Pro" svg:font-family="&apos;Source Sans Pro&apos;, &apos;DejaVu Sans&apos;, sans-serif" style:font-family-generic="swiss"/>'
    '<style:font-face style:name="DejaVu Sans Mono" svg:font-family="&apos;DejaVu Sans Mono&apos;, monospace" style:font-family-generic="modern" style:font-pitch="fixed"/>'
    "</office:font-face-decls>"
)


def styles_xml():
    def para(name, parent, props, text_props=""):
        return (f'<style:style style:name="{name}" style:family="paragraph" '
                f'style:parent-style-name="{parent}" style:class="text">'
                f"<style:paragraph-properties {props}/>"
                f"<style:text-properties {text_props}/>"
                "</style:style>")

    body_font = 'style:font-name="Source Sans Pro" fo:font-size="10.5pt" fo:color="#1c1c1e"'
    head_font = 'style:font-name="Source Sans Pro" fo:font-weight="bold"'

    s = [
        '<style:style style:name="Standard" style:family="paragraph">'
        f'<style:paragraph-properties fo:line-height="140%" fo:text-align="justify"/>'
        f"<style:text-properties {body_font}/></style:style>",

        para("Text_20_body", "Standard", 'fo:margin-top="0cm" fo:margin-bottom="0.28cm"'),

        para("Title", "Standard",
             'fo:margin-top="0cm" fo:margin-bottom="0.10cm" fo:text-align="start" '
             'fo:keep-with-next="always"',
             f'{head_font} fo:font-size="22pt" fo:color="#111114"'),
        para("Subtitle", "Standard",
             'fo:margin-top="0cm" fo:margin-bottom="0.10cm" fo:text-align="start"',
             'style:font-name="Source Sans Pro" fo:font-size="13pt" '
             'fo:color="#55555c"'),
        para("Byline", "Standard",
             'fo:margin-top="0cm" fo:margin-bottom="0.9cm" fo:text-align="start" '
             'fo:border-bottom="0.5pt solid #d5d5dc" fo:padding-bottom="0.25cm"',
             'style:font-name="Source Sans Pro" fo:font-size="9.5pt" '
             'fo:color="#77777f"'),

        para("Heading_20_1", "Standard",
             'fo:margin-top="0.75cm" fo:margin-bottom="0.30cm" fo:text-align="start" '
             'fo:keep-with-next="always"',
             f'{head_font} fo:font-size="15pt" fo:color="#111114"'),
        para("Heading_20_2", "Standard",
             'fo:margin-top="0.55cm" fo:margin-bottom="0.22cm" fo:text-align="start" '
             'fo:keep-with-next="always"',
             f'{head_font} fo:font-size="11.5pt" fo:color="#2c2c33"'),

        para("List_20_Bullet", "Standard",
             'fo:margin-top="0cm" fo:margin-bottom="0.18cm" fo:margin-left="0.75cm" '
             'fo:text-indent="-0.45cm" fo:text-align="start"'),

        para("Code", "Standard",
             'fo:margin-top="0cm" fo:margin-bottom="0cm" fo:margin-left="0.7cm" '
             'fo:text-align="start" fo:line-height="122%"',
             'style:font-name="DejaVu Sans Mono" fo:font-size="9pt" '
             'fo:color="#1f3d6e"'),

        para("Caption", "Standard",
             'fo:margin-top="0.18cm" fo:margin-bottom="0.45cm" fo:text-align="start"',
             'style:font-name="Source Sans Pro" fo:font-size="9pt" '
             'fo:color="#66666e" fo:font-style="italic"'),
        para("Spacer", "Standard", 'fo:margin-top="0cm" fo:margin-bottom="0.35cm"',
             'fo:font-size="4pt"'),
        para("Figure", "Standard",
             'fo:margin-top="0.35cm" fo:margin-bottom="0cm" fo:text-align="center"'),

        para("TblHead", "Standard",
             'fo:margin="0cm" fo:text-align="start" fo:line-height="118%"',
             'style:font-name="Source Sans Pro" fo:font-size="9pt" '
             'fo:font-weight="bold" fo:color="#ffffff"'),
        para("TblCell", "Standard",
             'fo:margin="0cm" fo:text-align="start" fo:line-height="118%"',
             'style:font-name="Source Sans Pro" fo:font-size="9pt"'),

        '<style:style style:name="Mono" style:family="text">'
        '<style:text-properties style:font-name="DejaVu Sans Mono" '
        'fo:font-size="9pt" fo:color="#1f3d6e"/></style:style>',
        '<style:style style:name="Bold" style:family="text">'
        '<style:text-properties fo:font-weight="bold"/></style:style>',

        '<style:style style:name="FrameStyle" style:family="graphic">'
        '<style:graphic-properties style:vertical-pos="middle" '
        'style:vertical-rel="text" fo:border="0.5pt solid #dcdce2" '
        'fo:padding="0.1cm"/></style:style>',
    ]

    page = (
        '<office:automatic-styles>'
        '<style:page-layout style:name="PL">'
        '<style:page-layout-properties fo:page-width="21.0cm" fo:page-height="29.7cm" '
        'style:print-orientation="portrait" fo:margin-top="2.0cm" '
        'fo:margin-bottom="2.0cm" fo:margin-left="2.0cm" fo:margin-right="2.0cm"/>'
        "</style:page-layout></office:automatic-styles>"
        '<office:master-styles>'
        '<style:master-page style:name="Standard" style:page-layout-name="PL"/>'
        "</office:master-styles>"
    )

    return ('<?xml version="1.0" encoding="UTF-8"?>'
            f"<office:document-styles {NS} office:version=\"1.2\">"
            f"{FONTS}<office:styles>{''.join(s)}</office:styles>{page}"
            "</office:document-styles>")


def content_xml(body, auto_cols):
    tbl_styles = (
        '<style:style style:name="Params" style:family="table">'
        '<style:table-properties style:width="17cm" table:align="left"/></style:style>'
        '<style:style style:name="Presets" style:family="table">'
        '<style:table-properties style:width="17cm" table:align="left"/></style:style>'
        '<style:style style:name="Freq" style:family="table">'
        '<style:table-properties style:width="17cm" table:align="left"/></style:style>'
        '<style:style style:name="CellHead" style:family="table-cell">'
        '<style:table-cell-properties fo:background-color="#3f4a5a" '
        'fo:padding="0.13cm" fo:border="none"/></style:style>'
        '<style:style style:name="CellA" style:family="table-cell">'
        '<style:table-cell-properties fo:background-color="#ffffff" '
        'fo:padding="0.13cm" fo:border-bottom="0.5pt solid #e2e2e8"/></style:style>'
        '<style:style style:name="CellB" style:family="table-cell">'
        '<style:table-cell-properties fo:background-color="#f5f6f8" '
        'fo:padding="0.13cm" fo:border-bottom="0.5pt solid #e2e2e8"/></style:style>'
    )
    list_style = (
        '<text:list-style style:name="Bullets">'
        + "".join(
            f'<text:list-level-style-bullet text:level="{lv}" text:bullet-char="•">'
            f'<style:list-level-properties text:space-before="{0.4*lv:.2f}cm" '
            f'text:min-label-width="0.45cm"/>'
            "</text:list-level-style-bullet>" for lv in range(1, 4))
        + "</text:list-style>"
    )
    return ('<?xml version="1.0" encoding="UTF-8"?>'
            f'<office:document-content {NS} office:version="1.2">'
            f"{FONTS}"
            f"<office:automatic-styles>{tbl_styles}{auto_cols}{list_style}"
            "</office:automatic-styles>"
            "<office:body><office:text>"
            f"{body}"
            "</office:text></office:body></office:document-content>")


META = ('<?xml version="1.0" encoding="UTF-8"?>'
        f'<office:document-meta {NS} office:version="1.2"><office:meta>'
        "<dc:title>Driving a 1 mm Ultrasound Crystal</dc:title>"
        "<meta:generator>docs/make_doc.py</meta:generator>"
        "</office:meta></office:document-meta>")

MANIFEST = ('<?xml version="1.0" encoding="UTF-8"?>'
            '<manifest:manifest xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0" manifest:version="1.2">'
            '<manifest:file-entry manifest:full-path="/" manifest:version="1.2" manifest:media-type="application/vnd.oasis.opendocument.text"/>'
            '<manifest:file-entry manifest:full-path="content.xml" manifest:media-type="text/xml"/>'
            '<manifest:file-entry manifest:full-path="styles.xml" manifest:media-type="text/xml"/>'
            '<manifest:file-entry manifest:full-path="meta.xml" manifest:media-type="text/xml"/>'
            '<manifest:file-entry manifest:full-path="Pictures/figure1.png" manifest:media-type="image/png"/>'
            "</manifest:manifest>")


def main():
    body, auto_cols = build_body()

    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        # mimetype must be the first entry and stored uncompressed
        z.writestr(zipfile.ZipInfo("mimetype"),
                   "application/vnd.oasis.opendocument.text",
                   compress_type=zipfile.ZIP_STORED)
        z.writestr("META-INF/manifest.xml", MANIFEST)
        z.writestr("meta.xml", META)
        z.writestr("styles.xml", styles_xml())
        z.writestr("content.xml", content_xml(body, auto_cols))
        z.write(FIG_PATH, "Pictures/figure1.png")

    print("wrote", OUT)
    print("figure:", os.path.basename(FIG_PATH),
          f"({FIG_W_PX}x{FIG_H_PX} px)",
          "-- PLACEHOLDER" if FIG_IS_PLACEHOLDER else "")


if __name__ == "__main__":
    main()
