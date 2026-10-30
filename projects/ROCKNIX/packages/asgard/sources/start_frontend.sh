#!/bin/bash
# Started by essway.service. There is no other frontend: ROCKNIX ES and ES-DE aren't in the image.
# exec, so essway's MainPID carries the full environment (Thor Panel reads it) and Restart=always restarts a crash.
. /etc/profile

# Timezone + quirk variables for every later process (what ROCKNIX ES's es_settings did before ES started).
TZ=$(get_setting system.timezone)
echo -n "TIMEZONE=${TZ}" > /storage/.cache/timezone
echo -n "${TZ}" > /storage/.cache/system_timezone
systemctl restart tz-data.service
# Settings > General > Date & time: "Automatic date & time" off. timesyncd is enabled in the read-only image.
[ "$(get_setting asgard.ntp)" = "0" ] && systemctl stop systemd-timesyncd
for VARIABLE in $(grep _ /etc/profile.d/999-export | sed 's/export//g; s/^\W//g; s/\\//g'); do
  systemctl import-environment "${VARIABLE}"
done
# ponytail: no system.language locale generation (ES did it for its translations); add with the frontend's i18n.
export SDL_AUDIODRIVER=pulseaudio
# A UTF-8 locale for Home and every game/app it starts (non-ASCII names in Terminal, Files...). glibc has no
# built-in C.UTF-8 and the image ships no compiled locales (ROCKNIX's SM8550 busybox drops locale.service), so
# compile it once into /storage (~1 s, 76 KB). localedef exits 1 on harmless warnings.
export LOCPATH=/storage/.cache/locpath LANG=C.UTF-8
[ -d "$LOCPATH/C.UTF-8" ] || { mkdir -p "$LOCPATH"; I18NPATH=/usr/share/i18n localedef --quiet -i POSIX -f UTF-8 "$LOCPATH/C.UTF-8"; }

exec /usr/bin/asgard-home >> /var/log/asgard-frontend.log 2>&1
