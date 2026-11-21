import QtQuick
import "stickcal.js" as StickCalJs

// Settings on the bottom screen, in iiSU's layout: a light glass panel, categories on the left, grouped cards of
// rows on the right (icon, title, subtitle, then a chevron, a switch or a value). D-pad + A/B or touch.
// Rows: kind "link" (A opens a sub-page or runs open()), "toggle" (A flips), "choice" (A / left / right step),
// "action" (A runs), "info" (read only). Values live in system.cfg via backend.getSetting/setSetting.
Item {
    id: settings
    property bool open: false
    property int rev: 0                      // bumped after every change: rows re-read their values
    property int cat: 0
    property string zone: "side"             // "side" (categories) or "list" (rows)
    property int row: 0
    property var stack: []                   // sub-pages: [{title, build}]
    property var live: ({})                  // command results (Wi-Fi, Bluetooth, USB...): key -> value
    // Drawn as the in-game menu (MENU-6): its dark backdrop, its header with "B  back", no categories, and each row one
    // of its big tiles. Only the look: the pages and what they run are the same.
    property bool menuStyle: false
    readonly property int rowH: menuStyle ? 150 : 112
    readonly property int rowGap: menuStyle ? 18 : 0            // between rows of a group
    readonly property int groupGap: menuStyle ? 18 : 22
    signal closed()

    readonly property color ink: "#2a2b3d"
    readonly property color inkDim: "#6f7186"
    readonly property color card: "#fbfbfd"
    readonly property color line: "#e4e5ec"

    // Y on a game: Settings opened straight on that game's page.
    function showGame(g) { show(); cat = 2; stack = [{ title: g.name, build: () => gamePage(g), closeOnBack: true }]; zone = "list" }
    // Select on a game > Cheats: Settings opened straight on that game's cheats.
    function showCheats(g) { show(); cat = 2; stack = [{ title: "Cheats · " + g.name, build: () => cheatsPage(g), closeOnBack: true }]; zone = "list" }
    function showPower() { show(); cat = categories.findIndex(c => c.title === "Power"); zone = "list" }
    function show() { open = true; zone = "side"; row = 0; stack = []; dialog.ask = null; keyboard.open = false; refresh(); rev++ }
    // The in-game menu's Wi-Fi and Bluetooth (MENU-6): opened straight on that Network page, as if picked there
    // (so Wi-Fi scans), and Back closes it, back to the menu.
    function showNetwork(title) {
        show(); cat = categories.findIndex(c => c.title === "Hardware"); zone = "list"
        openRow(section("Network")[0].find(r => r.title === title))
        stack = [Object.assign({}, stack[0], { closeOnBack: true })]
    }
    function close() { open = false; closed() }
    onOpenChanged: btScanCheck()
    onStackChanged: btScanCheck()

    // --- content ------------------------------------------------------------------------------------------------
    readonly property var categories: [
        { title: "General", icon: "gear" }, { title: "Appearance", icon: "palette" }, { title: "Library", icon: "list" },
        { title: "Achievements", icon: "trophy" }, { title: "Hardware", icon: "chip" }, { title: "About", icon: "info" },
        { title: "Power", icon: "power" }]

    function get(k, d) { return backend.getSetting(k, d === undefined ? "" : d) }
    function set(k, v) { backend.setSetting(k, v); rev++ }
    function toggle(icon, title, sub, key, dflt, after) {
        return { kind: "toggle", icon: icon, title: title, sub: sub, on: get(key, dflt) === "1",
                 activate: () => { set(key, get(key, dflt) === "1" ? "0" : "1"); if (after) after() } }
    }
    function choice(icon, title, sub, key, dflt, choices, after) {   // choices: [[label, value], ...]
        const cur = get(key, dflt)
        const i = Math.max(0, choices.findIndex(c => c[1] === cur))
        return { kind: "choice", icon: icon, title: title, sub: sub, value: choices[i][0],
                 step: d => { const v = choices[(i + d + choices.length) % choices.length][1]; set(key, v); if (after) after(v) } }
    }
    // poll: run on opening the sub-page, then every 3 s while it's on top (live status: VPNs)
    function link(icon, title, sub, page, poll) { return { kind: "link", icon: icon, title: title, sub: sub, page: page, poll: poll } }
    function action(icon, title, sub, run) { return { kind: "action", icon: icon, title: title, sub: sub, run: run } }
    function info(icon, title, sub) { return { kind: "info", icon: icon, title: title, sub: sub } }

    // Run a command, keep its (trimmed, optionally parsed) output in live[key] and redraw.
    function sh(key, cmd, parse) {
        backend.exec(cmd, out => note(key, parse ? parse(out) : out.trim()))
    }
    function note(key, value) { const l = Object.assign({}, live); l[key] = value; live = l; rev++ }
    function wifiNow(o) { const p = o.trim().split(":"); return p[1] === "connected" ? p.slice(2).join(":") : "" }
    function refresh() {
        sh("ssid", "nmcli -t -f DEVICE,STATE,CONNECTION dev | grep ^wlan", wifiNow)
        sh("ip", "ip -4 -o addr show wlan0 | awk '{print $4}' | cut -d/ -f1")
        sh("usb", "usbgadget")
        sh("update", "ls /storage/.update/*.tar 2>/dev/null | head -1")
        sh("eq", "python3 /usr/share/asgard/asgard-eq.py status", JSON.parse)
        sh("chargeRecal", "cat /run/asgard-charge-recal 2>/dev/null")
        sh("kernel", "uname -r")
        sh("emuVersions", "cat /usr/share/asgard/emulator-versions 2>/dev/null",   // scripts/emulator-versions, at image time
           o => o.split("\n").filter(l => l.includes("\t")).map(l => l.split("\t")))
        if (get("bluetooth.enabled") === "1") sh("bt", "asgardos-bluetooth list", parseBt)
        storageRefresh()
    }
    function parseBt(out) {   // <device id="MAC" name="..." connected="yes"/> lines
        return out.split("\n").filter(l => l.startsWith("<device")).map(l => {
            const a = n => (l.match(new RegExp(n + '="([^"]*)"')) || [])[1] || ""
            return { mac: a("id"), name: a("name") || a("id"), connected: a("connected") === "yes", type: a("type"), battery: a("battery"), codec: a("codec"), codecs: a("codecs") }
        })
    }
    function q(v) { return "'" + String(v).replace(/'/g, "'\\''") + "'" }      // shell quote
    function confirm(title, text, yes, run) { dialog.open(title, text, yes, run) }

    readonly property var percents: [10, 20, 30, 40, 50, 60, 70, 80, 90, 100].map(v => [v + "%", "" + v])
    // White balance steps for asgard-gamma (-10..10, 0 = the panel as it comes)
    function wbSteps(neg, pos) {
        return Array.from({ length: 21 }, (_, i) => i - 10).map(v => [v === 0 ? "Neutral" : Math.abs(v) + " " + (v < 0 ? neg : pos), "" + v])
    }
    // dflt: asgard-gamma's own default for an unset key (bottom tint and contrast +3, chosen by eye)
    function wbRow(screen, which, title, neg, pos, dflt) {
        return choice("display", title, "Match the two screens", "asgard." + which + "." + screen,
                      dflt || "0", wbSteps(neg, pos), () => backend.shell("kill -HUP $(pidof asgard-gamma)"))
    }
    // Hardware > Display > Top screen / Bottom screen. Submenus only: the keys stay flat (CFG-14).
    function brightnessRows(key, screen) {   // ROCKNIX's brightness script: screen 1 = DSI-1 (bottom), 2 = DSI-2 (top); restored per screen at boot
        return get("asgard.brightness_split") === "1"
            ? [choice("display", "Brightness", "", key, "50", percents, v => backend.shell("brightness set " + screen + " " + v))] : []
    }
    function topScreenPage() {
        return [[...brightnessRows("display.brightness2", 2),
                 choice("display", "Refresh rate", "120 Hz is smoother, 60 Hz saves battery", "asgard.refresh", "120",
                        [["120 Hz", "120"], ["60 Hz", "60"]], v => backend.shell("swaymsg output DSI-2 mode 1080x1920@" + v + "Hz"))],
                [wbRow("top", "warmth", "Warmth", "cooler", "warmer"), wbRow("top", "tint", "Tint", "greener", "pinker"),
                 wbRow("top", "contrast", "Contrast", "softer", "punchier")],
                // AYN's Ultra Black on the top panel (9061): sent at every panel power-on, so cycle the screen to apply it.
                [toggle("display", "OLED Ultra Black", "Deeper blacks; off shows more shadow detail", "asgard.ultra_black", "1",
                        () => backend.shell("echo " + (get("asgard.ultra_black", "1") === "1" ? "Y" : "N") +
                                            " > /sys/module/panel_chipone_icna35xx/parameters/ultra_black;" +
                                            " swaymsg output DSI-2 power off; sleep 0.5; swaymsg output DSI-2 power on; kill -HUP $(pidof asgard-gamma)"))]]
    }
    function bottomScreenPage() {
        return [[...brightnessRows("display.brightness", 1),
                 // 120 Hz (9059) drives the bottom panel ~1.8x brighter with roughly half the colour saturation (webcam,
                 // 2026-10-29): its DDIC keeps the 60 Hz settings. Off by default until the panel's 120 Hz commands are known.
                 choice("display", "Refresh rate", "120 Hz is washed out for now (fix pending)", "asgard.refresh_bottom",
                        "60", [["120 Hz (washed out)", "120"], ["60 Hz", "60"]], v => backend.shell("swaymsg output DSI-1 mode 1080x1240@" + v + "Hz"))],
                [wbRow("bottom", "warmth", "Warmth", "cooler", "warmer"), wbRow("bottom", "tint", "Tint", "greener", "pinker", "3"),
                 wbRow("bottom", "contrast", "Contrast", "softer", "punchier", "3")],
                // ROCKNIX's own switch (vertical-check): "vc" starts the save-state / brightness controls on the bottom
                // screen with RetroArch games; anything else leaves that screen off.
                [choice("gamepad", "RetroArch games", "Save-state and brightness controls in games",
                        "asgardos.bottomscreen.type", "vc", [["Controls", "vc"], ["Off", "off"]])]]
    }
    readonly property var fanModes: [["Quiet", "quiet"], ["Smart", "moderate"], ["Sport", "aggressive"],
                                     ["30%", "77"], ["50%", "128"], ["75%", "191"], ["100%", "255"]]
    function fanNow() { const m = get("asgard.fan_manual"); return m ? m : get("cooling.profile", "moderate") }
    function setFan(v) {   // fancontrol.service applies a fixed speed itself (asgard-fan.sh) instead of its curve
        const fixed = /^\d+$/.test(v)
        set("asgard.fan_manual", fixed ? v : "")
        if (!fixed) set("cooling.profile", v)
        backend.shell("systemctl restart fancontrol")
    }

    // Groups of rows for a category (or the open sub-page).
    function groups() {
        rev                                                   // re-evaluate after changes
        if (stack.length) return stack[stack.length - 1].build()
        return section(categories[cat].title)
    }
    // A category's rows; Hardware's sub-pages (Audio, Display...) reuse it.
    function section(title) {
        const user = get("global.retroachievements.username")
        switch (title) {
        case "General": return [
            [link("user", "Profile", backend.hostname + "  ·  RetroAchievements: " + (user || "not signed in"), profilePage)],
            [action("user", "Device name", backend.hostname + "  ·  applies after a restart",
                    () => keyboard.ask("Device name", get("system.hostname", backend.hostname), false, v => { if (v) set("system.hostname", v) })),
             link("clock", "Date & time", Qt.formatDateTime(new Date(), "ddd d MMM, hh:mm") + "  ·  " + get("system.timezone", "UTC"), dateTimePage)],
            [link("gamepad", "Emulator options", "Shaders, aspect ratio and more, per console", consolesPage)]]
        case "Appearance": return [
            [choice("palette", "Accent colour", "Selection glow and highlights", "asgard.accent", "aurora",
                    [["Aurora", "aurora"], ["Sunset", "sunset"], ["Mint", "mint"], ["Gold", "gold"]], v => Theme.accent = v)],
            [toggle("sparkle", "Animations", "Motion when moving and opening", "asgard.animations", "1",
                    () => Theme.animations = get("asgard.animations", "1") === "1")]]
        case "Library": return [
            [link("gamepad", "Consoles", "Emulator and core for each system", consolesPage)],
            [action("refresh", "Rescan library", backend.systems.length + " systems", () => backend.rescan()),
             action("refresh", "Scrape missing", live.scrape || "Art and details for every game without a cover; A again stops",
                    scrapeMissing),
             action("user", "ScreenScraper account", (get("screenscraper.username") || "Not signed in") +
                    "  ·  descriptions and Switch art; free at screenscraper.fr", ssSignIn)]]
        case "Achievements": return [
            [toggle("trophy", "RetroAchievements", "In supported emulators", "global.retroachievements", "0"),
             toggle("trophy", "Hardcore mode", "No savestates, rewind or cheats; earns hardcore unlocks",
                    "global.retroachievements.hardcore", "0")],
            cheevoOpts.map(o => toggle("trophy", o[0], o[2], "global.retroachievements." + o[1], "0")),
            [action("user", "Account", (user || "Not signed in") + "  ·  username and password, for unlocking in games",
                    raSignIn),
             action("user", "Web API key", (get("global.retroachievements.webapikey") ? "Set" : "Missing") +
                    "  ·  retroachievements.org > Settings > Keys; for the trophy lists",
                    () => keyboard.ask("Web API key", "", true, v => { if (v) { set("global.retroachievements.webapikey", v.trim()); achievements.refresh() } }))]]
        case "Hardware": return [
            [link("speaker", "Audio", "Volume and menu sounds", () => section("Audio")),
             link("display", "Display", "Brightness, screens and stick lights", () => section("Display")),
             link("gauge", "Performance", "Menu CPU profile, fan, gyro, charging and sleep", () => section("Performance")),
             link("wifi", "Network", "Wi-Fi, Bluetooth, USB and services", () => section("Network")),
             link("save", "Storage", storageSummary(), storagePage, storageRefresh),
             link("battery", "Battery", "What used it since it was unplugged", batteryPage)],
            [link("gamepad", "Calibration", "Touch screens and sticks", calibrationPage)]]
        case "Audio": return [
            [toggle("speaker", "Menu sounds", "Clicks when moving and selecting", "asgard.sounds", "1"),
             choice("speaker", "Menu sound volume", "", "asgard.sounds_volume", "50",
                    [["Quiet", "25"], ["Medium", "50"], ["Loud", "100"]], () => backend.sound("select"))],
            [choice("speaker", "Volume", "Speaker and headphones", "audio.volume", "50",
                    [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100].map(v => [v + "%", "" + v]), v => backend.shell("volume " + v))],
            [eqRow("speaker", "Speaker EQ", "Joey's: louder, fuller bass and wider (community JamesDSP tuning)"),
             eqRow("headphones", "Headphone EQ", live.eqMsg || (live.eq && live.eq.headphones_name ? "AutoEQ profile: " + live.eq.headphones_name
                                                                                               : "Follows the headphone jack")),
             live.eq && live.eq.saved && live.eq.saved.length
                 ? link("speaker", "Your headphones", "Saved AutoEQ profiles, or find another model", eqSavedPage)
                 : action("speaker", "Find your headphones", "AutoEQ corrects your model's sound; needs internet", eqAsk),
             link("speaker", "Bass, mid and treble", "For the speaker and the headphones, on top of their EQ", tonePage)],
            [toggle("battery", "Charger sounds", "A chime when the charger is plugged in or out", "asgard.charger_sounds", "1")]]
        case "Display": return [
            [toggle("display", "Separate screen brightness", "Set the top and bottom screens on their own",
                    "asgard.brightness_split", "0",
                    () => { if (get("asgard.brightness_split") !== "1") backend.shell("brightness set " + get("display.brightness2", "50")) }),
             // Separate, each screen's brightness is on its own page.
             ...(get("asgard.brightness_split") === "1" ? []
                 : [choice("display", "Brightness", "Both screens", "display.brightness2", "50", percents, v => backend.shell("brightness set " + v))]),
             choice("moon", "Screens off after", "Without input (OLED care)", "asgard.idle_blank", "300",
                    [["2 min", "120"], ["5 min", "300"], ["10 min", "600"], ["Never", "0"]],
                    () => backend.shell("systemctl restart thor-idle-blank"))],
            [link("display", "Top screen", "Refresh rate, colour and Ultra Black", topScreenPage),
             link("display", "Bottom screen", "Refresh rate, colour and RetroArch controls", bottomScreenPage)],
            [link("sparkle", "Stick lights", "Colour, brightness or battery level", ledPage)],
            // VID-1: every game's screen filter (asgard-screen-filter.sh). Sharp bilinear and FSR where the emulator
            // has them, else bilinear. A system's or game's own (Emulator options) wins.
            [choice("display", "Screen filter", "How games are scaled to the screens · a system's or game's own setting wins",
                    "asgard.screen_filter", "bilinear",
                    [["Bilinear (smooth)", "bilinear"], ["Nearest neighbour (sharp, uneven)", "nearest"],
                     ["Sharp bilinear", "sharp"], ["FSR (sharpened upscale)", "fsr"]])]]
        case "Performance": return [
            // Clock cap per core type, % of the cluster's top clock (asgard-cpu-cap.sh); lower = cooler, longer battery.
            // The Asgard menu's own profile per core type (asgard-cpu-cap.sh, only while in Home): clock cap, % of the
            // cluster's top clock, or Off (its cores offline). Games start at stock; their emulator options override.
            [...[["little", "Little core (A510)", "3× Cortex-A510, CPU0 always stays on", "90"],
                 ["mid", "Big cores (A715/A710)", "2× A715 + 2× A710", "75"], ["prime", "Prime core (X3)", "1× Cortex-X3", "75"]].map(c => {
                const key = "asgard.cpu_cap." + c[0]
                const values = ["off"].concat(Array.from({ length: 16 }, (_, i) => "" + (25 + 5 * i)))
                const cur = get(key, get("asgard.cpu_cap") === "0" ? "100" : c[3])
                return { kind: "choice", icon: "chip", title: c[1] + " · menu", sub: c[2] + " · only in Asgard Home",
                         value: cur === "off" ? "Off" : cur + "%",
                         step: d => { let i = Math.max(0, values.indexOf(cur))
                                      do { i = (i + d + values.length) % values.length }   // never the last type on to Off
                                      while (values[i] === "off" && allCoresOff("asgard", "", c[0], "off"))
                                      set(key, values[i]); backend.shell("/usr/share/asgard/asgard-cpu-cap.sh") } }
            }),
             // The GPU's clock cap while in Home (asgard.gpu_cap, asgard-cpu-cap.sh); games set their own.
             choice("chip", "GPU (Adreno 740) · menu", "% of top clock · only in Asgard Home", "asgard.gpu_cap", "100",
                    Array.from({ length: 16 }, (_, i) => [(25 + 5 * i) + "%", "" + (25 + 5 * i)]),
                    () => backend.shell("/usr/share/asgard/asgard-cpu-cap.sh")),
             { kind: "choice", icon: "fan", title: "Fan", sub: "Curve, or a fixed speed",
               value: (fanModes.find(m => m[1] === fanNow()) || fanModes[1])[0],
               step: d => { const i = Math.max(0, fanModes.findIndex(m => m[1] === fanNow()));
                            setFan(fanModes[(i + d + fanModes.length) % fanModes.length][1]) } },
             // asgard-motiond while in Home; games use their own Gyro option (Hardware overrides, default off)
             toggle("gamepad", "Gyro", "Motion sensors in the menu; games set their own. Uses more battery",
                    "asgard.motion", "0", () => backend.shell("/usr/share/asgard/asgard-perf-profile.sh motion"))],
            // asgard-charge-limit.sh: a gauge that drifted gets one charge to 100% (/run/asgard-charge-recal while due)
            [choice("battery", "Charge limit", live.chargeRecal ? "The next charge goes to 100% once, to recalibrate the battery gauge"
                                                                : "At the limit the charger runs the Thor and the battery rests; charges again 5% below it",
                    "asgard.charge_limit", "80",
                    [["80%", "80"], ["100%", "full"], ["Off", "100"]]),  // asgard-charge-limit.sh reads the setting
             // asgard-charge-limit.sh too: charge current 0 while on the cable, the charger runs the Thor
             toggle("battery", "Bypass charging", "On the cable, run from it and leave the battery alone (charges below 20%)",
                    "asgard.bypass_charging", "0"),
             choice("moon", "Sleep mode", "What the power button does", "system.suspendmode", "mem",
                    [["Sleep", "mem"], ["Light sleep", "freeze"], ["Screen off only", "off"]], v => backend.shell("suspendmode " + v)),
             // asgard-screens-off.sh, for a game set to keep running. A system's or game's own option comes first.
             choice("wifi", "Wi-Fi while screens off", "For games that keep running", "asgard.sleep_wifi", "on", [["On", "on"], ["Off", "off"]]),
             choice("bluetooth", "Bluetooth while screens off", "For games that keep running", "asgard.sleep_bt", "on", [["On", "on"], ["Off", "off"]])],
            osDriverRows()]
        case "Network": return [
            [link("wifi", "Wi-Fi", get("wifi.enabled", "1") !== "1" ? "Off" : live.ssid ? "Connected to " + live.ssid : "Not connected", wifiPage),
             link("bluetooth", "Bluetooth", get("bluetooth.enabled") === "1" ? "On" : "Off", btPage, btPoll)],
            [{ kind: "choice", icon: "chip", title: "USB connection", sub: "To a PC over the USB-C port",
               value: ({ disabled: "Off", network: "Network", file_transfer: "File transfer" })[live.usb] || "…",
               step: d => { const m = ["disabled", "network", "file_transfer"]
                            const v = m[(Math.max(0, m.indexOf(live.usb)) + d + 3) % 3]
                            note("usb", v); sh("usb", "usbgadget " + v + " >/dev/null 2>&1; usbgadget") } },
             info("info", "IP address", [live.ip, live.usb === "network" ? "USB 169.254.170.2" : ""].filter(x => x).join("  ·  ") || "—")],
            services.map(sv => toggle("terminal", sv[0], sv[3], sv[1], "0",
                    () => backend.shell("systemctl " + (get(sv[1]) === "1" ? "start " : "stop ") + sv[2]))),
            [link("shield", "Tailscale", get("tailscale.up") !== "1" ? "Off" : "On", tailscalePage, tsRefresh),
             link("shield", "ZeroTier", get("zerotier.up") !== "1" ? "Off" : "On", zerotierPage, ztRefresh),
             link("shield", "WireGuard", "Tunnels from .conf files", wireguardPage, wgRefresh)]]
        case "About": {
            const os = backend.osInfo()
            const emus = live.emuVersions || []
            return [[info("info", "Asgard OS", ["Version " + (os.OS_VERSION || "unknown"), (os.BUILD_ID || "").slice(0, 7),
                                                os.BUILD_DATE ? "built " + os.BUILD_DATE : ""].filter(x => x).join("  ·  ")),
                     info("terminal", "Linux", live.kernel || "…"),
                     info("chip", "Device", "AYN Thor  ·  " + (os.HW_DEVICE || "SM8550")),
                     info("gamepad", "Library", backend.systems.length + " systems"),
                     link("list", "Emulators", emus.length ? emus.length + " emulators and their versions" : "Versions unknown",
                          emulatorVersionsPage)],
                    [live.update
                     ? action("refresh", "Install update", live.update.split("/").pop() + "  ·  restarts to install",
                              () => confirm("Install update", "The Thor restarts and installs " + live.update.split("/").pop() + ".",
                                            "Restart", () => backend.shell("systemctl reboot")))
                     : info("refresh", "Updates", "Copy an Asgard .tar into /storage/.update to install it")],
                    [link("terminal", "Debug", "Sleep audit and experiments", debugPage)]]
        }
        case "Power": return [
            [action("moon", "Sleep", "Suspend now", () => { close(); backend.shell("systemctl suspend") }),
             action("refresh", "Restart", "Reboot the Thor",
                    () => confirm("Restart", "Restart the Thor now?", "Restart", () => backend.shell("systemctl reboot"))),
             action("power", "Power off", "Shut the Thor down",
                    () => confirm("Power off", "Power off the Thor now?", "Power off", () => backend.shell("systemctl poweroff")))]]
        }
        return []
    }
    readonly property var services: [["SSH", "ssh.enabled", "sshd", "Remote shell"],
                                      ["Samba", "samba.enabled", "smbd nmbd", "Share the SD card on the network"],
                                      ["Syncthing", "syncthing.enabled", "syncthing", "Sync saves with other devices"]]
    readonly property var cheevoOpts: [["Leaderboards", "leaderboards", "Submit scores"],
                                       ["Rich presence", "richpresence", "Show what you are doing on your profile"],
                                       ["Encore mode", "encore", "Unlock achievements again"],
                                       ["Challenge indicators", "challenge_indicators", "Icon while a challenge is active"],
                                       ["Screenshot on unlock", "screenshot", "Save a screenshot with each unlock"],
                                       ["Unofficial achievements", "unofficial", "Include sets still in testing"]]

    // Date & time: timesyncd on/off (asgard.ntp, start_frontend.sh stops it at boot when 0), system.timezone
    // (tz-data.service links /var/run/localtime from the cache file) and, without NTP, the clock set by hand.
    function dateTimePage() {
        const auto = get("asgard.ntp", "1") === "1"
        const now = new Date()
        const shift = (secs, title, fmt) => ({ kind: "choice", icon: "clock", title: title, sub: "", value: Qt.formatDateTime(now, fmt),
            // the Thor's RTC can be set; rtc-offset save covers one that can't
            step: d => backend.exec("date -s @" + (Math.floor(Date.now() / 1000) + d * secs) + " >/dev/null; hwclock -w; rtc-offset save",
                                    () => rev++) })
        const rows = [toggle("clock", "Automatic date & time", auto ? "From the internet (NTP)" : "Set by hand below", "asgard.ntp", "1",
                             () => backend.exec("systemctl " + (get("asgard.ntp", "1") === "1" ? "start" : "stop") + " systemd-timesyncd",
                                                () => rev++)),
                      link("clock", "Time zone", get("system.timezone", "UTC"), zoneRegionsPage)]
        if (!auto) rows.push(shift(86400, "Date", "ddd d MMM yyyy"), shift(3600, "Hour", "hh"), shift(60, "Minute", "mm"))
        return [rows]
    }
    readonly property var zoneRegions: ["Africa", "America", "Antarctica", "Asia", "Atlantic", "Australia", "Europe", "Indian", "Pacific"]
    function zoneRegionsPage() {
        return [[action("clock", "UTC", "", () => setZone("UTC"))],
                zoneRegions.map(r => action("clock", r, "", () => {
                    note("zones", null)
                    sh("zones", "cd /usr/share/zoneinfo/" + r + " && find . -type f | sed 's|^\\./||' | sort", o => o.split("\n").filter(x => x))
                    stack = stack.concat([{ title: r, build: () => zoneCitiesPage(r) }]); row = 0; rev++ }))]
    }
    function zoneCitiesPage(r) {
        if (!live.zones) return [[info("refresh", "Loading…", r)]]
        return [live.zones.map(c => action("clock", c.replace(/_/g, " "), r + "/" + c === get("system.timezone") ? "Current" : "",
                                             () => setZone(r + "/" + c)))]
    }
    function setZone(tz) {
        set("system.timezone", tz)
        backend.exec("echo -n TIMEZONE=" + q(tz) + " > /storage/.cache/timezone; echo -n " + q(tz) +
                     " > /storage/.cache/system_timezone; systemctl restart tz-data", () => {
            Date.timeZoneUpdated()   // the QML engine caches the zone
            stack = stack.filter(p => p.build !== zoneRegionsPage && p.title !== tz.split("/")[0]); row = 0; rev++ })
    }

    function calibrationPage() {
        const touch = s => () => { close(); backend.runTool("/usr/share/asgard/thor_touchcal.py", [s]) }
        return [[action("display", "Touch screen (top)", "Tap 5 targets; the controller confirms", touch("top")),
                 action("display", "Touch screen (bottom)", "Tap 5 targets; the controller confirms", touch("bottom")),
                 action("refresh", "Reset touch calibration", "Both screens back to the default",
                        () => confirm("Reset touch calibration", "Both touch screens go back to the default.", "Reset",
                                      () => backend.shell("python3 /usr/share/asgard/thor_touchcal.py reset")))],
                [action("gamepad", "Left stick", "Center, range and deadzone", () => stickCal.open("stick", "left")),
                 action("gamepad", "Right stick", "Center, range and deadzone", () => stickCal.open("stick", "right")),
                 action("gamepad", "Left trigger", "Rest and full press", () => stickCal.open("trigger", "left")),
                 action("gamepad", "Right trigger", "Rest and full press", () => stickCal.open("trigger", "right")),
                 action("gamepad", "Test controls", "Sticks and triggers as games see them", () => stickCal.open("all")),
                 action("refresh", "Reset sticks and triggers", "rsinput's own range, no deadzone",
                        () => confirm("Reset sticks and triggers", "The sticks and triggers go back to the driver's defaults.",
                                      "Reset", () => {
                            const p = StickCalJs.defaults()
                            backend.setRsinput(p); backend.saveRsinput(StickCalJs.savedText(p))
                            backend.shell("systemctl restart inputplumber") }))]]
    }
    function emulatorVersionsPage() {
        const emus = live.emuVersions || []
        return [emus.length ? emus.map(e => info("gamepad", e[0], e[1]))
                            : [info("info", "Versions unknown", "This build has no /usr/share/asgard/emulator-versions")]]
    }
    function debugPage() {
        return [[toggle("moon", "Sleep audit", "One line per sleep in /storage/sleep-audit.csv: drain and what slept",
                        "asgard.sleep_audit", "0"),
                 toggle("gamepad", "Controller wake fix", "After a wake, re-probe the pad if it stopped sending (rsinput stall)",
                        "asgard.pad_fix", "1"),
                 toggle("gamepad", "Controller wake fix log", "One line per re-probe in /storage/pad-fix.log",
                        "asgard.pad_fix_log", "1"),
                 choice("moon", "Sleep experiment", "Switched off during sleep, to find what drains the battery",
                        "asgard.sleep_experiment", "", [["None", ""], ["Wi-Fi off", "wifi"], ["Bluetooth off", "bt"],
                                                        ["Wi-Fi and Bluetooth off", "wifi bt"],
                                                        ["Wi-Fi off every other sleep", "alt:wifi"],
                                                        ["Bluetooth off every other sleep", "alt:bt"]])]]
    }
    // --- VPNs (Hardware > Network) -----------------------------------------------------------------------------
    function json(o, dflt) { try { return JSON.parse(o) } catch (e) { return dflt } }

    // Tailscale: tailscale.up (ROCKNIX's 099-networkservices starts tailscaled at boot) and tailscaled now. Sign in
    // runs `tailscale up` in the background; tailscaled then puts the login link (AuthURL) in its status.
    readonly property string ts: "/usr/sbin/tailscale"
    function tsRefresh() { sh("ts", ts + " status --json 2>/dev/null", o => json(o, {})) }
    function tailscalePage() {
        const on = get("tailscale.up") === "1"
        const s = live.ts || {}, st = s.BackendState || ""
        const state = ({ Running: "Connected", NeedsLogin: "Signed out", NoState: "Signed out", Starting: "Connecting…",
                         Stopped: "Disconnected" })[st] || "Starting…"
        const rows = [[toggle("shield", "Tailscale", on ? state : "Off", "tailscale.up", "0",
                              () => backend.exec("systemctl " + (get("tailscale.up") === "1" ? "start" : "stop") + " tailscaled", tsRefresh))]]
        if (!on || !st) return rows
        if (st === "NeedsLogin" || st === "NoState") {
            const signIn = action("user", "Sign in", s.AuthURL ? "Open the link below on your phone or PC" : "Gets a sign-in link",
                () => backend.exec("(setsid " + ts + " up --hostname=" + q(backend.hostname) + " >/tmp/tailscale-up.log 2>&1 &)", tsRefresh))
            rows.push(s.AuthURL ? [signIn, info("wifi", s.AuthURL.replace("https://", ""), "Waiting for you to sign in…")] : [signIn])
            return rows
        }
        const self = s.Self || {}
        const peers = Object.values(s.Peer || {})
        rows.push([info("wifi", "Address", (s.TailscaleIPs || [])[0] || "—"),
                   info("user", "Tailnet", ((s.CurrentTailnet || {}).Name || "—") + "  ·  this Thor is " + (self.HostName || backend.hostname)),
                   info("list", "Devices", peers.filter(p => p.Online).length + " online of " + peers.length)])
        rows.push([action("power", "Sign out", "Remove this Thor from the tailnet",
                          () => confirm("Sign out of Tailscale", "This Thor leaves the tailnet until you sign in again.", "Sign out",
                                        () => backend.exec(ts + " logout", tsRefresh)))])
        return rows
    }

    // ZeroTier: zerotier.up and zerotier-one, like Tailscale. Joined networks are kept in ROCKNIX's
    // /storage/.config/zerotier-networks, which zerotier-join.sh re-joins on every start (and leaves the rest).
    readonly property string zt: "/usr/sbin/zerotier-cli -D/storage/.config/zerotier/"
    readonly property string ztList: "/storage/.config/zerotier-networks"
    function ztRefresh() {
        sh("ztInfo", zt + " -j info 2>/dev/null", o => json(o, {}))
        sh("ztNets", zt + " -j listnetworks 2>/dev/null", o => json(o, []))
    }
    function zerotierPage() {
        const on = get("zerotier.up") === "1"
        const node = live.ztInfo || {}
        const rows = [[toggle("shield", "ZeroTier", !on ? "Off" : node.online ? "Online" : "Starting…", "zerotier.up", "0",
                              () => backend.exec("systemctl " + (get("zerotier.up") === "1" ? "start" : "stop") + " zerotier-one", ztRefresh))]]
        if (!on) return rows
        rows[0].push(info("user", "Node ID", (node.address || "—") + "  ·  authorize it in ZeroTier Central"))
        const status = n => ({ OK: "Connected  ·  " + ((n.assignedAddresses || [])[0] || "no address yet").split("/")[0],
                               ACCESS_DENIED: "Waiting for approval in ZeroTier Central", REQUESTING_CONFIGURATION: "Connecting…",
                               NOT_FOUND: "No such network" })[n.status] || n.status
        const nets = (live.ztNets || []).map(n => action("wifi", n.name || n.id || n.nwid, status(n), () => {
            const id = n.id || n.nwid
            confirm("Leave " + (n.name || id), "The Thor leaves this network and stops re-joining it.", "Leave",
                    () => backend.exec("sed -i '/^" + id + "$/d' " + ztList + "; " + zt + " leave " + id, ztRefresh))
        }))
        rows.push(nets.concat([action("refresh", "Join a network", live.ztMsg || "Its 16-character network ID",
            () => keyboard.ask("ZeroTier network ID", "", false, v => {
                const id = (v || "").trim().toLowerCase()
                if (!/^[0-9a-f]{16}$/.test(id)) { note("ztMsg", id ? "Not a network ID: 16 characters, 0-9 and a-f" : ""); return }
                note("ztMsg", "")
                backend.exec("grep -qx " + id + " " + ztList + " 2>/dev/null || echo " + id + " >> " + ztList + "; " + zt + " join " + id, ztRefresh)
            }))]))
        return rows
    }

    // WireGuard: NetworkManager's own tunnels, imported from .conf files in /storage/.config/wireguard (the Samba
    // "config" share). The connection is named after the file (an interface name: 15 characters at most); it
    // persists in NetworkManager's keyfiles, and a tunnel left on comes back at boot (autoconnect).
    readonly property string wgDir: "/storage/.config/wireguard"
    function wgRefresh() {
        sh("wg", "mkdir -p " + wgDir + "; for f in " + wgDir + "/*.conf; do [ -e \"$f\" ] && echo \"F:$(basename \"$f\" .conf)\"; done; " +
                 "nmcli -t -f NAME,TYPE,STATE connection show 2>/dev/null | grep ':wireguard:' | sed 's/^/C:/'; " +
                 "ip -4 -o addr 2>/dev/null | awk '{print \"I:\" $2 \":\" $4}'", o => {
            const r = { files: [], conns: {}, ips: {} }
            for (const l of o.split("\n")) {
                const p = l.split(":")
                if (p[0] === "F") r.files.push(p.slice(1).join(":"))
                else if (p[0] === "C") r.conns[p[1]] = p[3] || ""
                else if (p[0] === "I") r.ips[p[1]] = (p[2] || "").split("/")[0]
            }
            return r
        })
    }
    // NET-3: NetworkManager makes an imported tunnel the DNS default route (a .conf with DNS = also gets the catch-all
    // routing domain ~.), taking it from the Wi-Fi: every lookup goes through the tunnel. A tunnel whose Endpoint is a
    // hostname, up at boot before it resolved it, then sends that lookup into itself and every lookup on the Thor fails
    // (seen 2026-11-21). A split tunnel (no 0.0.0.0/0 or ::/0 in AllowedIPs) gets neither: never-default and no
    // catch-all, which on a Thor left the Wi-Fi the DNS default and lookups working with the tunnel dead. Sets "$@"
    // for the modify that follows.
    function wgSplitDns(n) {
        return "set --; f=" + q(wgDir + "/" + n + ".conf") + "; [ -f \"$f\" ] && ! grep -qiE " +
               "'^[[:space:]]*AllowedIPs[[:space:]]*=.*(0[.]0[.]0[.]0/0|::/0)' \"$f\" && set -- ipv4.dns-search '' ipv6.dns-search '' ipv4.never-default yes ipv6.never-default yes; "
    }
    function wireguardPage() {
        const w = live.wg
        if (!w) return [[info("refresh", "Loading…", "")]]
        const names = w.files.concat(Object.keys(w.conns).filter(n => !w.files.includes(n)))
        const run = cmd => backend.exec("(" + cmd + ") 2>&1", o => { const err = o.split("\n").find(l => /error/i.test(l)); note("wgMsg", err || ""); wgRefresh() })
        const tunnels = names.map(n => {
            const up = w.conns[n] === "activated"
            return { kind: "toggle", icon: "shield", title: n, on: up,
                     sub: up ? "Connected" + (w.ips[n] ? "  ·  " + w.ips[n] : "") : n in w.conns ? "Off" : "Off  ·  not imported yet",
                     activate: () => run(up ? "nmcli connection modify " + q(n) + " connection.autoconnect no; nmcli connection down " + q(n)
                                            : wgSplitDns(n) + (n in w.conns ? "" : "nmcli connection import type wireguard file " + q(wgDir + "/" + n + ".conf") + " && ") +
                                              "nmcli connection modify " + q(n) + " connection.autoconnect yes \"$@\" && nmcli connection up " + q(n)) }
        })
        const rows = [tunnels.length ? tunnels : [info("info", "No tunnels yet", "Add a WireGuard .conf file first (below)")]]
        if (live.wgMsg) rows[0].push(info("info", "Could not connect", live.wgMsg))
        rows.push([info("list", "Adding a tunnel", "Put its .conf in " + wgDir + "  ·  Samba share \"config\", folder wireguard, or Files"),
                   ...Object.keys(w.conns).map(n => action("refresh", "Forget " + n, "Remove it from the Thor (the .conf stays)",
                       () => confirm("Forget " + n, "The tunnel is removed; its .conf file stays, to import it again.", "Forget",
                                     () => run("nmcli connection delete " + q(n)))))])
        return rows
    }

    function wifiPage() {
        const on = get("wifi.enabled", "1") === "1"
        const rows = [[{ kind: "toggle", icon: "wifi", title: "Wi-Fi", sub: live.wifiMsg || (live.ssid ? "Connected to " + live.ssid : "Not connected"),
                         on: on, activate: () => { set("wifi.enabled", on ? "0" : "1"); note("wifiMsg", on ? "Turning off…" : "Turning on…")
                                                   backend.exec("wifictl " + (on ? "disable" : "enable"), () => { note("wifiMsg", ""); refresh() }) } }]]
        if (!on) return rows
        rows[0].push(action("refresh", "Scan for networks", live.scanning ? "Scanning…" : (live.nets || []).length + " found", scan))
        if (live.ssid) rows[0].push(action("wifi", "Disconnect", live.ssid,
                                           () => backend.exec("wifictl disconnect", () => refresh())))
        if ((live.nets || []).length)
            rows.push(live.nets.map(n => action("wifi", n, n === live.ssid ? "Connected" : n === get("wifi.ssid") ? "Saved" : "", () => join(n))))
        return rows
    }
    function scan() {
        note("scanning", true)
        backend.exec("wifictl list", o => { note("scanning", false); note("nets", o.split("\n").map(x => x.trim()).filter(x => x)) })
    }
    function join(ssid) {
        const go = psk => {
            set("wifi.ssid", ssid); set("wifi.key", psk)
            note("wifiMsg", "Connecting to " + ssid + "…")
            backend.exec("wifictl connect " + q(ssid) + " " + q(psk), () =>
                backend.exec("nmcli -t -f DEVICE,STATE,CONNECTION dev | grep ^wlan", o => {
                    const now = wifiNow(o)
                    note("ssid", now)
                    note("wifiMsg", now === ssid ? "" : "Could not connect to " + ssid + " — check the password")
                    sh("ip", "ip -4 -o addr show wlan0 | awk '{print $4}' | cut -d/ -f1")
                }))
        }
        if (ssid === get("wifi.ssid") && get("wifi.key")) go(get("wifi.key"))
        else keyboard.ask("Password for " + ssid, "", true, go)
    }

    // A paired device's state, with its audio codec and its battery when it reports one (only while connected)
    function btState(d) {
        return d.connected ? "Connected" + (d.codec ? "  ·  " + d.codec : "") + (d.battery ? "  ·  battery " + d.battery + "%" : "") : "Paired"
    }
    // While a Bluetooth page is up: connections, and a battery that headphones report a few seconds after connecting
    function btPoll() { if (get("bluetooth.enabled") === "1") sh("bt", "asgardos-bluetooth list", parseBt) }
    function btPage() {
        const on = get("bluetooth.enabled") === "1"
        const rows = [[{ kind: "toggle", icon: "bluetooth", title: "Bluetooth", sub: live.btMsg || (on ? "On" : "Off"), on: on,
                         activate: () => { set("bluetooth.enabled", on ? "0" : "1"); note("btMsg", on ? "Turning off…" : "Turning on…")
                                           backend.exec("asgardos-bluetooth " + (on ? "disable" : "enable"), () => { note("btMsg", ""); refresh() }) } }]]
        if (!on) return rows
        rows[0].push(link("bluetooth", "Pair a new device", "Controllers, headphones", btScanPage, btScanPoll))
        if ((live.bt || []).length)
            rows.push(live.bt.map(d => link("bluetooth", d.name, btState(d), () => btDevicePage(d), btPoll)))
        return rows
    }
    // The scan runs while this page is open: btScanCheck stops it however the page is left.
    property bool btScanning: false
    function btScanStart() {
        note("btScan", []); note("btScanError", ""); btScanning = true
        backend.exec("asgardos-bluetooth scan_start", o => note("btScanError", o.trim().split("\n").pop().slice(0, 60)))
    }
    function btScanCheck() {
        if (btScanning && (!open || !stack.some(p => p.build === btScanPage))) {
            btScanning = false
            backend.exec("asgardos-bluetooth scan_stop", () => {})
        }
    }
    function btScanPoll() { if (!live.btPairing) sh("btScan", "asgardos-bluetooth scan_list", parseBt) }
    function btScanPage() {
        if (live.btPairing) return [[info("bluetooth", "Pairing " + live.btPairing + "…", "This can take up to a minute")]]
        if (live.btScanError) return [[info("bluetooth", "Can't look for devices", live.btScanError)]]
        const paired = (live.bt || []).map(d => d.mac)
        const found = (live.btScan || []).filter(d => !paired.includes(d.mac))
        const rows = [[info("bluetooth", found.length ? "Choose a device" : "Looking for devices…", "Put the device in pairing mode")]]
        if (found.length)
            rows.push(found.map(d => action("bluetooth", d.name, ({ joystick: "Controller", audio: "Audio" })[d.type] || d.mac, () => btPair(d))))
        return rows
    }
    function btPair(d) {
        note("btPairing", d.name); row = 0
        backend.exec("asgardos-bluetooth trust " + d.mac, o => {
            note("btPairing", ""); note("btMsg", (o.trim().split("\n").pop() || "").slice(0, 60)); refresh()
            if (stack.length && stack[stack.length - 1].build === btScanPage) { stack = stack.slice(0, -1); row = 0 }
        })
    }
    // Connect and Disconnect can fail, and take up to half a minute: say so here. The page holds the device as it was
    // when opened, so the state comes from the current list.
    function btConnect(d) {
        const k = "btConn" + d.mac
        if (live[k] && live[k].endsWith("…")) return
        note(k, d.connected ? "Disconnecting…" : "Connecting…")
        backend.exec("asgardos-bluetooth " + (d.connected ? "disconnect " : "connect ") + d.mac, o => {
            const last = o.trim().split("\n").pop() || ""
            note(k, last.startsWith("ERROR: ") ? last.slice(7, 67) : ""); refresh() })
    }
    function btDevicePage(opened) {
        const d = (live.bt || []).find(x => x.mac === opened.mac) || opened
        return [[action("bluetooth", d.connected ? "Disconnect" : "Connect", live["btConn" + d.mac] || d.mac, () => btConnect(d)),
                 action("power", "Forget this device", d.name,
                        () => confirm("Forget device", "Forget " + d.name + "? You will need to pair it again.", "Forget",
                                      () => backend.exec("asgardos-bluetooth remove " + d.mac, () => { refresh(); stack = stack.slice(0, -1) })))],
                ...(d.connected && (d.codec || d.codecs || d.battery)
                    ? [[...(d.codec || d.codecs ? [btCodecRow(d)] : []),
                        ...(d.battery ? [info("battery", "Battery", d.battery + "%")] : [])]] : [])]
    }
    // The codec music plays over; ‹ › switches to the next one the device offers (codecs=, best first). The row stays
    // while a switch reopens the stream and no codec is reported for a moment.
    function btCodecRow(d) {
        const offered = d.codecs ? d.codecs.split(",") : []
        const k = "btCodec" + d.mac
        if (offered.length < 2) return info("speaker", "Audio codec", d.codec || "…")
        return { kind: "choice", icon: "speaker", title: "Audio codec", sub: live[k] || "Sound quality, or a steadier link",
                 value: d.codec || "…",
                 step: dir => {
                     if (live[k] === "Switching…") return
                     const c = offered[(Math.max(0, offered.indexOf(d.codec)) + dir + offered.length) % offered.length]
                     note(k, "Switching…")
                     backend.exec("asgardos-bluetooth codec " + d.mac + " " + q(c) + " 2>&1", o => {
                         const last = o.trim().split("\n").pop() || ""
                         note(k, last.startsWith("ERROR: ") ? last.slice(7, 67) : ""); btPoll() })
                 } }
    }

    readonly property var ledColours: [["Red", "255 0 0"], ["Orange", "255 100 0"], ["Yellow", "255 200 0"], ["Green", "0 255 0"],
                                       ["Cyan", "0 255 255"], ["Blue", "0 0 255"], ["Purple", "160 0 255"], ["Pink", "255 0 120"],
                                       ["White", "255 255 255"], ["Off", "0 0 0"]]
    // asgard-eq.py: Thor tuning / off / an AutoEQ profile (headphones) and bass, mid and treble, set on the running EQ
    // with no gap (SND-7). "later": the running EQ is of an older shape and a game is playing, so it waits for the next one.
    function eqRun(args, then) {
        note("eqMsg", "Applying…")
        backend.exec("python3 /usr/share/asgard/asgard-eq.py " + args, out => {
            const r = JSON.parse(out || "{}")
            note("eqMsg", r.error || (r.later ? "Saved: heard from the next game" : ""))
            eqRefresh()
            if (then && !r.error) then()
        })
    }
    function eqRefresh() { sh("eq", "python3 /usr/share/asgard/asgard-eq.py status", JSON.parse) }
    // Headphones cycle through Thor tuning, Off and every saved AutoEQ profile (by name); each step applies at once.
    // While a game overrides that output's EQ (its Sound EQ option, SND-3), the row shows it and doesn't step.
    function eqRow(which, title, sub) {
        const modes = which === "speaker" ? [["Thor tuning", "set speaker thor"], ["Joey (Retro Handhelds)", "set speaker joey"], ["Off", "set speaker off"]]
                                          : [["Thor tuning", "set headphones thor"], ["Off", "set headphones off"]]
        if (which === "headphones" && live.eq)
            for (const n of live.eq.saved || []) modes.push([n, "use " + q(n)])
        const e = live.eq, cur = !e ? "" : which === "headphones" && e.headphones === "autoeq" ? "use " + q(e.headphones_name)
                                                                                          : "set " + which + " " + e[which]
        const i = Math.max(0, modes.findIndex(m => m[1] === cur))
        const game = e && e.game && e.game[which]
        if (game)
            return { kind: "choice", icon: "speaker", title: title, sub: "Set by this game's Sound EQ option",
                     value: ({ thor: "Thor tuning", joey: "Joey (Retro Handhelds)", off: "Off", autoeq: e.headphones_name || "AutoEQ" })[game] || game,
                     step: d => {} }
        return { kind: "choice", icon: "speaker", title: title, sub: sub, value: e ? modes[i][0] : "…",
                 step: d => eqRun(modes[(i + d + modes.length) % modes.length][1]) }
    }
    // Bass, mid and treble, -6..+6 dB, per output: on top of its EQ, whichever it is.
    function toneRow(which, band, title, sub) {
        const t = live.eq && live.eq.tone ? live.eq.tone[which] : null
        const v = t ? Math.round(t[band]) : 0
        return { kind: "choice", icon: "speaker", title: title, sub: sub, value: t ? (v > 0 ? "+" : "") + v + " dB" : "…",
                 step: d => {
                     if (!t || Math.abs(v + d) > 6) return
                     const n = t.slice(); n[band] = v + d
                     eqRun("tone " + which + " " + n.join(" "))
                 } }
    }
    // An output's EQ and tone: Settings' Tone page and the in-game menu's Sound page (SND-7).
    function soundRows(which) {
        return [eqRow(which, which === "speaker" ? "Speaker EQ" : "Headphone EQ", ""),
                toneRow(which, 0, "Bass", "Below 100 Hz"), toneRow(which, 1, "Mid", "Around 1 kHz"), toneRow(which, 2, "Treble", "Above 8 kHz")]
    }
    function tonePage() {
        return [["speaker", "Speaker"], ["headphones", "Headphones"]].map(w => [
            toneRow(w[0], 0, w[1] + " bass", "Below 100 Hz"), toneRow(w[0], 1, w[1] + " mid", "Around 1 kHz"),
            toneRow(w[0], 2, w[1] + " treble", "Above 8 kHz")])
    }
    function eqAsk() { keyboard.ask("Headphone model", "", false, v => { if (v && v.trim()) eqSearch(v.trim()) }) }
    // Headphones found before (no internet needed), then a search for a new model.
    function eqSavedPage() {
        const e = live.eq || {}
        return [(e.saved || []).map(n => action("speaker", n,
                    e.headphones === "autoeq" && e.headphones_name === n ? "In use" : "Use this AutoEQ profile",
                    () => eqRun("use " + q(n), () => { stack = stack.slice(0, -1); row = 0; rev++ }))),
                [action("speaker", "Find another model", "Search AutoEQ; needs internet", eqAsk)]]
    }
    function eqSearch(text) {
        note("eqMsg", "Searching AutoEQ…")
        backend.exec("python3 /usr/share/asgard/asgard-eq.py search " + q(text), out => {
            const r = JSON.parse(out || "{}")
            note("eqMsg", r.error || (r.results.length ? "" : "No AutoEQ profile matches \"" + text + "\""))
            if (r.results && r.results.length) {
                note("eqResults", r.results)
                stack = stack.concat([{ title: "AutoEQ: " + text, build: eqResultsPage }]); row = 0; rev++
            }
        })
    }
    function eqResultsPage() {
        return [[info("info", "Pick your model", "Measured by the source shown; the first ones are the most reliable")],
                (live.eqResults || []).map(h => action("speaker", h.name, h.by,
                    () => eqRun("autoeq " + q(h.path) + " " + q(h.name), () => { stack = stack.slice(0, -1); row = 0; rev++ })))]
    }

    // Hardware > Storage (SET-5): df for the internal storage, the SD card, the system partition and the ROMs folder.
    // ROCKNIX mounts the card at /storage/games-external (and binds /storage/roms to it); without a card that path
    // is a plain folder, and df answers for the mount it's on. One line per path: "<path> <df -P line>", so a path
    // df can't read (empty) doesn't shift the others.
    readonly property var volumes: ["/storage", "/storage/games-external", "/flash", "/storage/roms"]
    function storageRefresh() {
        sh("storage", "for p in " + volumes.join(" ") + "; do echo \"$p $(df -PkT \"$p\" 2>/dev/null | tail -n +2 | tail -1)\"; done",
           parseStorage)
    }
    // -> { "<path>": {dev, type, total, used, free, mount} } in bytes, for the paths df answered
    function parseStorage(out) {
        const r = {}
        for (const l of out.split("\n")) {
            const p = l.trim().split(/\s+/)   // path, Filesystem, Type, 1024-blocks, Used, Available, Capacity, Mounted on
            if (p.length < 8 || !/^\d+$/.test(p[3])) continue
            r[p[0]] = { dev: p[1], type: p[2], total: p[3] * 1024, used: p[4] * 1024, free: p[5] * 1024, mount: p.slice(7).join(" ") }
        }
        return r
    }
    function gb(bytes) {   // decimal units, as cards and drives are labelled
        const g = bytes / 1e9
        return g >= 1000 ? (g / 1000).toFixed(2) + " TB" : g >= 100 ? Math.round(g) + " GB" : g >= 10 ? g.toFixed(1) + " GB"
                         : g >= 1 ? g.toFixed(2) + " GB" : Math.round(bytes / 1e6) + " MB"
    }
    function volume(path) {   // the volume at exactly that mount point, else null
        const v = (live.storage || {})[path]
        return v && v.mount === path ? v : null
    }
    function usage(v) {
        return gb(v.free) + " free of " + gb(v.total) + "  ·  " + gb(v.used) + " used (" + Math.round(100 * v.used / Math.max(1, v.total)) + "%)"
    }
    function storageSummary() {
        if (!live.storage) return "Internal storage and SD card"
        const i = volume("/storage"), sd = volume("/storage/games-external")
        return [i ? gb(i.free) + " free inside" : "", sd ? gb(sd.free) + " free on the SD card" : "No SD card"].filter(x => x).join("  ·  ")
    }
    function storagePage() {
        if (!live.storage) return [[info("save", "Storage", "Reading…")]]
        const i = volume("/storage"), sd = volume("/storage/games-external"), sys = volume("/flash")
        const roms = live.storage["/storage/roms"]
        const where = !roms ? "—" : sd && roms.dev === sd.dev ? "On the SD card" : roms.dev === (i || {}).dev ? "On the internal storage" : roms.mount
        return [[info("save", "Internal storage", i ? usage(i) : "Can't read /storage"),
                 info("save", "SD card", sd ? usage(sd) + "  ·  " + sd.type : "No SD card in")],
                [info("gamepad", "Games", where + "  ·  /storage/roms"),
                 ...(sys ? [info("chip", "System", usage(sys) + "  ·  the OS image and its updates")] : [])]]
    }

    // battery-report.py: the battery logger's samples since the last unplug, split by what was running (or asleep).
    function batteryPage() {
        const b = live.battery
        if (!b) return [[info("battery", "Battery", "Reading the battery log…")]]
        if (b.error) return [[info("battery", "Battery", b.error)]]
        const hm = h => { const m = Math.round(h * 60); return m < 60 ? m + " min" : Math.floor(m / 60) + " h " + m % 60 + " min" }
        const at = ts => Qt.formatDateTime(new Date(ts * 1000), "ddd hh:mm")
        const n = b.now, s = b.session
        const top = [info("battery", "Now", n.pct + "%  ·  " + (n.charging ? "charging" : n.ma + " mA") +
                          (n.hours_left ? "  ·  about " + hm(n.hours_left) + " left at this rate" : ""))]
        if (b.charge)
            top.push(info("battery", "Charging since " + at(b.charge.start), b.charge.from_pct + "% → " + b.charge.to_pct + "% in " + hm(b.charge.hours)))
        if (!s) return [top]
        top.push(info("battery", "Since unplugged " + at(s.start), s.from_pct + "% → " + s.to_pct + "% over " + hm(s.hours)))
        return [top, s.activities.map(a => info(a.name === "Sleep" ? "moon" : a.name === "Home" ? "list" : "gamepad", a.name,
                                                 hm(a.hours) + "  ·  " + a.pct + "% used  ·  " + a.ma + " mA average"))]
    }

    function ledPage() {
        let v = get("analogsticks.led", "150 0 0 255 0 0 255").split(" ")
        if (v.length !== 7) v = "150 0 0 255 0 0 255".split(" ")
        const apply = nv => { set("analogsticks.led", nv.join(" "))
                              if (get("led.color") !== "rgb") { set("led.color", "rgb"); backend.shell("ledcontrol rgb") }
                              backend.shell("analog_sticks_ledcontrol " + nv.join(" ")) }
        const colour = (title, at) => {
            const cur = v.slice(at, at + 3).join(" ")
            const found = ledColours.findIndex(c => c[1] === cur)
            const i = Math.max(0, found)
            return { kind: "choice", icon: "palette", title: title, sub: "", value: found < 0 ? "Custom" : ledColours[i][0],
                     step: d => { const nv = v.slice(); const c = ledColours[(i + d + ledColours.length) % ledColours.length][1].split(" ")
                                  nv.splice(at, 3, c[0], c[1], c[2]); apply(nv) } }
        }
        const levels = [["Low", "60"], ["Medium", "150"], ["High", "255"]]
        const li = Math.max(0, levels.findIndex(l => l[1] === v[0]))
        return [[choice("sparkle", "Mode", "", "led.color", "off", [["Off", "off"], ["Colour", "rgb"], ["Battery level", "battery"]],
                        m => backend.shell("ledcontrol " + m)),
                 { kind: "choice", icon: "display", title: "Brightness", sub: "", value: levels[li][0],
                   step: d => { const nv = v.slice(); nv[0] = levels[(li + d + 3) % 3][1]; apply(nv) } }],
                [colour("Right stick", 1), colour("Left stick", 4)]]
    }

    // Per-game emulator/core: ROCKNIX's <system>["<file>"].<key> settings, which the launcher reads first.
    function gamePage(g) {
        const file = g.path.split("/").pop()
        const k = key => g.sys + '["' + file + '"].' + key
        const emus = backend.emulators(g.sys)
        const sysEmu = get(g.sys + ".emulator", g.emulator), sysCore = get(g.sys + ".core", g.core)
        const emu = get(k("emulator"), sysEmu)
        const cur = emus.find(e => e.name === emu) || emus[0]
        const own = get(k("emulator")) !== "" || get(k("core")) !== ""
        const rows = [{ kind: "choice", icon: "gamepad", title: "Emulator", sub: own ? "This game only" : "Same as " + g.sysName,
                        value: emu,
                        step: d => { const i = Math.max(0, emus.findIndex(e => e.name === emu))
                                     const e = emus[(i + d + emus.length) % emus.length]
                                     set(k("emulator"), e.name); set(k("core"), e.cores[0] || "") } }]
        if (cur && cur.cores.length > 1)
            rows.push({ kind: "choice", icon: "chip", title: "Core", sub: "RetroArch core", value: get(k("core"), sysCore),
                        step: d => { const c = get(k("core"), sysCore); const i = Math.max(0, cur.cores.indexOf(c))
                                     set(k("emulator"), emu); set(k("core"), cur.cores[(i + d + cur.cores.length) % cur.cores.length]) } })
        if (own)
            rows.push(action("refresh", "Use " + g.sysName + " settings", sysEmu + " / " + sysCore,
                             () => { set(k("emulator"), ""); set(k("core"), "") }))
        const st = backend.playStats(g.path)
        rows.push(link("sparkle", "Cheats", "On at the next launch", () => cheatsPage(g)))
        const cacheKey = "shaderCache:" + g.path   // asgard-shader-cache.sh's answer: what it deleted, or why not
        return [rows, [info("info", "Played", st.playtime ? Math.round(st.playtime / 60) + " min" : "Never"),
                       link("chip", "Emulator options", "This game only; unset ones follow " + g.sysName,
                            () => optionsPage(g.sys + '["' + file + '"]', emu, get(k("core"), sysCore), g.sys)),
                       action("broom", "Delete shader cache", live[cacheKey] || "Rebuilt on the next launch; fixes a black screen at start",
                              () => sh(cacheKey, "/usr/share/asgard/asgard-shader-cache.sh " + q(g.sys) + " " + q(g.path) + " 2>&1"))]]
    }

    // A game's cheats (asgard-cheats.py): a row per cheat in the database for its emulator, on or off, applied when the
    // game next starts. The emulator and core are the game's, as the page above resolves them.
    function cheatsPage(g) {
        const file = g.path.split("/").pop()
        const k = key => g.sys + '["' + file + '"].' + key
        const emu = get(k("emulator"), get(g.sys + ".emulator", g.emulator))
        const core = get(k("core"), get(g.sys + ".core", g.core))
        const key = "cheats:" + g.path
        const args = [g.sys, g.path, emu, core].map(q).join(" ")
        const parse = o => { try { return JSON.parse(o) } catch (e) { return { cheats: [], error: "Couldn't read the cheats" } } }
        if (live[key] === undefined) { note(key, null); sh(key, "python3 /usr/share/asgard/asgard-cheats.py list " + args, parse) }
        const r = live[key]
        if (!r) return [[info("refresh", "Looking for cheats…", "")]]
        if (r.error || !r.cheats.length) return [[info("info", r.error || "No cheats in this game's list", emu)]]
        const on = r.cheats.filter(c => c.on).length
        return [[info("info", on ? on + " on" : "All off", "From " + r.source + " · applied when the game next starts")],
                r.cheats.map(c => ({ kind: "toggle", icon: "sparkle", title: c.name, sub: "", on: c.on,
                                     activate: () => sh(key, "python3 /usr/share/asgard/asgard-cheats.py set " + args + " "
                                                        + q(c.name) + " " + (c.on ? "off" : "on"), parse) }))]
    }

    // ROCKNIX's per-emulator options (es_features.cfg), read through thor_settings.py --features as JSON.
    // prefix: "<system>" or '<system>["<file>"]'; inherit: what an unset game option falls back to.
    function features(emu, core) {
        const k = "feat:" + emu + "/" + core
        if (live[k] === undefined) {
            note(k, null)
            backend.exec("python3 /usr/share/asgard/thor_settings.py --features " + q(emu) + " " + q(core),
                         o => { let v = []; try { v = JSON.parse(o) } catch (e) {} note(k, v) })
        }
        return live[k]
    }
    // Core types switched off, as a game would get them: its own value, else the system's, else stock (on): games
    // never inherit the Asgard menu's profile. The menu's own (prefix "asgard", keys asgard.cpu_cap.<type>) the same.
    // A core type is off when its clock is "off" (cpu_cap_<type>).
    // At least one type stays on (asgard-cpu-lib.sh keeps the prime core otherwise; the menus don't offer it).
    readonly property var coreTypes: ["little", "mid", "prime"]
    function allCoresOff(prefix, inherit, type, value) {
        const key = t => prefix === "asgard" ? "asgard.cpu_cap." + t : prefix + ".cpu_cap_" + t
        return coreTypes.every(t => {
            const own = t === type ? value : get(key(t))
            return (own || (inherit ? get(inherit + ".cpu_cap_" + t) : "")) === "off"
        })
    }
    function optionRow(f, prefix, inherit) {
        const key = prefix + "." + f.key
        const cur = get(key)
        // A value between the choices (the OS's brightness 45, the choices 10% steps) gets their unit too
        const pct = f.choices.length > 0 && f.choices.every(c => c[0] === c[1] + "%")
        const label = v => (f.choices.find(c => c[1] === v) || [pct ? v + "%" : v])[0]
        const parent = inherit ? get(inherit + "." + f.key) : ""
        const values = [""].concat(f.choices.map(c => c[1]))
        const type = f.key.startsWith("cpu_cap_") ? f.key.slice(8) : ""
        // Unset takes the parent's setting: the emulator's, else the OS's (thor_settings.py "default": stock clocks,
        // gyro off, the image's Mesa), else just "Default".
        // osKey: the OS's value is a setting, read now because the features are cached.
        // An empty OS value (the drivers, GPU-4: none chosen) is the image's, f.default.
        const osValue = f.osKey ? get(f.osKey, f.osDefault) : ""
        const os = osValue ? label(osValue) : f.default
        const unset = parent ? "Emulator settings (" + label(parent) + ")" : os ? "OS (" + os + ")" : "Default"
        return { kind: "choice", icon: "chip", title: f.label, sub: "", value: cur ? label(cur) : unset,
                 step: d => { let i = Math.max(0, values.indexOf(cur))
                              for (let n = 0; n < values.length; n++) {   // skip a value that turns every core type off
                                  i = (i + d + values.length) % values.length
                                  if (!type || !allCoresOff(prefix, inherit, type, values[i])) break
                              }
                              set(key, values[i]) } }
    }
    // GPU-4: the Vulkan and OpenGL drivers for every game (asgard.gpu_driver / asgard.gl_driver, runemu.sh). A system's or
    // game's own choice wins. The rows and the image's defaults are the emulator options' (thor_settings.py, any emulator).
    function osDriverRows() {
        const feats = features("os", "os")
        if (!feats) return [info("chip", "Graphics drivers", "Loading…")]
        const subs = { gpu_driver: "Vulkan, for every game · a system's or game's own setting wins",
                       gl_driver: "OpenGL, for every game · a system's or game's own setting wins" }
        return feats.filter(f => subs[f.key]).map(f => {
            const key = "asgard." + f.key, cur = get(key)
            const values = [""].concat(f.choices.map(c => c[1]))
            return { kind: "choice", icon: "chip", title: f.key === "gpu_driver" ? "Vulkan driver" : "OpenGL driver", sub: subs[f.key],
                     value: cur ? (f.choices.find(c => c[1] === cur) || [cur])[0] : "Image's (" + f.default + ")",
                     step: d => set(key, values[(Math.max(0, values.indexOf(cur)) + d + values.length) % values.length]) }
        })
    }
    // The game's CPU and GPU cap rows, the same ones as its Emulator options (the in-game menu's Performance page).
    function perfRows(prefix, emu, core, inherit) {
        const feats = features(emu, core)
        return feats && feats.filter(f => f.key.startsWith("cpu_cap_") || f.key === "gpu_cap").map(f => optionRow(f, prefix, inherit))
    }
    // Its screen rows, by key: the in-game menu fits five rows to a page, so it picks what goes where.
    function screenRows(prefix, emu, core, inherit, keys) {
        const feats = features(emu, core)
        return feats && keys.map(k => feats.find(f => f.key === k)).filter(f => f).map(f => optionRow(f, prefix, inherit))
    }
    function optionsPage(prefix, emu, core, inherit) {
        const feats = features(emu, core)
        if (feats === null) return [[info("refresh", "Loading options…", emu + " / " + core)]]
        if (!feats.length) return [[info("info", "No extra options", emu + " / " + core + " has none")]]
        const row = f => optionRow(f, prefix, inherit)
        // Grouped features (thor_settings.py GROUPS: Hardware overrides, its core types and Sleep) are submenus, in
        // the order they first appear; a group "A/B" is submenu B inside A.
        const icons = { "Hardware overrides": "gauge", "Sleep": "moon", "Sound EQ": "speaker", "Top screen": "display", "Bottom screen": "display" }
        const level = (fs, depth) => {
            const out = [], groups = {}
            for (const f of fs) {
                const path = f.group ? f.group.split("/") : []
                if (path.length <= depth) { out.push(row(f)); continue }
                const name = path[depth]
                if (!groups[name]) {
                    const g = groups[name] = []
                    out.push(link(icons[name] || "chip", name, "", () => level(g, depth + 1)))
                }
                groups[name].push(f)
            }
            for (const r of out)   // a group's link shows its rows' current values
                if (r.kind === "link") r.sub = r.page()[0].map(x => x.kind === "link" ? x.title : x.value).join(" · ")
            return [out]
        }
        return level(feats, 0)
    }

    // RetroAchievements sign-in: ROCKNIX's RetroArch launcher builds cheevos_username/password from these keys on
    // every launch. An empty password keeps the saved one (changing only the username).
    // Library > Scrape missing (SCRAPE-1): asgard-scrape.py for each game without a cover, one at a time, in the
    // background (Settings can close). A again stops it. Home rescans every 10 games, so the art shows as it comes.
    property var scrapeQueue: []
    function scrapeMissing() {
        if (scrapeQueue.length) { scrapeQueue = []; note("scrape", "Stopped"); return }
        const todo = []
        for (const s of backend.systems)
            for (const g of backend.games(s.name))
                if (!g.cover) todo.push(g)
        if (!todo.length) { note("scrape", "Every game has a cover"); return }
        scrapeQueue = todo
        scrapeNext({ done: 0, got: 0, total: todo.length })
    }
    function scrapeNext(n) {
        const g = scrapeQueue[0]
        note("scrape", (n.done + 1) + " of " + n.total + " · " + g.name)
        backend.exec("python3 /usr/share/asgard/asgard-scrape.py " + [g.sys, g.path, g.stem].map(q).join(" "), out => {
            let r
            try { r = JSON.parse(out) } catch (e) { r = { error: "The scraper failed" } }
            if (!scrapeQueue.length) { backend.rescan(); return }          // stopped meanwhile
            n.done++
            if (!r.error) n.got++
            const offline = !!r.error && r.error.startsWith("No internet")
            scrapeQueue = offline ? [] : scrapeQueue.slice(1)
            if (scrapeQueue.length) {
                if (n.done % 10 === 0) backend.rescan()
                scrapeNext(n)
                return
            }
            note("scrape", offline ? r.error : "Done: found " + n.got + " of " + n.total + " games")
            backend.rescan()
        })
    }

    // ScreenScraper sign-in (SCRAPE-1): asgard-scrape.py passes it to Skyscraper. An empty password keeps the saved one;
    // an empty username signs out.
    function ssSignIn() {
        keyboard.ask("ScreenScraper username", get("screenscraper.username"), false, u => {
            if (u === undefined || u === null) return
            if (!u.trim()) { set("screenscraper.username", ""); set("screenscraper.password", ""); return }
            set("screenscraper.username", u.trim())
            keyboard.ask("ScreenScraper password", "", true, p => { if (p) set("screenscraper.password", p) })
        })
    }

    function raSignIn() {
        keyboard.ask("RetroAchievements username", get("global.retroachievements.username"), false, u => {
            if (!u) return
            set("global.retroachievements.username", u.trim())
            keyboard.ask("RetroAchievements password", "", true, p => {
                if (p) set("global.retroachievements.password", p)
                set("global.retroachievements", "1")
            })
        })
    }
    function profilePage() {
        return [[info("user", "Name", backend.hostname + "  (system.hostname in asgard.yml)"),
                 action("trophy", "RetroAchievements", get("global.retroachievements.username") || "Not signed in", raSignIn),
                 action("list", "ScreenScraper", get("screenscraper.username") || "Not signed in", ssSignIn)]]
    }
    function consolesPage() {
        return [backend.systems.map(s => link("gamepad", s.fullname,
            (get(s.name + ".emulator") || s.emulator) + " / " + (get(s.name + ".core") || s.core), () => systemPage(s)))]
    }
    function systemPage(s) {
        const emus = backend.emulators(s.name)
        const emu = get(s.name + ".emulator", s.emulator)
        const cur = emus.find(e => e.name === emu) || emus[0]
        const rows = [{ kind: "choice", icon: "gamepad", title: "Emulator", sub: s.fullname, value: emu,
                        step: d => { const i = Math.max(0, emus.findIndex(e => e.name === emu));
                                     const e = emus[(i + d + emus.length) % emus.length]
                                     set(s.name + ".emulator", e.name); set(s.name + ".core", e.cores[0] || "") } }]
        if (cur && cur.cores.length > 1)
            rows.push({ kind: "choice", icon: "chip", title: "Core", sub: "RetroArch core", value: get(s.name + ".core", s.core),
                        step: d => { const c = get(s.name + ".core", s.core); const i = Math.max(0, cur.cores.indexOf(c))
                                     set(s.name + ".core", cur.cores[(i + d + cur.cores.length) % cur.cores.length]) } })
        rows.push(link("chip", "Emulator options", "Shaders, aspect ratio and more for " + s.fullname,
                       () => optionsPage(s.name, get(s.name + ".emulator", s.emulator), get(s.name + ".core", s.core), "")))
        rows.push(action("refresh", "Use default", s.emulator + " / " + s.core,
                         () => { set(s.name + ".emulator", ""); set(s.name + ".core", "") }))
        return [rows]
    }

    readonly property var page: groups()
    readonly property var flat: { const out = []; for (const g of page) for (const r of g) out.push(r); return out }

    function openRow(r) {
        if (!r) return
        if (r.kind === "link") {
            const build = typeof r.page === "function" && r.page.length === 0 ? r.page : null
            if (build) {
                stack = stack.concat([{ title: r.title, build: build, poll: r.poll }]); row = 0
                if (r.poll) r.poll()
                if (build === wifiPage) scan()
                if (build === btScanPage) btScanStart()
                if (build === batteryPage) { note("battery", null); sh("battery", "python3 /usr/share/asgard/battery-report.py", JSON.parse) }
            }
            else { r.page(); }
            rev++
        } else if (r.kind === "toggle") r.activate()
        else if (r.kind === "choice") r.step(1)
        else if (r.kind === "action") r.run()
    }

    // Returns true if the button was used.
    function nav(b) {
        if (!open) return false
        if (stickCal.nav(b)) return true
        if (keyboard.nav(b)) return true
        if (dialog.nav(b)) return true
        if (b === "start" || (b === "b" && zone === "side" && !stack.length)) { close(); return true }
        if (zone === "side") {
            if (b === "up") cat = (cat + categories.length - 1) % categories.length
            else if (b === "down") cat = (cat + 1) % categories.length
            else if ((b === "right" || b === "a") && flat.length) { zone = "list"; row = 0 }
            if (b === "up" || b === "down") { row = 0; stack = [] }
            return true
        }
        const r = flat[row]
        if (b === "up") row = Math.max(0, row - 1)
        else if (b === "down") row = Math.min(flat.length - 1, row + 1)
        else if (b === "a") openRow(r)
        else if ((b === "left" || b === "right") && r && r.kind === "choice") r.step(b === "left" ? -1 : 1)
        else if (b === "left" || b === "b") {
            if (stack.length === 1 && stack[0].closeOnBack) close()
            else if (stack.length) { stack = stack.slice(0, -1); row = 0 }
            else zone = "side"
        }
        return true
    }

    // --- look -----------------------------------------------------------------------------------------------------
    visible: open
    Rectangle { anchors.fill: parent; color: settings.menuStyle ? "#0b0c14" : "#80000000"; MouseArea { anchors.fill: parent } }

    Rectangle {
        id: sheet
        x: 36; y: 36; width: parent.width - 72; height: parent.height - 72; radius: 44
        color: "#ebedf2"; border.color: "#ffffff"; border.width: 2

        // categories
        Rectangle {
            id: side
            visible: !settings.menuStyle
            x: 22; y: 22; width: 340; height: parent.height - 44; radius: 32; color: "#e1e3ea"
            Text {
                x: 32; y: 26; text: settings.stack.length > 1 ? "‹  " + settings.stack[settings.stack.length - 2].title
                  : settings.stack.length ? "‹  " + settings.categories[settings.cat].title : "Settings"
                // long back labels ("‹  Emulator options") ran into the page title: shrink, then elide, inside the panel
                width: side.width - 2 * x; fontSizeMode: Text.HorizontalFit; minimumPixelSize: 28; elide: Text.ElideRight
                font.family: Theme.font; font.pixelSize: 40; font.weight: Font.Black; color: settings.ink
            }
            Column {
                y: 104; width: parent.width
                Repeater {
                    model: settings.categories
                    Item {
                        width: side.width; height: 86
                        readonly property bool on: index === settings.cat
                        Rectangle {
                            anchors.fill: parent; anchors.leftMargin: 10; anchors.rightMargin: 10; radius: 22
                            color: parent.on ? "#cfd2dc" : "transparent"
                            border.color: parent.on && settings.zone === "side" ? Theme.selA : "transparent"; border.width: 3
                        }
                        Image {
                            x: 34; anchors.verticalCenter: parent.verticalCenter; width: 38; height: 38
                            source: "icons/settings/" + modelData.icon + ".svg"; sourceSize: Qt.size(76, 76)
                        }
                        Text {
                            x: 90; anchors.verticalCenter: parent.verticalCenter
                            font.family: Theme.font; font.pixelSize: 33; font.weight: Font.ExtraBold
                            color: parent.on ? Theme.selB : settings.ink; text: modelData.title
                        }
                        MouseArea {
                            anchors.fill: parent
                            onClicked: { backend.sound("move"); settings.cat = index; settings.stack = []; settings.zone = "list"; settings.row = 0 }
                        }
                    }
                }
            }
        }

        // close
        Rectangle {
            visible: !settings.menuStyle
            anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 22
            width: 60; height: 60; radius: 30; color: "#d6d8e0"
            Text { anchors.centerIn: parent; text: "×"; font.family: Theme.font; font.pixelSize: 44; font.weight: Font.Black; color: settings.ink }
            MouseArea { anchors.fill: parent; onClicked: settings.close() }
        }

        // rows
        Flickable {
            id: list
            x: settings.menuStyle ? 32 : side.x + side.width + 26; y: settings.menuStyle ? 120 : 96
            width: parent.width - x - (settings.menuStyle ? 32 : 26); height: parent.height - y - 22
            clip: true; interactive: false
            // Row positions from the page itself (rowH a row, rowGap between rows, groupGap between groups): a change
            // rebuilds every row item, and positions read from the new items (not laid out yet) scrolled the list back
            // to the top.
            readonly property real rowY: {
                let y = 0, n = settings.row
                for (const g of settings.page) {
                    if (n < g.length) return y + n * (settings.rowH + settings.rowGap)
                    y += g.length * (settings.rowH + settings.rowGap) - settings.rowGap + settings.groupGap; n -= g.length
                }
                return 0
            }
            readonly property real pageHeight: settings.page.reduce((h, g) => h + g.length * (settings.rowH + settings.rowGap)
                                                                    - settings.rowGap + settings.groupGap, 0) - settings.groupGap
            contentHeight: pageHeight
            contentY: settings.zone !== "list" ? 0 : Math.max(0, Math.min(pageHeight - height, rowY - height / 2 + 60))
            Behavior on contentY { NumberAnimation { duration: Theme.anim } }

            Column {
                id: groupsCol
                width: list.width; spacing: settings.groupGap
                Repeater {
                    model: settings.page
                    Rectangle {
                        id: group
                        readonly property int base: { let n = 0; for (let g = 0; g < index; g++) n += settings.page[g].length; return n }
                        width: groupsCol.width; height: rows.height; radius: 28
                        color: settings.menuStyle ? "transparent" : settings.card
                        Column {
                            id: rows
                            width: parent.width; spacing: settings.rowGap
                            Repeater {
                                model: modelData
                                Item {
                                    readonly property int flatIndex: group.base + index
                                    readonly property bool sel: settings.zone === "list" && flatIndex === settings.row
                                    width: rows.width; height: settings.rowH
                                    Rectangle {  // the selection; in menuStyle, the tile itself (the menu's own)
                                        anchors.fill: parent; anchors.margins: settings.menuStyle ? 0 : 6
                                        radius: settings.menuStyle ? 30 : 22
                                        color: parent.sel ? "#e6ecff" : settings.menuStyle ? settings.card : "transparent"
                                        border.color: parent.sel ? Theme.selA : "transparent"; border.width: 3
                                    }
                                    Rectangle {  // separator
                                        visible: index > 0 && !settings.menuStyle; x: 28; width: parent.width - 56; height: 2; color: settings.line
                                    }
                                    Image {
                                        x: settings.menuStyle ? 30 : 34; anchors.verticalCenter: parent.verticalCenter
                                        width: settings.menuStyle ? 52 : 44; height: width
                                        source: "icons/settings/" + modelData.icon + ".svg"; sourceSize: Qt.size(104, 104)
                                    }
                                    Column {
                                        x: 104; anchors.verticalCenter: parent.verticalCenter
                                        width: parent.width - x - ({ link: 100, action: 100, toggle: 140, choice: 230 }[modelData.kind] || 30)
                                        Text {
                                            width: parent.width; elide: Text.ElideRight; text: modelData.title
                                            font.family: Theme.font; font.pixelSize: settings.menuStyle ? 34 : 32; font.weight: Font.Black
                                            color: settings.ink
                                        }
                                        Text {
                                            width: parent.width; elide: Text.ElideRight; text: modelData.sub || ""; visible: text !== ""
                                            font.family: Theme.font; font.pixelSize: settings.menuStyle ? 22 : 24; font.weight: Font.Bold
                                            color: settings.inkDim
                                        }
                                    }
                                    // right side: chevron (link/action), switch (toggle), value (choice)
                                    Rectangle {
                                        visible: (modelData.kind === "link" || modelData.kind === "action") && !settings.menuStyle
                                        anchors.right: parent.right; anchors.rightMargin: 30; anchors.verticalCenter: parent.verticalCenter
                                        width: 50; height: 50; radius: 25; color: settings.ink
                                        Text { anchors.centerIn: parent; anchors.horizontalCenterOffset: 2; text: "›"; color: "white"
                                               font.pixelSize: 40; font.weight: Font.Black }
                                    }
                                    Rectangle {
                                        visible: modelData.kind === "toggle"
                                        anchors.right: parent.right; anchors.rightMargin: 30; anchors.verticalCenter: parent.verticalCenter
                                        width: 92; height: 50; radius: 25
                                        color: modelData.on ? Theme.selB : "#c9cbd6"
                                        Behavior on color { ColorAnimation { duration: Theme.anim } }
                                        Rectangle {
                                            width: 40; height: 40; radius: 20; color: "white"; y: 5
                                            x: modelData.on ? parent.width - width - 5 : 5
                                            Behavior on x { NumberAnimation { duration: Theme.anim; easing.type: Easing.OutCubic } }
                                        }
                                    }
                                    Text {
                                        visible: modelData.kind === "choice"
                                        anchors.right: parent.right; anchors.rightMargin: 32; anchors.verticalCenter: parent.verticalCenter
                                        text: "‹  " + (modelData.value || "") + "  ›"
                                        font.family: Theme.font; font.pixelSize: 30; font.weight: Font.Black; color: Theme.selB
                                    }
                                    MouseArea {
                                        anchors.fill: parent
                                        onClicked: { backend.sound("select"); settings.zone = "list"; settings.row = parent.flatIndex; settings.openRow(modelData) }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
        // page title on the right when a sub-page is open; in menuStyle, where the menu has "Paused"
        Text {
            x: settings.menuStyle ? 44 : list.x + 8; y: settings.menuStyle ? 34 : 30
            width: parent.width - x - (settings.menuStyle ? 260 : 110); elide: Text.ElideRight
            text: settings.stack.length ? settings.stack[settings.stack.length - 1].title : settings.categories[settings.cat].title
            font.family: Theme.font; font.pixelSize: settings.menuStyle ? 44 : 40; font.weight: Font.Black; color: settings.ink
        }
        Text {                               // menuStyle: the menu's hint, where Settings has its close button
            visible: settings.menuStyle
            anchors.right: parent.right; anchors.rightMargin: 44; y: 46
            text: "B  back"; font.family: Theme.font; font.pixelSize: 28; font.weight: Font.Bold; color: settings.inkDim
            MouseArea { anchors.fill: parent; anchors.margins: -20; onClicked: settings.nav("b") }
        }
    }

    Timer {
        interval: 3000; repeat: true
        running: settings.open && settings.stack.length > 0 && !!settings.stack[settings.stack.length - 1].poll
        onTriggered: settings.stack[settings.stack.length - 1].poll()
    }
    Confirm { id: dialog; anchors.fill: parent }
    Keyboard { id: keyboard; anchors.fill: parent }
    StickCal { id: stickCal; anchors.fill: parent }
}
