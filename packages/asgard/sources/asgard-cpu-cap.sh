#!/bin/bash
# The Asgard menu's CPU profile per core type (Settings > Hardware > Performance), while in Home only: run at boot
# (090-asgard-tuning), from Settings, and by asgard-perf-profile.sh after a game (games start at stock instead):
#   asgard.cpu_cap.<type>     clock cap, % of the cluster's top clock (25-100), or "off": the cluster's cores
#                             offline (CPU0 stays: the kernel can't offline it)
#     little  3x Cortex-A510 (policy0, CPU0-2)      cap default 90
#     mid     2x A715 + 2x A710 (policy3, CPU3-6)   cap default 75
#     prime   1x Cortex-X3 (policy7, CPU7)          cap default 75
# At least one type stays enabled: with all three off, the prime core is kept. The older on/off asgard.cpu_cap=0 means
# no cap (100 for all). The highest frequency the cluster supports at or under the cap is set as scaling_max_freq.
# Every core comes online first and the GPU goes back to uncapped, so this also undoes a game's profile
# (asgard-perf-profile.sh restore).
#   asgard-cpu-cap.sh
. /etc/profile.d/001-functions
. /usr/share/asgard/asgard-cpu-lib.sh
OLD=$(get_setting asgard.cpu_cap)
autotune_stop   # a game's (asgard-perf-profile.sh restore runs this)
for t in $TYPES; do online_type "$t" 1; done
off=""
for t in $TYPES; do
  dflt=$(default_cap "$t"); [ "$OLD" = "0" ] && dflt=100
  pct=$(get_setting "asgard.cpu_cap.$t")
  [ "$pct" = autotune ] && pct=""   # games only: the menu doesn't offer it
  if [ "$pct" = off ]; then off="$off $t"; else set_cap "$t" "${pct:-$dflt}"; fi
done
set_gpu_cap 100   # games set their own (gpu_cap); the menu doesn't cap the GPU
offline_types "$off"
write_affinity
