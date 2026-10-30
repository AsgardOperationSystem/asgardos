# Shared by asgard-cpu-cap.sh (global), asgard-perf-profile.sh (per game) and asgard-screens-off.sh: the Thor's
# three core types, their caps, taking them offline, and the launchers' core pinning.
CPU=/sys/devices/system/cpu
TYPES="little mid prime"
policy_of() { case $1 in little) echo 0 ;; mid) echo 3 ;; prime) echo 7 ;; esac; }
cpus_of()   { case $1 in little) echo "1 2" ;; mid) echo "3 4 5 6" ;; prime) echo 7 ;; esac; }   # offlinable: CPU0 stays
default_cap() { case $1 in little) echo 90 ;; *) echo 75 ;; esac; }

online_type() { for n in $(cpus_of "$1"); do echo "$2" > $CPU/cpu$n/online; done; }

# set_cap <type> <percent 25-100>: the highest supported frequency at or under that share of the top clock
set_cap() {
  local P=$CPU/cpufreq/policy$(policy_of "$1") pct=$2 want khz
  [ -d "$P" ] || return 0
  [ "$pct" -ge 25 ] 2>/dev/null || pct=25
  [ "$pct" -le 100 ] || pct=100
  want=$(( $(cat $P/cpuinfo_max_freq) * pct / 100 ))
  khz=$(tr ' ' '\n' < $P/scaling_available_frequencies | awk -v w="$want" '$1 && $1 <= w && $1 > b {b = $1} END {print b}')
  echo "${khz:-$(cat $P/cpuinfo_min_freq)}" > $P/scaling_max_freq
}

# offline_types "<types>": take them offline, but never all three (the prime core is kept then). Caps first: a
# cluster's policy directory goes away with its last core.
offline_types() {
  local types=$1
  [ "$(echo $types | wc -w)" -ge 3 ] && types=$(echo "$types" | tr ' ' '\n' | grep -v '^prime$')
  for t in $types; do online_type "$t" 0; done
}

# Launchers pin emulators with $FAST_CORES ("taskset -c 3-7") / $SLOW_CORES ("taskset -c 0-2"); a mask with no
# online CPU makes taskset fail. Override them with the online cores (after ROCKNIX's 040-affinity), or drop the
# override when every core is online.
write_affinity() {
  local f=/storage/.config/profile.d/041-asgard-affinity on fast slow n
  on=$(cat $CPU/online)
  if [ "$on" = 0-7 ]; then rm -f $f; return; fi
  for n in 3 4 5 6 7; do [ "$(cat $CPU/cpu$n/online)" = 1 ] && fast="$fast${fast:+,}$n"; done
  for n in 0 1 2; do [ "$n" = 0 ] || [ "$(cat $CPU/cpu$n/online)" = 1 ] && slow="$slow${slow:+,}$n"; done
  printf '# Asgard: cores online now (asgard-cpu-lib.sh write_affinity); removed when all are\nFAST_CORES="taskset -c %s"\nSLOW_CORES="taskset -c %s"\n' \
    "${fast:-$slow}" "$slow" > $f
}
