#!/usr/bin/env python3
"""steam-pad-profile.py on|off: while Steam runs, Home (Guide) opens Asgard Home's in-game menu, not Steam's.

InputPlumber's profile for the pad gets one more mapping (Guide -> F20 on its keyboard, which Steam ignores and
thor_ayn_button.py turns into the menu) on "on"; the profile from before is kept in /run and loaded back on "off".
start_steam.sh calls it around gamescope. The menu's Steam overlay / Quick Access entries inject Guide through
InputPlumber's SendButtonChord, which skips the profile, so they reach Steam as a real Home press.
"""
import json
import os
import subprocess
import sys

DEV = ["org.shadowblip.InputPlumber", "/org/shadowblip/InputPlumber/CompositeDevice0",
       "org.shadowblip.Input.CompositeDevice"]
SAVED = "/run/asgard-ip-profile.yaml"
MARK = "Home opens the Asgard menu"
OLD_MARKS = ("Home opens Quick Access",)   # a profile saved by an older version of this script
HOME_TO_QAM = f"""- name: {MARK}
  source_event:
    gamepad:
      button: Guide
  target_events:
  - keyboard: KeyF20
"""


def call(method, *args):
    return subprocess.run(["busctl", "call", "--json=short", *DEV, method, *args],
                          capture_output=True, text=True, check=True).stdout


def with_home_to_qam(yaml):
    """The profile with the Guide -> QuickAccess mapping first."""
    if MARK in yaml:
        return yaml
    head, sep, rest = yaml.partition("mapping:\n")
    return head + sep + HOME_TO_QAM + rest if sep else yaml + "mapping:\n" + HOME_TO_QAM


def main(mode):
    if mode == "on":
        cur = json.loads(call("GetProfileYaml"))["data"][0]
        if MARK not in cur and not any(m in cur for m in OLD_MARKS):
            open(SAVED, "w").write(cur)
        call("LoadProfileFromYaml", "s", with_home_to_qam(cur))
    elif mode == "off" and os.path.exists(SAVED):
        call("LoadProfileFromYaml", "s", open(SAVED).read())
        os.remove(SAVED)


if __name__ == "__main__":
    y = "version: 1\nkind: DeviceProfile\nname: Default\nmapping:\n- name: X\n"
    assert with_home_to_qam(y).index(MARK) < with_home_to_qam(y).index("name: X")
    assert with_home_to_qam(with_home_to_qam(y)) == with_home_to_qam(y)
    try:
        main(sys.argv[1] if len(sys.argv) > 1 else "")
    except (subprocess.CalledProcessError, OSError, KeyError, ValueError) as e:
        print("steam-pad-profile:", e, file=sys.stderr)   # never block Steam from starting
