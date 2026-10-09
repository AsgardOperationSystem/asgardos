#!/bin/bash
# Copy asgard.yml onto an image's boot partition (/flash) so the card boots with your Wi-Fi, logins and keys.
# The published image stays generic; only your local copy carries secrets.
#   ./inject-config.sh <image.img[.gz]> [asgard.yml]  ->  <image>-configured.img (don't share it)
# Alternative: flash the plain image, then copy asgard.yml to the card's FAT partition from any PC.
set -euo pipefail
IMG=$1; YML=${2:-asgard.yml}
[ -f "$YML" ] || { echo "no $YML (start from asgard.yml.example)"; exit 1; }
OUT="${IMG%.gz}"; OUT="${OUT%.img}-configured.img"
case "$IMG" in *.gz) zcat "$IMG" > "$OUT" ;; *) cp "$IMG" "$OUT" ;; esac
START=$(sfdisk -J "$OUT" | python3 -I -c 'import json,sys; print(json.load(sys.stdin)["partitiontable"]["partitions"][0]["start"])')
mcopy -o -i "$OUT@@$((START * 512))" "$YML" ::asgard.yml
chmod 600 "$OUT"
echo "$OUT"
