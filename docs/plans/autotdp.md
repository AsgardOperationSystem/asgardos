# AutoTDP plan (2026-10-29)

Goal: hold a game's target FPS at the lowest CPU/GPU clocks. The Snapdragon has no TDP knob, so "TDP" here means
per-cluster `scaling_max_freq` and the GPU devfreq `max_freq` (today a fixed ~75 % CPU cap, `40-thor-cpu-cap.sh`).

## Done

- **FPS source for every app** (`0bc6150`): sway counts each window's new frames (`sway-100.02`, `frames` in
  `get_tree`); the AYN panel shows the busiest window's rate. Verified on the Thor: `current_fps()` = 120 on Home.
  It counts presented frames, not an emulator's internal rate.

## Open

1. **Home redraws while idle.** Measured over 2 s on Home, untouched: bottom window (`Asgard Home (Bottom)`) ~116 fps
   (the full 120 Hz), top ~39 fps. An idle menu should be near 0. Find what keeps animating (a QML animation, a
   timer, a running `Image`/`AnimatedImage`) and stop it when nothing changes. Battery drain on its own, and it
   skews item 2.
   Check: `SWAYSOCK=/var/run/0-runtime-dir/sway-ipc.0.sock swaymsg -t get_tree -r`, read `frames` twice, 2 s apart.
2. **Panel FPS may read Home instead of the game.** `thor_panel.py:current_fps()` takes the busiest window. If
   Home's bottom window keeps drawing at 120 during a game (dual-screen games keep DSI-1 on), the panel shows 120,
   not the game's rate. Check: open the panel in a game with the bottom screen on and compare with the
   emulator's own counter. If it's wrong, skip `asgard-home` windows while a game runs (`/run/thor-playing.txt`).
3. **AutoTDP itself** (`d2ec2f0`, untested on the Thor): game options `cpu_cap_<type>` / `gpu_cap` = Auto run
   `asgard-autotune.py`, which steps those ceilings down while the game holds its rate and up when it drops (log:
   `/var/log/asgard-autotune.log`). Its FPS input has the same busiest-window caveat as item 2. To test: Auto on Big
   cores, Prime core and GPU in a Switch and a PS2 game; watch `dmesg` for `a6xx_gmu` / `hangcheck` /
   `dpu_encoder_frame_done_timeout`, compare `power_now` with stock.

## Side note: Go writes its cache into the tree

A Go package's build left `.cache/go-build` (~300 MB) and `.config/go` in the repo root (2026-10-30 19:32), so it
ran with `HOME` = the tree. Now git-ignored. Better: find that package and point `GOCACHE` / `GOENV` (or `HOME`)
into `build/`, so nothing is written outside it.
