#!/usr/bin/env python3
"""Draw the two RMT waveforms of US_TST.c with dimension lines for every
burst_config_t field.

The geometry here mirrors build_burst_symbols() / build_hiZ_symbols():

    burst pin : 0 for hiz_lead_ticks
                pulse_count x (1 tick high, 1 tick low)
                hold_level for hold_ticks
                0 (eot_level) afterwards
    Hi-Z gate : STATE_LO_Z for lead + 2*pulse_count + hold + tail
                STATE_HI_Z (init_level / eot_level) otherwise

Both channels are released by the RMT TX sync manager, so t = 0 is the same
clock edge on both pins.

    python3 docs/make_timing_diagram.py     # writes docs/timing_*.png and .svg
"""

import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle

# ---------------------------------------------------------------- palette --
C_BURST = "#1f6feb"   # pulse train
C_GATE  = "#d1731a"   # Hi-Z gate
INK     = "#1c1c1e"
INK2    = "#55555c"
MUTED   = "#9a9aa2"
SURFACE = "#fcfcfb"
BAND    = "#eceef2"   # shading behind the window in which the gate is low

RMT_TICKS_PER_CYCLE = 2


# ------------------------------------------------------------- the configs --
# Field names match burst_config_t in main/US_TST.h.
CONFIGS = {
    # Not one of the presets: every optional field is non-zero and generously
    # sized so each dimension line has room. This is the parameter drawing.
    "illustrative": dict(
        name="illustrative (all fields non-zero)",
        burst_gpio=9, hiz_gpio=10,
        resolution_hz=3636364,
        pulse_count=6,
        hold_level=1, hold_ticks=8,
        hiz_lead_ticks=4, hiz_tail_ticks=4,
    ),
    # ACTIVE_CONFIG in main/US_TST.c.
    "long-hold": dict(
        name="long-hold  (ACTIVE_CONFIG)",
        burst_gpio=9, hiz_gpio=10,
        resolution_hz=3636364,
        pulse_count=8,
        hold_level=1, hold_ticks=181,
        hiz_lead_ticks=0, hiz_tail_ticks=0,
    ),
    "guarded": dict(
        name="guarded",
        burst_gpio=9, hiz_gpio=10,
        resolution_hz=3636364,
        pulse_count=8,
        hold_level=1, hold_ticks=2,
        hiz_lead_ticks=4, hiz_tail_ticks=4,
    ),
    "no-hold": dict(
        name="no-hold",
        burst_gpio=9, hiz_gpio=10,
        resolution_hz=3636364,
        pulse_count=8,
        hold_level=0, hold_ticks=0,
        hiz_lead_ticks=0, hiz_tail_ticks=0,
    ),
}


def edges(cfg):
    """Tick numbers of the boundaries in the waveform."""
    lead = cfg["hiz_lead_ticks"]
    burst = cfg["pulse_count"] * RMT_TICKS_PER_CYCLE
    e = dict(t0=0, burst_start=lead, burst_end=lead + burst,
             hold_end=lead + burst + cfg["hold_ticks"], burst_ticks=burst)
    e["tail_end"] = e["hold_end"] + cfg["hiz_tail_ticks"]
    return e


# ------------------------------------------------------------- primitives --
def trace(ax, pts, lo, hi, color, lw=2.0):
    """pts is [(t, level 0|1), ...]; drawn as an ideal square wave."""
    xs, ys, prev = [], [], None
    for t, lv in pts:
        y = hi if lv else lo
        if prev is not None and prev != y:
            xs.append(t); ys.append(prev)          # the vertical edge
        xs.append(t); ys.append(y)
        prev = y
    ax.plot(xs, ys, color=color, lw=lw, solid_joinstyle="miter",
            solid_capstyle="butt", zorder=5, clip_on=False)


def burst_points(cfg, e, pre, post):
    p = [(-pre, 0), (e["burst_start"], 0)]
    t = e["burst_start"]
    for _ in range(cfg["pulse_count"]):
        p += [(t, 1), (t + 1, 1), (t + 1, 0), (t + 2, 0)]
        t += 2
    if cfg["hold_ticks"]:
        p += [(t, cfg["hold_level"]), (e["hold_end"], cfg["hold_level"])]
    return p + [(e["hold_end"], 0), (e["tail_end"] + post, 0)]


def gate_points(cfg, e, pre, post):
    return [(-pre, 1), (0, 1), (0, 0), (e["tail_end"], 0),
            (e["tail_end"], 1), (e["tail_end"] + post, 1)]


def dim(ax, x0, x1, y, label, sub=None, color=INK, fs=9.5, above=True,
        outside=False, gap=0.55):
    """A dimension line with arrowheads and end ticks, plus its caption.

    outside=True puts the arrowheads outside the extension lines, for a span
    too narrow to hold them.
    """
    if outside:
        pad = 0.05 * (x1 - x0) + 0.012 * (ax.get_xlim()[1] - ax.get_xlim()[0])
        ax.annotate("", xy=(x0, y), xytext=(x0 - pad, y),
                    arrowprops=dict(arrowstyle="->", color=color, lw=1.1,
                                    shrinkA=0, shrinkB=0))
        ax.annotate("", xy=(x1, y), xytext=(x1 + pad, y),
                    arrowprops=dict(arrowstyle="->", color=color, lw=1.1,
                                    shrinkA=0, shrinkB=0))
        ax.plot([x0, x1], [y, y], color=color, lw=1.1, solid_capstyle="butt")
    else:
        ax.annotate("", xy=(x0, y), xytext=(x1, y),
                    arrowprops=dict(arrowstyle="<->", color=color, lw=1.1,
                                    shrinkA=0, shrinkB=0))
    # end ticks
    h = 0.13 * (ax.get_ylim()[1] - ax.get_ylim()[0]) / 13.0
    for x in (x0, x1):
        ax.plot([x, x], [y - h, y + h], color=color, lw=1.1)

    xm = (x0 + x1) / 2
    if above:
        y_lab, y_sub, va = y + gap + 0.60, y + gap, "bottom"
    else:
        y_lab, y_sub, va = y - gap, y - gap - 0.60, "top"
    ax.text(xm, y_lab, label, ha="center", va=va, fontsize=fs, color=color,
            family="monospace", zorder=8)
    if sub:
        ax.text(xm, y_sub, sub, ha="center", va=va, fontsize=8.5, color=INK2,
                zorder=8)


def witness(ax, x, y0, y1):
    ax.plot([x, x], [y0, y1], color=MUTED, lw=0.7, ls=(0, (2, 2)), zorder=1)


# ------------------------------------------------------- the main waveform --
def draw_main(ax, cfg, e, us):
    span = max(e["tail_end"], 1)
    pre = max(0.16 * span, 2.0)
    post = max(0.16 * span, 2.5)

    ax.set_facecolor(SURFACE)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_xticks([]); ax.set_yticks([])
    ax.set_xlim(-pre, e["tail_end"] + post)
    ax.set_ylim(-3.6, 9.8)

    B_LO, B_HI = 6.5, 8.0        # burst trace rails
    G_LO, G_HI = 1.9, 3.4        # gate trace rails

    ax.add_patch(Rectangle((0, G_LO - 0.6), e["tail_end"],
                           (B_HI + 0.6) - (G_LO - 0.6),
                           facecolor=BAND, edgecolor="none", zorder=0))

    for x in {0, e["burst_start"], e["burst_end"], e["hold_end"], e["tail_end"]}:
        witness(ax, x, -2.6, 8.6)

    trace(ax, burst_points(cfg, e, pre, post), B_LO, B_HI, C_BURST)
    trace(ax, gate_points(cfg, e, pre, post), G_LO, G_HI, C_GATE)

    # ---- identification, in the left gutter ------------------------------
    ax.text(-pre, B_HI + 0.55, f"BURST  ·  burst_gpio = GPIO {cfg['burst_gpio']}",
            fontsize=11.5, color=C_BURST, fontweight="bold", va="bottom")
    ax.text(-pre, G_HI + 0.55, f"HI-Z GATE  ·  hiz_gpio = GPIO {cfg['hiz_gpio']}",
            fontsize=11.5, color=C_GATE, fontweight="bold", va="bottom")
    for y, lab in ((B_HI, "1"), (B_LO, "0"), (G_HI, "1"), (G_LO, "0")):
        ax.text(-pre - 0.012 * span, y, lab, fontsize=9, color=MUTED,
                ha="right", va="center")

    # ---- resting levels ---------------------------------------------------
    ax.text(-pre * 0.5, B_LO - 0.35, "idles low\nflags.init_level = 0",
            fontsize=8.5, color=INK2, ha="center", va="top")
    ax.text(e["tail_end"] + post * 0.55, B_LO - 0.35,
            "rests low\nflags.eot_level = 0",
            fontsize=8.5, color=INK2, ha="center", va="top")
    ax.text(-pre * 0.5, G_HI - 0.35, "STATE_HI_Z = 1\ninit_level",
            fontsize=8.5, color=INK2, ha="center", va="top")
    ax.text(e["tail_end"] + post * 0.55, G_HI - 0.35,
            "STATE_HI_Z = 1\neot_level", fontsize=8.5, color=INK2,
            ha="center", va="top")
    ax.text(e["tail_end"] / 2, G_LO - 0.4,
            "STATE_LO_Z = 0   —   driver enabled for this whole window",
            fontsize=9, color=C_GATE, ha="center", va="top")

    if cfg["hold_ticks"]:
        hy = B_HI if cfg["hold_level"] else B_LO
        ax.text((e["burst_end"] + e["hold_end"]) / 2,
                hy + (0.25 if cfg["hold_level"] else -0.25),
                f"hold_level = {cfg['hold_level']}", fontsize=9.5,
                color=C_BURST, ha="center", family="monospace",
                va="bottom" if cfg["hold_level"] else "top")

    # ---- dimensions between the two traces -------------------------------
    mid = 5.1
    dim(ax, e["burst_start"], e["burst_end"], mid,
        f"pulse_count x 2 = {e['burst_ticks']} ticks",
        sub=f"pulse_count = {cfg['pulse_count']} cycles   ({us(e['burst_ticks']):.2f} µs)",
        color=C_BURST, above=False)
    if cfg["hold_ticks"]:
        dim(ax, e["burst_end"], e["hold_end"], mid,
            f"hold_ticks = {cfg['hold_ticks']}",
            sub=f"{us(cfg['hold_ticks']):.2f} µs", color=C_BURST, above=True,
            outside=cfg["hold_ticks"] / span < 0.10)
    else:
        ax.annotate("hold_ticks = 0\n(no post-burst hold)",
                    xy=(e["hold_end"], mid), xytext=(e["hold_end"] + 0.22 * span, mid + 1.1),
                    fontsize=9, color=C_BURST, ha="center", va="center",
                    family="monospace",
                    arrowprops=dict(arrowstyle="->", color=C_BURST, lw=0.9))

    # ---- dimensions below the gate ---------------------------------------
    d1, d2 = 0.0, -2.0
    if cfg["hiz_lead_ticks"]:
        dim(ax, 0, e["burst_start"], d1, f"hiz_lead_ticks = {cfg['hiz_lead_ticks']}",
            sub=f"{us(cfg['hiz_lead_ticks']):.2f} µs", color=C_GATE, above=False,
            outside=cfg["hiz_lead_ticks"] / span < 0.10)
    else:
        ax.annotate("hiz_lead_ticks = 0\ngate falls with the first pulse",
                    xy=(0, G_LO), xytext=(-pre * 0.52, d1 - 0.5),
                    fontsize=8.5, color=C_GATE, ha="center", va="center",
                    arrowprops=dict(arrowstyle="->", color=C_GATE, lw=0.9))
    if cfg["hiz_tail_ticks"]:
        dim(ax, e["hold_end"], e["tail_end"], d1, f"hiz_tail_ticks = {cfg['hiz_tail_ticks']}",
            sub=f"{us(cfg['hiz_tail_ticks']):.2f} µs", color=C_GATE, above=False,
            outside=cfg["hiz_tail_ticks"] / span < 0.10)
    else:
        ax.annotate("hiz_tail_ticks = 0\ngate rises when the hold ends",
                    xy=(e["tail_end"], G_LO), xytext=(e["tail_end"] + post * 0.52, d1 - 0.5),
                    fontsize=8.5, color=C_GATE, ha="center", va="center",
                    arrowprops=dict(arrowstyle="->", color=C_GATE, lw=0.9))

    dim(ax, 0, e["tail_end"], d2,
        f"cfg_hiZ_low_ticks() = lead + 2*pulse_count + hold + tail = {e['tail_end']} ticks",
        sub=f"{us(e['tail_end']):.2f} µs   —   the length of one round, and the basis of "
            f"s_wait_timeout_ms", color=INK, above=False)


# ------------------------------------------------------ one-cycle detail --
def draw_detail(ax, cfg, us):
    f_pulse = cfg["resolution_hz"] / RMT_TICKS_PER_CYCLE
    ax.set_facecolor(SURFACE)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_xticks([]); ax.set_yticks([])
    ax.set_xlim(-0.7, 4.7)
    ax.set_ylim(-1.5, 5.4)

    pts = [(-0.7, 0), (0, 0)]
    t = 0
    for _ in range(2):
        pts += [(t, 1), (t + 1, 1), (t + 1, 0), (t + 2, 0)]
        t += 2
    pts += [(4.7, 0)]
    trace(ax, pts, 0.0, 1.5, C_BURST, lw=2.2)

    for x in (0, 1, 2):
        ax.plot([x, x], [-0.9, 2.0], color=MUTED, lw=0.7, ls=(0, (2, 2)), zorder=1)

    dim(ax, 0, 1, 2.45, "duration0 = 1", sub="level0 = 1", color=INK, fs=9,
        gap=0.18)
    dim(ax, 1, 2, -0.55, "duration1 = 1", sub="level1 = 0", color=INK, fs=9,
        above=False, gap=0.18)
    dim(ax, 0, 2, 4.35, "one RMT symbol = one cycle = 2 ticks", color=INK, fs=9,
        gap=0.18)
    ax.text(1.0, 3.55,
            f"{us(2):.4f} µs  →  resolution_hz / 2 = {f_pulse/1e6:.4f} MHz",
            fontsize=8.5, color=INK2, ha="center", va="center")

    ax.text(-0.7, 5.3, "Detail: one pulse  (built directly in build_burst_symbols)",
            fontsize=10, color=INK, fontweight="bold", va="top")


# ------------------------------------------------------- repetition panel --
def draw_repetition(ax, us, total_ticks):
    ax.set_facecolor(SURFACE)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_xticks([]); ax.set_yticks([])
    ax.set_xlim(-0.5, 10.5)
    ax.set_ylim(-2.2, 5.4)

    round_ms = us(total_ticks) / 1000.0
    w = max(round_ms / 10.0 * 3.2, 0.13)          # 10 ms mapped to 3.2 units
    for k in range(3):
        ax.add_patch(Rectangle((k * 3.2, 0), w, 1.5, facecolor=C_BURST,
                               edgecolor="none"))
    ax.plot([-0.4, 10.4], [0, 0], color=MUTED, lw=0.9)

    dim(ax, 0, 3.2, 2.6, "vTaskDelay(1) = 1 FreeRTOS tick", color=INK, fs=9,
        gap=0.18)
    ax.text(1.6, 4.3, "10 ms at the default CONFIG_FREERTOS_HZ = 100"
                      "\n→  ~100 bursts/s",
            fontsize=8.5, color=INK2, ha="center", va="center")
    ax.annotate(f"one round = {us(total_ticks):.1f} µs\n(the drawing above)",
                xy=(w, 0.75), xytext=(2.0, -1.5), fontsize=8.5, color=INK2,
                ha="center", va="center",
                arrowprops=dict(arrowstyle="->", color=MUTED, lw=0.9))
    ax.text(-0.5, 5.3, "Repetition  (horizontal scale compressed)", fontsize=10,
            color=INK, fontweight="bold", va="top")


# ------------------------------------------------------------ field table --
def draw_fields(ax, cfg, tick_us):
    rows = [
        ("name",           f'"{cfg["name"].split("  ")[0]}"',  "boot-log label only"),
        ("burst_gpio",     f"GPIO {cfg['burst_gpio']}",        "pin carrying the pulse train"),
        ("hiz_gpio",       f"GPIO {cfg['hiz_gpio']}",          "pin carrying the Hi-Z gate"),
        ("resolution_hz",  f"{cfg['resolution_hz']:,}",        f"1 tick = {tick_us:.4f} µs"),
        ("pulse_count",    f"{cfg['pulse_count']}",            "full cycles, 2 ticks each"),
        ("hold_level",     f"{cfg['hold_level']}",             "level parked after the last pulse"),
        ("hold_ticks",     f"{cfg['hold_ticks']}",             "length of that park; 0 = none"),
        ("hiz_lead_ticks", f"{cfg['hiz_lead_ticks']}",         "gate leads the first pulse"),
        ("hiz_tail_ticks", f"{cfg['hiz_tail_ticks']}",         "gate lags the end of the hold"),
    ]
    ax.set_facecolor(SURFACE)
    ax.set_axis_off()
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    ax.text(0, 1.0, "burst_config_t fields", fontsize=10, color=INK,
            fontweight="bold", va="top")
    ax.plot([0, 1], [0.90, 0.90], color="#dcdce2", lw=0.8)
    for i, (f, v, d) in enumerate(rows):
        y = 0.82 - i * 0.098
        ax.text(0.00, y, f, fontsize=8.5, color=INK, family="monospace", va="top")
        ax.text(0.34, y, v, fontsize=8.5, color=C_BURST, family="monospace", va="top")
        ax.text(0.62, y, d, fontsize=8, color=INK2, va="top")


# ------------------------------------------------------------- the figure --
def draw(cfg, path):
    e = edges(cfg)
    tick_us = 1e6 / cfg["resolution_hz"]
    us = lambda ticks: ticks * tick_us
    f_pulse = cfg["resolution_hz"] / RMT_TICKS_PER_CYCLE

    fig = plt.figure(figsize=(15.5, 10.0), facecolor=SURFACE)

    fig.text(0.055, 0.975, f'burst_config_t  "{cfg["name"]}"', fontsize=16,
             color=INK, fontweight="bold", va="top")
    fig.text(0.055, 0.937,
             f"resolution_hz = {cfg['resolution_hz']:,} Hz   →   1 tick = {tick_us:.4f} µs"
             f"   ·   pulse frequency = resolution_hz / 2 = {f_pulse:,.0f} Hz"
             f"   ·   horizontal axis is exact in RMT ticks",
             fontsize=10, color=INK2, va="top")

    draw_main(fig.add_axes([0.055, 0.40, 0.915, 0.50]), cfg, e, us)
    draw_detail(fig.add_axes([0.055, 0.07, 0.24, 0.24]), cfg, us)
    draw_repetition(fig.add_axes([0.375, 0.07, 0.24, 0.24]), us, e["tail_end"])
    draw_fields(fig.add_axes([0.675, 0.055, 0.295, 0.26]), cfg, tick_us)

    fig.legend(handles=[Line2D([], [], color=C_BURST, lw=2.4, label="burst pin"),
                        Line2D([], [], color=C_GATE, lw=2.4, label="Hi-Z gate pin")],
               loc="upper right", bbox_to_anchor=(0.97, 0.995), frameon=False,
               ncol=2, fontsize=10)
    fig.text(0.055, 0.018,
             "Both channels are released on the same clock edge by the RMT TX sync manager, "
             "so t = 0 is common to both pins.  Edges drawn ideal; no propagation delay shown.",
             fontsize=8.5, color=INK2)

    fig.savefig(path + ".png", dpi=170, facecolor=SURFACE)
    fig.savefig(path + ".svg", facecolor=SURFACE)
    plt.close(fig)
    print("wrote", path + ".png")


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    for key, cfg in CONFIGS.items():
        draw(cfg, os.path.join(here, f"timing_{key}"))
