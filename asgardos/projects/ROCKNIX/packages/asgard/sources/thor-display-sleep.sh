#!/bin/sh
# Thor: panels off across suspend, and after resume turn back on only the outputs that
# were on before (ROCKNIX keeps the bottom panel off unless a dual-screen game uses it).
# usage: thor-display-sleep.sh pre|post
export SWAYSOCK=/run/0-runtime-dir/sway-ipc.0.sock
STATE=/run/thor-display-sleep.on
case "$1" in
  pre)
    swaymsg -t get_outputs -r | python3 -c 'import json,sys; print("\n".join(o["name"] for o in json.load(sys.stdin) if o.get("power")))' > "$STATE"
    swaymsg "output * dpms off" >/dev/null 2>&1
    ;;
  post)
    if [ -s "$STATE" ]; then
      while read -r out; do swaymsg "output $out dpms on" >/dev/null 2>&1; done < "$STATE"
    else
      swaymsg "output DSI-2 dpms on" >/dev/null 2>&1   # no record: at least the main screen
    fi
    # Controller focus back to the top screen unless a window lives on the bottom one (e.g. a DS game).
    swaymsg -t get_tree -r | python3 -c 'import json,sys
def w(n, o=None):
    o = n.get("name") if n.get("type") == "output" else o
    return (o == "DSI-1" and bool(n.get("pid"))) or any(w(c, o) for c in n.get("nodes", []) + n.get("floating_nodes", []))
sys.exit(0 if w(json.load(sys.stdin)) else 1)' || swaymsg "focus output DSI-2" >/dev/null 2>&1
    ;;
esac
exit 0
