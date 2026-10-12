#!/usr/bin/env python3
# Battery report for Settings > Hardware > Battery: what used the battery since it was last unplugged, from
# battery-log.sh's CSV (one line per 30 s while awake; a gap in ts = asleep). Prints JSON.
# charge_uah comes from the gauge in coarse, delayed steps: per-activity mAh is only meaningful over minutes.
import csv, json, sys

LOGS = ["/storage/battery-log.csv.1", "/storage/battery-log.csv"]
SLEEP_GAP = 120   # s between samples (logged every 30 s) that can only be a suspend
NAMES = {"menu": "Home", "es": "Home", "es-de": "Home", "panel": "Thor Panel", "settings": "Settings",
         "retroarch": "RetroArch", "azahar": "Azahar (3DS)", "melonDS": "melonDS (DS)", "drastic": "DraStic (DS)",
         "dolphin-emu": "Dolphin (GC/Wii)", "eden": "Eden (Switch)", "citron": "Citron (Switch)",
         "ryujinx": "Ryujinx (Switch)", "ppsspp": "PPSSPP (PSP)", "PPSSPP": "PPSSPP (PSP)", "pcsx2": "PCSX2 (PS2)",
         "armsx2": "ARMSX2 (PS2)", "aethersx2": "AetherSX2 (PS2)", "duckstation": "DuckStation (PS1)",
         "flycast": "Flycast (Dreamcast)", "mupen64plus": "Mupen64Plus (N64)", "moonlight": "Moonlight",
         "portmaster": "PortMaster"}


def name(app):
    for k, v in NAMES.items():   # the logger cuts process names to 15 chars (dolphin-emu-nog, armsx2-qt)
        if app.startswith(k):
            return v
    return app or "Home"


def load(paths):
    rows = []
    for p in paths:
        try:
            with open(p) as f:
                for r in csv.DictReader(f):
                    try:
                        rows.append({"ts": int(r["ts"]), "pct": int(r["capacity"]), "ua": int(r["current_ua"]),
                                     "uah": int(r["charge_uah"]), "app": r.get("app") or "",
                                     # older logs have no bat_status: the current's sign says it
                                     "chg": r.get("bat_status") in ("Charging", "Full") if r.get("bat_status")
                                            else int(r["current_ua"]) > 0})
                    except (KeyError, TypeError, ValueError):
                        continue   # a line cut by a crash or rotation
        except OSError:
            continue
    rows.sort(key=lambda r: r["ts"])
    return rows


def stretch(rows, end, charging):
    """Rows [start, end) of the run of samples with chg == charging that ends just before end."""
    start = end
    while start > 0 and rows[start - 1]["chg"] == charging:
        start -= 1
    return start


def report(rows):
    if not rows:
        return {"error": "no battery log yet"}
    last = rows[-1]
    end = len(rows)
    out = {"now": {"pct": last["pct"], "ma": round(-last["ua"] / 1000), "charging": last["chg"]}}
    if last["chg"]:   # charging now: report this charge, then the discharge before it
        s = stretch(rows, end, True)
        out["charge"] = span(rows[s:end])
        end = s
    d = stretch(rows, end, False)
    # A charger plugged in while asleep shows only as a level that rose across a sleep gap (both ends
    # Discharging): the session starts after the last rise.
    for i in range(end - 1, d, -1):
        if rows[i]["pct"] >= rows[i - 1]["pct"] + 2:   # 2: the gauge can tick up 1 % on its own after a load
            d = i
            break
    seg = rows[d:end]
    if len(seg) < 2:
        out["session"] = None
        return out
    acts = {}
    for a, b in zip(seg, seg[1:]):
        dt = b["ts"] - a["ts"]
        act = "Sleep" if dt > SLEEP_GAP else name(a["app"])
        x = acts.setdefault(act, [0, 0])
        x[0] += dt
        x[1] += a["uah"] - b["uah"]
    total_s = seg[-1]["ts"] - seg[0]["ts"]
    used_pct = seg[0]["pct"] - seg[-1]["pct"]
    used_uah = max(1, sum(max(0, v[1]) for v in acts.values()))
    out["session"] = dict(span(seg), activities=sorted(
        ({"name": k, "hours": round(v[0] / 3600, 2),
          "pct": round(used_pct * max(0, v[1]) / used_uah, 1),   # the % drop, split by each activity's share of mAh
          "ma": round(max(0, v[1]) / 1000 / (v[0] / 3600)) if v[0] else 0} for k, v in acts.items()),
        key=lambda a: -a["pct"]))
    # Time left at this session's average draw (sleep included): the gauge's charge counter is the remaining charge.
    hours = total_s / 3600
    avg_ma = (seg[0]["uah"] - seg[-1]["uah"]) / 1000 / hours if hours else 0
    if not last["chg"] and avg_ma > 0 and hours >= 0.5:
        out["now"]["hours_left"] = round(last["uah"] / 1000 / avg_ma, 1)
    return out


def span(seg):
    return {"start": seg[0]["ts"], "end": seg[-1]["ts"], "from_pct": seg[0]["pct"], "to_pct": seg[-1]["pct"],
            "hours": round((seg[-1]["ts"] - seg[0]["ts"]) / 3600, 2)}


if __name__ == "__main__":
    print(json.dumps(report(load(sys.argv[1:] or LOGS))))
