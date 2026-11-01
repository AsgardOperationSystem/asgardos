#!/usr/bin/env python3
# spec: BAT-1
# python3 test_battery_report.py: battery-report.py on a synthetic log (asleep = a gap, then a charge).
import importlib.util, os, tempfile

spec = importlib.util.spec_from_file_location("br", os.path.join(os.path.dirname(os.path.abspath(__file__)), "battery-report.py"))
br = importlib.util.module_from_spec(spec)
spec.loader.exec_module(br)

H = "ts,capacity,current_ua,voltage_uv,charge_uah,bat_temp,cpu0_khz,cpu3_khz,cpu7_khz,gpu_hz,bl_top,bl_bottom,suspends,app,usb_online,usb_ua,bat_status\n"
def line(ts, pct, ua, uah, app, st): return f"{ts},{pct},{ua},0,{uah},300,0,0,0,0,0,0,0,{app},0,0,{st}\n"

rows = [line(0, 100, 5000, 5000000, "menu", "Charging")]                      # on the charger
t, uah, pct = 30, 5000000, 100
for _ in range(120):                                                            # 1 h of Azahar at 1 A
    rows.append(line(t, pct, -1000000, uah, "azahar", "Discharging")); t += 30; uah -= 8333
rows.append(line(t, pct - 17, -150000, uah, "menu", "Discharging"))
t += 7200; uah -= 300000                                                        # 2 h asleep at 150 mA
rows.append(line(t, pct - 22, -400000, uah, "menu", "Discharging"))
rows.append("1791,cut-by-crash\n")                                              # a torn line is skipped
with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as f:
    f.write(H + "".join(rows))

r = br.report(br.load([f.name, "/nonexistent"]))
acts = {a["name"]: a for a in r["session"]["activities"]}
assert r["session"]["from_pct"] == 100 and r["session"]["to_pct"] == 78, r["session"]
assert set(acts) == {"Azahar (3DS)", "Sleep"}, acts
assert abs(acts["Azahar (3DS)"]["hours"] - 1.0) < 0.02 and abs(acts["Azahar (3DS)"]["ma"] - 1000) < 20, acts
assert acts["Sleep"]["hours"] == 2.0 and acts["Sleep"]["ma"] == 150, acts
assert abs(sum(a["pct"] for a in acts.values()) - 22) < 0.5, acts                  # the drop, split by mAh
assert r["now"]["hours_left"] > 0 and not r["now"]["charging"], r["now"]

# Charging now: the current charge, plus the discharge before it.
with open(f.name, "a") as g:
    g.write(line(t + 30, 78, 2000000, uah + 1000, "menu", "Charging") + line(t + 630, 82, 2000000, uah + 300000, "menu", "Charging"))
r = br.report(br.load([f.name]))
assert r["now"]["charging"] and r["charge"]["from_pct"] == 78 and r["charge"]["to_pct"] == 82, r
assert r["session"]["to_pct"] == 78 and "hours_left" not in r["now"], r
# A charger plugged in while asleep (the level rose across a sleep gap, both ends Discharging) starts a new session.
with open(f.name, "a") as g:
    g.write(line(t + 660, 82, -400000, uah + 300000, "menu", "Discharging") + line(t + 9000, 95, -400000, uah + 900000, "menu", "Discharging")
            + line(t + 9030, 95, -400000, uah + 896000, "retroarch", "Discharging") + line(t + 9060, 95, -400000, uah + 892000, "retroarch", "Discharging"))
r = br.report(br.load([f.name]))
assert r["session"]["from_pct"] == 95 and {a["name"] for a in r["session"]["activities"]} == {"Home", "RetroArch"}, r["session"]
# Newer logs: Home's launch record names the game (a PC app has no emulator process: app = its system).
with open(f.name + "2", "w") as g:
    g.write(H.rstrip() + ",game,core\n"
            + line(0, 95, -400000, 900000, "pc", "Discharging").rstrip() + ',"Gen1 Recomp, Red",\n'
            + line(30, 94, -400000, 896000, "retroarch", "Discharging").rstrip() + ',"Zelda ""LA""",gambatte\n'
            + line(60, 94, -400000, 892000, "menu", "Discharging").rstrip() + ',"",\n'
            + line(90, 94, -400000, 888000, "menu", "Discharging").rstrip() + ',"",\n')
names = {a["name"] for a in br.report(br.load([f.name + "2"]))["session"]["activities"]}
assert names == {"Gen1 Recomp, Red · PC", 'Zelda "LA" · RetroArch gambatte', "Home"}, names
os.unlink(f.name + "2")
assert br.report([]) == {"error": "no battery log yet"}
assert br.name("dolphin-emu-nog") == "Dolphin (GC/Wii)" and br.name("") == "Home"
os.unlink(f.name)
print("ok")
