# spec: SET-1 SET-3 SET-4 SET-5 NET-1 NET-2 LOOK-2 LOOK-3 OLED-2 SND-4
# requires: file:build/AsgardOS-SM8550.aarch64/toolchain/usr/local/qt6/lib/libQt6Quick.so cmd:cmake
"""Run: python -I test_home_settings.py  (no Thor): Settings on the host, offscreen, driven by pad presses. On a host commands
are logged, not run, and a QML copy answers backend.exec with canned output, so this checks what is offered and what it
would run, never that a radio joins or a sound plays (device and human checks). SET-3: the confirmations and the offer, the
.tar-only listing is test_update_offer.py. SET-4: live changes and the row that says it needs a restart; whether every
setting that could apply live does is a human check. OLED-2: the switch, its re-send and the boot path; the driver is
test_ultra_black_driver.py. LOOK-3: Theme's timings; test_look_motion.py for what still moves with animations off. SND-4: the
settings and the code path; hearing them is a human check."""
import json
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "../../../tools/test"))
import home_harness as hh  # noqa: E402
from home_harness import CFG, Root  # noqa: E402

# Settings' sidebar: Start opens it on General; the rest are this many downs away, then A enters the list.
GENERAL, APPEARANCE, LIBRARY, ACHIEVEMENTS, HARDWARE, ABOUT, POWER = range(7)
AUDIO, DISPLAY, PERFORMANCE, NETWORK, STORAGE = range(5)   # rows of Hardware


def keys(*parts):
    return " ".join(p for p in parts if p)


def cat(n):
    return keys("start", *["down"] * n, "a")


def row(n, then="a"):
    return keys(*["down"] * n, then)


def hardware(n):
    return keys(cat(HARDWARE), row(n))


TOP_SCREEN = keys(hardware(DISPLAY), row(3))     # Display: split, brightness, screens off after, then Top screen


def copy(root, answers=None, probes=False):
    """Home's QML, with backend.exec answering `answers` ({regex: output}, logged like the real one) and Theme's values on
    the root (the dump shows the root's plain properties)."""
    out = f"{root.path}/.qml"
    shutil.rmtree(out, ignore_errors=True)
    shutil.copytree(f"{hh.SRC}/qml", out)
    text = open(f"{out}/Settings.qml").read()
    assert "backend.exec(" in text
    text = text.replace("backend.exec(", "fakeExec(")
    text = text.replace("    function close() {", """    readonly property var answers: %s
    function fakeExec(cmd, done) {
        console.log("exec: " + cmd)
        let out = ""
        for (const k in answers) if (new RegExp(k).test(cmd)) out = answers[k]
        if (done) Qt.callLater(done, out)
    }
    function close() {""" % json.dumps(answers or {}))
    open(f"{out}/Settings.qml", "w").write(text)
    if probes:
        text = open(f"{out}/Main.qml").read()
        old = "    property int tab: 0"
        assert old in text
        text = text.replace(old, '    readonly property int themeAnim: Theme.anim\n    readonly property int themeFade: Theme.fade\n'
                                 '    readonly property string themeSel: "" + Theme.selA + Theme.selB\n' + old)
        open(f"{out}/Main.qml", "w").write(text)
    return {"ASGARD_HOME_QML": out}


def press(root, sequence, answers=None, probes=False):
    return root.run(sequence, env=copy(root, answers, probes), ms=300)


def cfg(root, key):
    values = [line.split("=", 1)[1] for line in root.read(CFG).splitlines() if line.startswith(key + "=")]
    return values[-1] if values else None


# ---- SET-1: what Settings offers
OFFERS = {GENERAL: ["Device name", "Date & time", "Emulator options"], APPEARANCE: ["Accent colour", "Animations"],
          LIBRARY: ["Rescan library"], ACHIEVEMENTS: ["Account", "Hardcore mode"], ABOUT: ["Asgard OS", "Updates", "Debug"],
          POWER: ["Sleep", "Restart", "Power off"]}
with Root() as r:
    r.library()
    for n, titles in OFFERS.items():
        shown = r.run(cat(n), ms=300).window("Asgard Home")
        for title in titles:
            assert title in shown, title
    # Device name, with the on-screen keyboard: A types the first key (q), Start is Done.
    named = press(r, keys(cat(GENERAL), row(1), "a"))
    assert named.shows("Device name") and named.shows("q")
    press(r, keys(cat(GENERAL), row(1), "a", "start"))
    assert cfg(r, "system.hostname") == "TESTq"
    # Date and time zone
    dates = press(r, keys(cat(GENERAL), row(2)))
    assert dates.shows("Automatic date & time") and dates.shows("Time zone")
    assert "Europe" in press(r, keys(cat(GENERAL), row(2), row(1))).window("Asgard Home")
    zone = press(r, keys(cat(GENERAL), row(2), row(1), row(0)))       # UTC, the first row
    assert "restart tz-data" in zone.log and cfg(r, "system.timezone") == "UTC"
    # Emulator options per console
    consoles = press(r, keys(cat(GENERAL), row(3)))
    assert consoles.shows("GBA console") and consoles.shows("NDS console")
    assert press(r, keys(cat(GENERAL), row(3), row(0))).shows("Shaders, aspect ratio and more for GBA console")
    # Rescan: a second scan after the one at start
    assert press(r, cat(LIBRARY)).log.count("library:") == 1
    assert press(r, keys(cat(LIBRARY), row(1))).log.count("library:") == 2
    # RetroAchievements sign-in, hardcore
    signing = press(r, keys(cat(ACHIEVEMENTS), row(8)))               # 2 switches, 6 options, then Account
    assert signing.shows("RetroAchievements username")
    press(r, keys(cat(ACHIEVEMENTS), row(8), "a", "start", "a", "start"))
    assert cfg(r, "global.retroachievements.username") == "q" and cfg(r, "global.retroachievements.password") == "q"
    press(r, keys(cat(ACHIEVEMENTS), row(1)))
    assert cfg(r, "global.retroachievements.hardcore") == "1"
    # Debug, sleep
    assert press(r, keys(cat(ABOUT), row(4))).shows("Sleep audit")
    assert "shell: systemctl suspend" in press(r, keys(cat(POWER), row(0))).log

# ---- SET-3: restart and power off ask first. The update row: only with something to install, and it asks too.
with Root() as r:
    r.library()
    for n, title, command in ((1, "Restart", "systemctl reboot"), (2, "Power off", "systemctl poweroff")):
        asked = press(r, keys(cat(POWER), row(n)))
        assert asked.shows(f"{title} the Thor now?") and command not in asked.log
        cancelled = press(r, keys(cat(POWER), row(n), "b"))
        assert not cancelled.shows("the Thor now?") and command not in cancelled.log
        assert f"shell: {command}" in press(r, keys(cat(POWER), row(n), "a")).log
    assert not press(r, cat(ABOUT)).shows("Install update")
    update = {"ls /storage/.update": "/storage/.update/AsgardOS.tar"}
    assert press(r, cat(ABOUT), update).shows("Install update")
    asked = press(r, keys(cat(ABOUT), row(3)), update)
    assert asked.shows("installs AsgardOS.tar") and "systemctl reboot" not in asked.log
    assert "shell: systemctl reboot" in press(r, keys(cat(ABOUT), row(3), "a"), update).log

# ---- LOOK-2: the accents, aurora by default. SET-4: they apply at once. LOOK-3: timings, and the Animations switch.
with Root() as r:
    r.library()
    aurora = press(r, "", probes=True).props
    assert aurora["themeSel"] == "#47d1ff#8f7dff"
    seen = {}
    for name in ("sunset", "mint", "gold", "aurora"):                 # one step each, from the saved one
        res = press(r, keys(cat(APPEARANCE), "right"), probes=True)
        assert cfg(r, "asgard.accent") == name                        # saved, and in the running Home
        seen[name] = res.props["themeSel"]
    assert seen["aurora"] == aurora["themeSel"] and len(set(seen.values())) == 4
    assert aurora["themeAnim"] == "180" and aurora["themeFade"] == "320"
    off = press(r, keys(cat(APPEARANCE), row(1)), probes=True).props   # Animations: off, without a restart (SET-4)
    assert cfg(r, "asgard.animations") == "0" and off["themeAnim"] == "0" and off["themeFade"] == "0"
    assert press(r, "", probes=True).props["themeAnim"] == "0"        # a new start keeps it
QML = os.path.join(HERE, "../../asgard-home/src/qml")
assert "Behavior on scale { NumberAnimation { duration: Theme.anim" in open(f"{QML}/Tile.qml").read()   # the selection's move
assert open(f"{QML}/Backdrop.qml").read().count("NumberAnimation { duration: Theme.fade }") == 2        # the art's crossfade

# ---- SET-4: a change applies at once; the one that can't says so on its row
with Root() as r:
    r.library()
    assert press(r, cat(GENERAL)).shows("applies after a restart")    # Device name
    live = [(keys(hardware(AUDIO), row(2, "right")), "shell: volume 60", "audio.volume"),
            (keys(hardware(DISPLAY), row(1, "right")), "shell: brightness set 60", "display.brightness2"),
            (keys(hardware(DISPLAY), row(2, "right")), "shell: systemctl restart thor-idle-blank", "asgard.idle_blank")]
    for sequence, effect, key in live:
        assert effect in press(r, sequence).log, effect
        assert cfg(r, key), key

# ---- OLED-2: the switch in Settings re-sends it by cycling the screen; the driver and the boot path do the rest
with Root() as r:
    r.library()
    assert press(r, TOP_SCREEN).shows("OLED Ultra Black")
    res = press(r, keys(TOP_SCREEN, row(4)))
    assert cfg(r, "asgard.ultra_black") == "0"
    sent = re.search(r"shell: echo N > /sys/module/panel_chipone_icna35xx/parameters/ultra_black;(.*)", res.log)
    assert sent and sent.group(1).index("DSI-2 power off") < sent.group(1).index("DSI-2 power on")
boot = open(os.path.join(HERE, "thor-sway-rotate.sh")).read()
assert re.search(r"asgard\\\.ultra_black=.*\n.*> /sys/module/panel_chipone_icna35xx/parameters/ultra_black", boot)

# ---- NET-1
with Root() as r:
    r.library()
    r.write(CFG, "system.hostname=TEST\nbluetooth.enabled=1\nwifi.enabled=1\n")
    answers = {"wifictl list": "HomeNet\nCafe",
               "asgardos-bluetooth list": '<device id="AA:BB" name="Pad" connected="no"/>', "^usbgadget$": "disabled",
               "asgardos-bluetooth scan_list": '<device id="AA:BB" name="Pad" type="joystick"/>\n'
                                               '<device id="CC:DD" name="Headphones" type="audio"/>'}
    network = hardware(NETWORK)
    shown = press(r, network, answers).window("Asgard Home")
    for title in ("Wi-Fi", "Bluetooth", "USB connection", "SSH", "Samba", "Syncthing", "Tailscale", "ZeroTier", "WireGuard"):
        assert title in shown, title
    wifi = keys(network, "a")
    assert "HomeNet" in press(r, wifi, answers).window("Asgard Home")  # scanned on opening
    assert "exec: wifictl list" in press(r, keys(wifi, row(1)), answers).log
    typing = press(r, keys(wifi, row(2)), answers)                     # the first network: its password, on the keyboard
    assert typing.shows("Password for HomeNet")
    joined = press(r, keys(wifi, row(2), "a", "start"), answers)
    assert "exec: wifictl connect 'HomeNet' 'q'" in joined.log and cfg(r, "wifi.ssid") == "HomeNet"
    bt = keys(network, row(1))
    pairing = keys(bt, row(1))                                         # a list of what's nearby, already paired left out
    found = press(r, pairing, answers)
    assert "exec: asgardos-bluetooth scan_start" in found.log and "exec: asgardos-bluetooth scan_list" in found.log
    assert found.shows("Headphones") and "scan_stop" not in found.log
    assert "exec: asgardos-bluetooth trust CC:DD" in press(r, keys(pairing, row(1)), answers).log   # first row of the list
    assert "exec: asgardos-bluetooth scan_stop" in press(r, keys(pairing, "b"), answers).log        # leaving stops the scan
    assert "exec: asgardos-bluetooth scan_stop" in press(r, keys(pairing, "start"), answers).log    # so does closing Settings
    assert "Pad" in press(r, bt, answers).window("Asgard Home")
    failing = {**answers, "asgardos-bluetooth connect": "INFO: Attempting to connect...\nERROR: Couldn't connect. Is the device on and nearby?"}
    tried = press(r, keys(bt, row(2), "a"), failing)                   # Connect that fails says so, on the page
    assert "exec: asgardos-bluetooth connect AA:BB" in tried.log and tried.shows("Couldn't connect"), tried.log
    charged = {**answers, "asgardos-bluetooth list": '<device id="AA:BB" name="Pad" connected="yes" battery="64"/>'}
    assert press(r, bt, charged).shows("battery 64%")                  # a connected device's battery, in the list
    assert press(r, keys(bt, row(2)), charged).shows("64%")            # and on its page
    playing = {**answers, "asgardos-bluetooth list": '<device id="AA:BB" name="Phones" connected="yes" battery="" codec="LDAC"/>'}
    assert press(r, bt, playing).shows("Connected  ·  LDAC")           # a connected device's audio codec, in the list
    assert press(r, keys(bt, row(2)), playing).shows("Audio codec")    # and on its page
    choosing = {**answers, "asgardos-bluetooth list":
                '<device id="AA:BB" name="Phones" connected="yes" battery="" codec="LDAC" codecs="LDAC,AAC,SBC-XQ,SBC"/>'}
    assert "exec: asgardos-bluetooth codec AA:BB 'AAC'" in press(r, keys(bt, row(2), row(2, "right")), choosing).log
    assert "exec: asgardos-bluetooth codec AA:BB 'SBC'" in press(r, keys(bt, row(2), row(2, "left")), choosing).log  # wraps
    reopening = {**answers, "asgardos-bluetooth list":
                 '<device id="AA:BB" name="Phones" connected="yes" battery="" codec="" codecs="LDAC,AAC,SBC-XQ,SBC"/>'}
    assert press(r, keys(bt, row(2)), reopening).shows("Audio codec")  # mid-switch, no codec yet: the row stays
    asked = press(r, keys(bt, row(2), row(1)), answers)                # the device's page: Forget, which asks
    assert asked.shows("Forget Pad?") and "asgardos-bluetooth remove" not in asked.log
    assert "exec: asgardos-bluetooth remove AA:BB" in press(r, keys(bt, row(2), row(1), "a"), answers).log
    assert "usbgadget network" in press(r, keys(network, row(2, "right")), answers).log
    for n, key, unit in ((4, "ssh.enabled", "sshd"), (5, "samba.enabled", "smbd nmbd"), (6, "syncthing.enabled", "syncthing")):
        res = press(r, keys(network, row(n)), answers)
        assert cfg(r, key) == "1" and f"shell: systemctl start {unit}" in res.log, key

# ---- NET-2
with Root() as r:
    r.library()
    r.write(CFG, "system.hostname=TEST\ntailscale.up=1\nzerotier.up=1\n")
    network = hardware(NETWORK)
    tailscale = {"tailscale status": json.dumps({"BackendState": "NeedsLogin", "AuthURL": "https://login.tailscale.com/a/x1"})}
    page = press(r, keys(network, row(7)), tailscale)
    assert page.shows("login.tailscale.com/a/x1")                      # the sign-in link, on screen
    assert " up --hostname=" in press(r, keys(network, row(7), row(1)), tailscale).log
    zerotier = keys(network, row(8), row(2))                           # the switch, node ID, then Join a network
    ident = " ".join(["up"] + ["a"] * 16 + ["start"])                  # up: the digits row; 16 times the 1
    assert press(r, zerotier).shows("ZeroTier network ID")
    assert "join 1111111111111111" in press(r, keys(zerotier, ident)).log
    bad = press(r, keys(zerotier, "up a start"))                       # one character: not an ID, and said so
    assert bad.shows("Not a network ID") and " join " not in bad.log
    wireguard = {"wireguard": "F:home\nC:office:wireguard:activated"}
    page = press(r, keys(network, row(9)), wireguard)
    assert page.shows("home") and page.shows("office") and page.shows("/storage/.config/wireguard")
    imported = press(r, keys(network, row(9), "a"), wireguard)
    assert "nmcli connection import type wireguard file '/storage/.config/wireguard/home.conf'" in imported.log

# ---- SET-5: Storage, from df (the Thor's own answer, 2026-11-08): internal, SD card, games folder, system; no card
DF = "df -PkT"
with Root() as r:
    r.library()
    card = {DF: "/storage /dev/sda19 ext4 197797304 62741964 135038956 32% /storage\n"
                "/storage/games-external /dev/mmcblk0p1 exfat 488552448 156551680 332000768 32% /storage/games-external\n"
                "/flash /dev/sda18 vfat 2092928 1668644 424284 80% /flash\n"
                "/storage/roms /dev/mmcblk0p1 exfat 488552448 156551680 332000768 32% /storage/games-external"}
    assert press(r, cat(HARDWARE), card).shows("138 GB free inside  ·  340 GB free on the SD card")
    page = press(r, hardware(STORAGE), card)
    assert "exec: for p in /storage /storage/games-external /flash /storage/roms; do" in page.log
    for text in ("138 GB free of 203 GB  ·  64.2 GB used (32%)", "340 GB free of 500 GB  ·  160 GB used (32%)  ·  exfat",
                 "On the SD card  ·  /storage/roms", "434 MB free of 2.14 GB  ·  1.71 GB used (80%)"):
        assert page.shows(text), text
    # No card: games-external is a folder on /storage, so df names /storage as its mount; a path df can't read is empty
    none = {DF: "/storage /dev/sda19 ext4 197797304 62741964 135038956 32% /storage\n"
                "/storage/games-external /dev/sda19 ext4 197797304 62741964 135038956 32% /storage\n/flash \n"
                "/storage/roms /dev/sda19 ext4 197797304 62741964 135038956 32% /storage"}
    page = press(r, hardware(STORAGE), none)
    assert page.shows("No SD card in") and page.shows("On the internal storage") and not page.shows("System")
    assert press(r, cat(HARDWARE), none).shows("138 GB free inside  ·  No SD card")

# ---- SND-4: the settings; pw-play and no Qt Multimedia
with Root() as r:
    r.library()
    audio = hardware(AUDIO)
    shown = press(r, audio).window("Asgard Home")
    assert "Menu sounds" in shown and "Menu sound volume" in shown and "Charger sounds" in shown
    press(r, keys(audio, "a"))
    assert cfg(r, "asgard.sounds") == "0"
    press(r, keys(audio, row(1, "left")))
    assert cfg(r, "asgard.sounds_volume") == "25"
    press(r, keys(audio, row(7)))                                      # past the volume, the EQ and tone rows
    assert cfg(r, "asgard.charger_sounds") == "0"
home = os.path.join(HERE, "../../asgard-home/src")
backend = open(f"{home}/backend.cpp").read()
assert re.search(r'void Backend::sound\(.*?\{[^}]*getSetting\("asgard\.sounds", "1"\) == "1"\)\s*play\(name\)', backend, re.S)
assert re.search(r'getSetting\("asgard\.charger_sounds", "1"\) == "1"\)\s*play\(', backend)
assert re.search(r'void Backend::play\(.*?startDetached\("pw-play", \{"--volume=" \+ .*?asgard\.sounds_volume', backend, re.S)
linked = re.search(r"find_package\(Qt6 REQUIRED COMPONENTS (.*?)\)", open(f"{home}/CMakeLists.txt").read()).group(1)
assert "Multimedia" not in linked
for name in os.listdir(f"{home}/qml"):
    if name.endswith(".qml"):
        assert "import QtMultimedia" not in open(f"{home}/qml/{name}").read(), name
print("ok")
