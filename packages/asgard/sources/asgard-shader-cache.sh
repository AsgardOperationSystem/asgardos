#!/bin/bash
# Delete one game's compiled shader cache (Thor Settings > game > Delete shader cache): the emulator rebuilds it on
# demand. A cache that grew huge makes a game start on a black screen for minutes, compiling it all (Azahar, 2026-10-31).
#   asgard-shader-cache.sh <system> <rom path>   prints what it deleted, or why not
# 3ds (Azahar): <title ID>_* in shaders/<api>/<kind>/, the title ID from the NCSD header (media ID, offset 0x108).
# switch (Eden): shader/<title ID>/, the title ID from the file name's [0100...].
sys=$1 rom=$2
case "$sys" in
  3ds)
    [ -f "$rom" ] || { echo "ROM not found"; exit 1; }
    [ "$(dd if="$rom" bs=1 skip=256 count=4 2>/dev/null)" = NCSD ] || { echo "Not a .3ds/.cci image: title ID unknown"; exit 1; }
    tid=$(od -An -tx8 -j 264 -N8 "$rom" | tr -d ' ' | tr a-f A-F)
    files=$(ls /storage/.config/azahar/shaders/*/*/"$tid"_* 2>/dev/null)
    ;;
  switch)
    tid=$(basename "$rom" | grep -o '\[0100[0-9A-Fa-f]\{12\}\]' | head -1 | tr -d '[]' | tr A-F a-f)
    [ -n "$tid" ] || { echo "No [title ID] in the file name"; exit 1; }
    files=$(ls -d /storage/.local/share/eden/shader/"$tid" 2>/dev/null)
    ;;
  *) echo "Not supported for $sys"; exit 1 ;;
esac
[ -n "$files" ] || { echo "No shader cache for $tid"; exit 0; }
size=$(du -shc $files | tail -1 | cut -f1)
rm -rf $files
echo "Deleted $size ($tid)"
