#!/bin/sh
# Thor: ROCKNIX regenerates the sway config every boot and leaves the bottom panel (DSI-1)
# unrotated (portrait 1080x1240); it's a landscape panel. A transform set while DSI-1 is
# powered off doesn't reliably stick, so also re-apply it whenever a dual-screen window
# powers the panel on (this rule lands after ROCKNIX's own "output DSI-1 power on" rule).
C=/storage/.config/sway/config
grep -q '^output DSI-1 transform' "$C" || echo 'output DSI-1 transform 90' >> "$C"
grep -q '^# thor-rotate' "$C" || printf '%s\n' '# thor-rotate' \
  'for_window [title=".*(Secondary|\[w2\]|Sub|Bottom|Screen 2|GamePad).*"] output DSI-1 transform 90' >> "$C"
# A frontend is a plain tiled window, so a game window opening next to it got half the screen (2026-10-09).
# Fullscreen every new top-screen window except lowerdeck / second-screen windows.
# ROCKNIX's lowerdeck (bottom-screen companion, e.g. for GB/GBA) isn't matched by the title rule above.
# Its rule leaves focus on DSI-1, so RetroArch's re-created window after Close Content opened down there.
# Rotate 1.5 s later: an immediate transform raced ROCKNIX's power-on/vertical-check modeset and the top
# panel's DPU kickoff timed out (frame done timeout, garbled colours until reboot), 2026-10-09.
# vertical-check later re-focuses DSI-1 asynchronously, so also pin RetroArch's bare menu window (title exactly
# "RetroArch", i.e. after Close Content) to the top screen. Running games have longer titles (DS layouts untouched).
grep -q '^# thor-lowerdeck' "$C" || printf '%s\n' '# thor-lowerdeck' \
  'for_window [app_id="lowerdeck"] exec "sleep 1.5; swaymsg output DSI-1 transform 90"' \
  'for_window [app_id="lowerdeck"] focus output DSI-2' \
  'for_window [app_id="com.libretro.RetroArch" title="^RetroArch$"] move window to output DSI-2, focus' >> "$C"
# Second-screen windows (melonDS [w2], lowerdeck) request fullscreen while still on the top workspace and steal
# it from the game's main window (melonDS then shows its menu bar). `assign` places them on DSI-1 at creation.
grep -q '^# thor-assign' "$C" || printf '%s\n' '# thor-assign' \
  'assign [title="^\[w2\]"] output DSI-1' \
  'assign [app_id="lowerdeck"] output DSI-1' >> "$C"
# Touches on the bottom screen move sway's pointer; with the default focus_follows_mouse the controller focus then
# drifted to the (often empty, powered-off) bottom output and the frontend stopped seeing the d-pad (2026-10-09).
grep -q '^# thor-focus' "$C" || printf '%s\n' '# thor-focus' 'focus_follows_mouse no' 'mouse_warping none' >> "$C"
grep -q '^# thor-fullscreen' "$C" || printf '%s\n' '# thor-fullscreen' \
  'for_window [app_id="^(?!lowerdeck$).*" title="^(?!.*(Secondary|\[w2\]|Sub|Bottom|Screen 2|GamePad)).*"] fullscreen enable' >> "$C"
# Asgard Home's bottom window: ROCKNIX's "Bottom" rules move it to DSI-1 and power the panel on; fill it.
grep -q '^# asgard-bottom' "$C" || printf '%s\n' '# asgard-bottom' 'for_window [title="^Asgard Home \(Bottom\)$"] fullscreen enable' >> "$C"
# Each Asgard Home window on its own panel, every time it maps (start, and after every game/tool, when it is
# shown again). A new window otherwise opens on the focused output: with focus on the bottom screen the top
# window landed on DSI-1 behind the bottom one, and the top screen stayed dark (2026-10-10).
grep -q '^# asgard-assign' "$C" || printf '%s\n' '# asgard-assign' \
  'assign [title="^Asgard Home$"] output DSI-2' \
  'assign [title="^Asgard Home \(Bottom\)$"] output DSI-1' >> "$C"
exit 0
