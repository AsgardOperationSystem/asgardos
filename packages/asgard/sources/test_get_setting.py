#!/usr/bin/env python3
# spec: CFG-9
# requires: cmd:bash file:packages/asgardos/profile.d/001-functions
"""get_setting itself, run from the 001-functions that ships: SPEC section 4's five steps in order, an empty value counts
as unset, and a key only matches whole. This is the order half of CFG-9; that no other code does its own lookup is
test_game_option_lookup.py."""
import os
import re
import subprocess
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
FUNCTIONS = open(os.path.join(HERE, "../../asgardos/profile.d/001-functions")).read()
get_setting = re.search(r"^function get_setting\(\) \{.*?^\}", FUNCTIONS, re.M | re.S).group(0)
# The image's bash is 5.3, where BASH_REMATCH can be local. An older host bash leaves that local empty, so don't declare it.
get_setting = get_setting.replace("local -a keys=() BASH_REMATCH", "local -a keys=()")

GAME, SYSTEM, NAMED, BARE, GLOBAL = ('3ds["Pokemon X.3ds"].ratio=game', "3ds.ratio=system", "system.ratio=named",
                                     "ratio=bare", "global.ratio=global")
X = ("ratio", "3ds", "Pokemon X.3ds")
TABLE = [
    # what system.cfg holds, what's asked, the answer
    ([GAME, SYSTEM, NAMED, BARE, GLOBAL], X, "game"),
    ([SYSTEM, NAMED, BARE, GLOBAL], X, "system"),
    ([NAMED, BARE, GLOBAL], X, "named"),
    ([BARE, GLOBAL], X, "bare"),
    ([GLOBAL], X, "global"),
    ([], X, ""),
    # the order is the scope's, not the file's
    ([GLOBAL, BARE, NAMED, SYSTEM, GAME], X, "game"),
    ([GLOBAL, BARE, NAMED, SYSTEM], X, "system"),
    ([GLOBAL, BARE, NAMED], X, "named"),
    ([GLOBAL, BARE], X, "bare"),
    # empty is unset, at every step: it inherits from the next one
    (['3ds["Pokemon X.3ds"].ratio=', SYSTEM], X, "system"),
    (['3ds["Pokemon X.3ds"].ratio=', "3ds.ratio=", NAMED], X, "named"),
    (['3ds["Pokemon X.3ds"].ratio=', "3ds.ratio=", "system.ratio=", BARE], X, "bare"),
    (['3ds["Pokemon X.3ds"].ratio=', "3ds.ratio=", "system.ratio=", "ratio=", GLOBAL], X, "global"),
    (['3ds["Pokemon X.3ds"].ratio=', "3ds.ratio=", "system.ratio=", "ratio=", "global.ratio="], X, ""),
    # another game or system isn't this one
    (['3ds["Other.3ds"].ratio=other', "n64.ratio=other", GLOBAL], X, "global"),
    # fewer arguments skip those steps, and only those
    ([GAME, SYSTEM, BARE], ("ratio", "3ds"), "system"),
    ([GAME, SYSTEM, BARE], ("ratio",), "bare"),
    ([GAME, SYSTEM, NAMED], ("ratio",), "named"),
    # whole keys only, not a comment or a longer key
    (["#ratio=comment", "myratio=prefix", "ratio2=suffix", "3ds.ratio.x=child", GLOBAL], X, "global"),
    # a ROM name is text, not a pattern
    (['3ds["Zelda (USA) [!].3ds"].ratio=zelda', SYSTEM], ("ratio", "3ds", "Zelda (USA) [!].3ds"), "zelda"),
    (['3ds["ZeldaX(USA).3ds"].ratio=other', SYSTEM], ("ratio", "3ds", "Zelda.(USA).3ds"), "system"),
]

with tempfile.TemporaryDirectory() as tmp:
    cfg = os.path.join(tmp, "system.cfg")
    script = get_setting + '\nJ_CONF=$1; shift\nget_setting "$@"\n'

    def ask(*args):
        run = subprocess.run(["bash", "-c", script, "bash", cfg, *args], capture_output=True, text=True, check=True)
        return run.stdout.rstrip("\n")

    for lines, asked, want in TABLE:
        with open(cfg, "w") as f:
            f.write("".join(line + "\n" for line in lines))
        got = ask(*asked)
        assert got == want, f"{lines} {asked}: got {got!r}, want {want!r}"

    os.remove(cfg)
    assert ask(*X) == "", "a missing system.cfg isn't unset"

print("get_setting: ok")
