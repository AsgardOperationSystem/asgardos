#!/bin/sh
# SPDX-License-Identifier: GPL-2.0
# Copyright (C) 2024-present ROCKNIX (https://github.com/ROCKNIX)

[ -z "$SYSTEM_ROOT" ] && SYSTEM_ROOT=""
[ -z "$BOOT_ROOT" ] && BOOT_ROOT="/flash"
[ -z "$BOOT_PART" ] && BOOT_PART=$(df "$BOOT_ROOT" | tail -1 | awk {' print $1 '})

# identify the boot device
if [ -z "$BOOT_DISK" ]; then
  case $BOOT_PART in
    /dev/mmcblk*) BOOT_DISK=$(echo $BOOT_PART | sed -e "s,p[0-9]*,,g");;
  esac
fi

# mount $BOOT_ROOT rw
mount -o remount,rw $BOOT_ROOT

if [ -d "$SYSTEM_ROOT/usr/share/bootloader/rocknix_abl" ]; then
  mkdir -p $BOOT_ROOT/rocknix_abl
  echo "Copying the ROCKNIX ABL files to $BOOT_ROOT/rocknix_abl..."
  cp $SYSTEM_ROOT/usr/share/bootloader/rocknix_abl/* $BOOT_ROOT/rocknix_abl
fi

# AsgardOS: OpenABL's Boot Loader Spec layout next to KERNEL, so either bootloader starts this system.
if [ -f "$SYSTEM_ROOT/usr/share/bootloader/Image.gz" ]; then
  echo "Updating the Boot Loader Spec kernel, device trees and entry..."
  cp -f $SYSTEM_ROOT/usr/share/bootloader/Image.gz $BOOT_ROOT/
  mkdir -p $BOOT_ROOT/dtbs $BOOT_ROOT/loader/entries
  cp -f $SYSTEM_ROOT/usr/share/bootloader/dtbs/* $BOOT_ROOT/dtbs/
  cp -f $SYSTEM_ROOT/usr/share/bootloader/loader/entries/* $BOOT_ROOT/loader/entries/
fi

# AsgardOS: an update never flashes abl_a/abl_b. ROCKNIX ran updateabl here, which rewrites both slots whenever
# they differ from the bundled ABL. Flash it by hand (updateabl) after checking the backup in thor/rocknix-abl/.

### REMOVE IN THE FUTURE ###
# cleanup old boot files
[ -d "$BOOT_ROOT/boot" ] && rm -rf "$BOOT_ROOT/boot"
[ -d "$BOOT_ROOT/EFI" ] && rm -rf "$BOOT_ROOT/EFI"
# end

# mount $BOOT_ROOT ro
sync
mount -o remount,ro $BOOT_ROOT

echo "UPDATE" > /storage/.boot.hint
