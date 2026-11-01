# Sleep: deep sleep work and other distros

Moved out of the README on 2026-10-28. Device history: `thor/ayn_thor_pro.md`.

## Deep sleep plan (2026-10-14, updated 2026-10-15) — done 2026-10-16

**Done 2026-10-16: `cxsd`, `aosd` and `ddr` all count.** The CX blocker was audio: Armada's
[PR #723](https://github.com/armada-os/armada/pull/723) (Odin 3, SM8750, 7.8 mA asleep) found the ADSP's "AUDIO"
DRV holding CX through s2idle for LPASS macro/SoundWire/LPI votes and the board I2S clock. Ported as `9047`
(replaces `9040`). With it and the floor off, a 1 h lid-closed sleep spent 99.9% (3732 of 3736 s) in
CXSD/AOSD/DDR LPM at **~23–24 mA** (vs ~46 mA with the floor, ~100 mA before `0031`/`9045`/`0032`), with ~20 brief
wakes that went straight back down. Power button and RTC alarm both wake it from there; audio, UFS and Wi-Fi resume
fine. `suspend_floor` now defaults to off (`9037`; verified on a fresh boot 2026-10-16). Deferred for now: the remaining ~23 mA is board-level (panels,
touch, gamepad MCU, LEDs, Wi-Fi chip, PMIC); Armada's Odin 2 rail fixes are the first place to look.
Note: `clk_summary` in debugfs runtime-resumes every clock provider while it prints, so it shows the LPASS macros
active with `LPASS_HW_MACRO`/`DCODEC` enabled; read `/sys/kernel/debug/clk/<name>/clk_enable_count` instead.

Goal: full SoC sleep (`cxsd`/`ddr`, ideally `aosd`, counting in `/sys/kernel/debug/qcom_stats/`), as Android does
on this Thor (750+ CX/DDR collapses in 10 min, each one resumed). Today the PCIe suspend OPP (`0220`/`0221`)
keeps a small DDR vote in sleep; without it the first wake from DDR low power resets the SoC. Full notes:
`thor/ayn_thor_pro.md` (git-ignored), sections from "CXSD-only sleep experiment" on.

**Known (2026-10-14):**
- The reset is the SoC dropping PS_HOLD: XBL log (`9043`, `/sys/kernel/debug/xbl_log`) shows `Reset by PSHOLD`,
  `Hard Reset` and, only after the crash, `PON by RTC`. Not a TZ crash (`qcom_scm` download mode stays unused),
  not a power fault (PMIC PON registers match a normal reboot). DDR is re-initialised, so pstore stays empty.
- It hits the first wake event after DDR enters low power (alarm +60: kernel 117 s after suspend; +300: 163 s).
- Android's apps_rsc sleep/wake sets (RPMh trace, cmd-db names) match Linux's with the floor dropped, except
  LDO E1 and E3, which Android switches off in SLEEP and on in WAKE. Copying that alone (`0028`, since dropped)
  hung a normal sleep: their consumers (PCIe PHY, USB PHY, DSI/UFS PLL) aren't ready.
- Ruled out: ADSP/CDSP (stopped), UFS (already `spm_lvl=5`), MC4/SH5 (`9042`), Wi-Fi PDC table (`9038`),
  AOSD block (`9037`), GPU stale votes (fixed by `9039`), display RSC (empty TCSs, `9044` disabled).

**Found 2026-10-15: the floor only hid a live PCIe link.** The Wi-Fi link never powered down in sleep:
`pcie_ports=compat` left the root port without a driver, and the root port advertises Hot-Plug Capable, which
(without pciehp) keeps `pci_bridge_d3_possible()` false. So the port stayed in D0, D3cold was refused and
`qcom_pcie_suspend_noirq()` kept the controller, PHY, clocks and rails on. Fixed by `0031` (no `pcie_ports=compat`)
and `9045` (clear SltCap HPC/HPS). Now the root port goes to D3hot and the link retrains on every resume.
With the floor dropped (`suspend_floor=0`), 8 RTC sleeps (45 s–3 min) all resumed and `ddr` counted DDR LPM
for the first time (~55 of 60 s). Kettle has the same fix for SM8250 only (their `1140`); for Kettle's Thor:
[gist](https://gist.github.com/zmelumian972/3dc7b5a002f0564eada3f27b6d0d8807).

**Still 0 (2026-10-15): `cxsd`, `aosd`.** Ruled out as the CX blocker, each with a floor-off 60 s sleep:
LDO E1/E3 (`0032` turns them off in sleep, like Android; it no longer hangs now the link is down), USB (controller
and combo PHY unbound, `usb3_phy_gdsc` off), the apps RSC's own votes (RPMh trace: CX level 0, every BCM 0 in the
sleep set). Left: requesters the apps trace can't see (ADSP/CDSP votes, display RSC) and AOP QMP messages Android
sends that Linux doesn't. Stopping ADSP/CDSP isn't a valid test: DDR LPM stopped too, and the sound card was lost.

**Plan (port Android's suspend behaviour driver by driver, Qualcomm downstream source:
[OnePlusOSS/android_kernel_oneplus_sm8550](https://github.com/OnePlusOSS/android_kernel_oneplus_sm8550)):**
1. ~~Measure the ≥1 h unplugged sleep drain with `9039`.~~ Done 2026-10-15: 6.6 h at 102 mA and 1.9 h at 99 mA, with DDR at 200 MHz for the whole night. That is no better than the 100–135 mA baseline, so DDR clock was not the drain.
2. ~~PCIe.~~ Done (`0031`, `9045`): no port of `msm_pcie` needed. Android keeps the link in L1ss and hands it to
   the ADSP (`qcom,drv-name = "lpass"`, DRV over rpmsg); mainline now powers it fully down instead (D3cold).
3. ~~USB.~~ Not the CX blocker (see above). "HS-PHY not in L2" is noise: device mode, no cable. The combo PHY
   stays runtime-active (DP aux bridge), keeping `usb3_phy_gdsc` on while awake.
4. ~~Retry `0028`.~~ Done as `0032`: works, but CX still doesn't collapse.
5. ~~Floor-dropped overnight sleep.~~ Done 2026-10-16: `suspend_floor` defaults to off (`9037`).
6. ~~CX: replay the downstream drivers' AOP QMP messages.~~ Not needed: `9047` got CX to collapse.
7. ~~If still blocked, go to linux-arm-msm and AYN.~~ Not needed, for the same reason.
8. Still open: clean up whatever is no longer needed: test switches (`9037`/`9038`/`9042`), ftrace (`0027`), ramoops
   (`0029`/`0030`).

## Projects to learn from

Other ARM64 handheld distros that cover the Thor or SM8550. Check them before solving a Thor problem from scratch.

- **[Kettle Linux](https://github.com/kettlelinux/kettlelinux)** (BSD-3-Clause, early, single developer). SteamOS "deckard" aarch64 userspace + mainline **7.2** with a pinned patch stack. **Targets the AYN Thor and Odin 2 Portal** (SM8550) and the RP5. Worth reading:
  - kernel patches for panels, gamepad, LEDs, haptics, microSD, Wi-Fi and **s2idle suspend**. Compare with ours for sleep drain (DDR stuck at 1555 MHz asleep) and the rsinput resume stall.
  - Thor bottom screen: a Performance app (stats, trackpad, keyboard) plus a Plasma Mobile touch shell in Game Mode.
  - power controls: TDP, per-game fan curves, Auto TDP, **charge limit** (the basis of ours, `9018`–`9021`), refresh rate.
  - InputPlumber presents the pad as a Steam Deck controller; A/B atomic updates (RAUC).
- **[Armada](https://github.com/armada-os/armada)** (GPL-2.0+, ~1.9k stars, very active). Fedora bootc + device support derived from ROCKNIX; Steam Gaming Mode + KDE, FEX + Proton, OTA updates, Armada Control (power, fan, controller, calibration). Its SM8550 sleep work is [armada-packages #1](https://github.com/gh123man/armada-packages/pull/1) (RP6: #2954 ported to 7.0.11, UFS gate-race fix, charger-wake classifier, PCIe D3cold). Worth checking:
  - its sleep patches against ours.
  - how it sets up Steam + FEX + Proton and per-game compatibility settings.

### Findings from Kettle/Armada (2026-10-11)

Kettle's `kernel/patches/README.md` is a dense, per-patch log of SM8550 sleep/GPU fixes, many by gennro and
shared with Armada. These apply cleanly to our 7.2 tree (dry run) and aren't in it:

| Kettle | What it fixes | Relevance here |
|---|---|---|
| `1180` a6xx drop boot bus vote | GPU driver's boot DDR vote (680 MHz OPP, 16.5 GB/s) is never removed while the GPU is powered | **DDR at 4224 MHz with the screens on** (measured) |
| `1150` geni power down open ports | open UARTs (rsinput pad, BT) keep SE clocks, CX and QUP/NoC votes through s2idle | blocks CX collapse |
| `1160` ufs lane clocks once | leaked clock refs keep UFS clocks and XO on in s2idle (upstream bug) | blocks XO shutdown |
| `1291`–`1293` AudioReach suspend | an open PCM keeps the ADSP out of power collapse all night | sleep drain with a game's stream open |
| `1350`–`1352` a6xx GMU HFI fixes | HFI IRQ ate GMU replies: `GX_BW_PERF_VOTE timed out`, GPU freeze | our `fenced register write` / GMU errors |
| `1384`, `1385` | review fixes on top of our `1006` (geni) and `1010` (UFS) | correctness |

- `1170` (battmgr without a wakeup source) doesn't apply: it conflicts with our `9003`/`9005`.
- Kettle **dropped `0502`** (IPCC masked in suspend). With the mailbox masked, the charger stops drawing power about 5 min into s2idle. That's our "not charging after sleep" bug; `9005` already keeps IPCC live on the Thor.
- Kettle gamescope `0021`: a 120 Hz UI holds a 7.8 GB/s display vote, so DDR sits at 1555 MHz while idle. Asgard Home's top screen runs at 120 Hz.
- Still unexplained: the 1555 MHz DDR floor with both screens off and asleep (no Linux vote above 547 MHz).
- **Charger, compared (2026-10-11):**
  - **IPCC in sleep:** our `9005` (live on the Thor), Kettle (dropped `0502`) and Armada `0504` (live in s2idle, masked only for s2ram) agree.
  - **Charge limit:** our `9003` (AYN vendor property 16) is ignored by the firmware. Kettle `1190` / Armada `0903` set the fast-charge current (`BATT_CHG_CTRL_LIM`) instead, as `constant_charge_current`, and a daemon writes 0 at the limit. Read on the Thor too (4.68 A max). **Port this to replace `9003`.**
  - **battmgr wakeups:** Kettle `1170` drops battmgr's wakeup source; while charging, its notifications otherwise end s2idle within minutes. Unplugged sleeps here last hours, but sleep *while charging* is unmeasured. Needs a hand port (conflicts with `9003`).
  - **Unplug while asleep:** Armada `0519` clears the USB role for charger-only partners (otherwise a hang on unplug while asleep). Our `9005` fixed our reset differently (freezable wq).
  - **`95-thor-charge-fix`** logs "stuck" and rebinds UCSI after *every* unplugged wake (no partner looks the same as unplugged). With `9005` it may be obsolete.

## Sleep drain on 7.3 (2026-10-31)

**No 7.3 regression: the floor is ~21–25 mA on both kernels.** Every sleep of 30 min or more since 10-29
(fan-sleep fix), by battery voltage at sleep entry:

| Sleeps | Kernel | Voltage at entry | Drain |
|---|---|---|---|
| 10-29 21:28 | 7.2 | 4.00 V | 23 mA |
| 10-30 07:55, 08:49 | 7.2 | 4.31–4.32 V, right after a charge | 7 mA |
| 6 sleeps, 10-30 18:12 – 10-31 12:09 (incl. a 10.6 h overnight) | 7.3.1 | 3.80–4.13 V | 21–25 mA |

- `charge_counter` is the gauge's SoC estimate in 666 µAh steps (0.01 % of ~6.66 Ah), not a raw coulomb count.
  Near full after a charge it under-reads, so compare sleeps only at similar mid-range voltage, and only sleeps of
  45 min or more.
- The 7.3 suspend matches the 7 mA one on 7.2 event for event: the same rails switched, the same RPMh sleep/wake sets
  (598 vs 599 messages), CX/AOSS/DDR collapsed the whole sleep, `vdd_fan_5v0` off.
- 7.3 sometimes leaves s2idle and re-enters it (118 times in the overnight sleep, every ~5 min). A sleep with no re-entries
  still drew 22 mA, so they aren't the drain. Their source is unknown; `ipcc_0` (`IRQF_NO_SUSPEND` on the Thor, `9005`)
  is a guess. The sleep audit now writes `<start>.irq` (per-IRQ and wakeup-source deltas) to catch it.
- Rails still on in suspend: `vph_pwr`, `s6g_1p8`, `l15b_1p8` (WCD codec buck/io/rxtx, WCN vddio), `bob1` (codec
  mic-bias). Everything else switchable is off: SD, touch, pad MCU, WCN, UFS.
- **Unattended test sleeps:** `echo +900 > /sys/class/rtc/rtc0/wakealarm; systemd-run --on-active=3 systemctl suspend`.
  The RTC wakes it on time. `pm_debug_messages` isn't writable.

**Next (parked):** A/B the suspects one per sleep with the audit's `asgard.sleep_experiment`, with RTC-woken sleeps of
45 min or more at mid charge. Start with the audio codec (unbind it so `l15b`/`bob1` drop), then devices on `vph_pwr`
(speaker amps, LED controller, panels, USB-C chips).
