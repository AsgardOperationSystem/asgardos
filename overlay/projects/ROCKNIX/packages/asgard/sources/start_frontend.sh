#!/bin/bash
# Started by essway.service. There is no other frontend: ROCKNIX ES and ES-DE aren't in the image.
# exec, so essway's MainPID carries the full environment (Thor Panel reads it) and Restart=always restarts a crash.
. /etc/profile

# Timezone + quirk variables for every later process (what ROCKNIX ES's es_settings did before ES started).
TZ=$(get_setting system.timezone)
echo -n "TIMEZONE=${TZ}" > /storage/.cache/timezone
echo -n "${TZ}" > /storage/.cache/system_timezone
systemctl restart tz-data.service
for VARIABLE in $(grep _ /etc/profile.d/999-export | sed 's/export//g; s/^\W//g; s/\\//g'); do
  systemctl import-environment "${VARIABLE}"
done
# ponytail: no system.language locale generation (ES did it for its translations); add with the frontend's i18n.
export SDL_AUDIODRIVER=pulseaudio
# Qt needs a UTF-8 locale; ROCKNIX ES's es_settings set LANG, nothing does now. C.UTF-8 is built into glibc.
export LANG=${LANG:-C.UTF-8}

exec /usr/bin/asgard-home >> /var/log/asgard-frontend.log 2>&1
