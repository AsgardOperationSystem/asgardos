import QtQuick

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
    signal closed()

    readonly property color ink: "#2a2b3d"
    readonly property color inkDim: "#6f7186"
    readonly property color card: "#fbfbfd"
    readonly property color line: "#e4e5ec"

    function show() { open = true; zone = "side"; row = 0; stack = []; rev++ }
    function close() { open = false; closed() }

    // --- content ------------------------------------------------------------------------------------------------
    readonly property var categories: [
        { title: "General", icon: "gear" }, { title: "Appearance", icon: "palette" }, { title: "Library", icon: "list" },
        { title: "Achievements", icon: "trophy" }, { title: "Audio", icon: "speaker" }, { title: "Display", icon: "display" },
        { title: "Performance", icon: "gauge" }, { title: "Network", icon: "wifi" }, { title: "About", icon: "info" }]

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
    function link(icon, title, sub, page) { return { kind: "link", icon: icon, title: title, sub: sub, page: page } }
    function action(icon, title, sub, run) { return { kind: "action", icon: icon, title: title, sub: sub, run: run } }
    function info(icon, title, sub) { return { kind: "info", icon: icon, title: title, sub: sub } }

    readonly property var fanModes: [["Quiet", "quiet"], ["Smart", "moderate"], ["Sport", "aggressive"],
                                     ["30%", "77"], ["50%", "128"], ["75%", "191"], ["100%", "255"]]
    function fanNow() { const m = get("asgard.fan_manual"); return m ? m : get("cooling.profile", "moderate") }
    function setFan(v) {
        if (/^\d+$/.test(v)) {
            set("asgard.fan_manual", v)
            backend.shell("systemctl stop fancontrol; P=$(ls /sys/class/hwmon/hwmon*/pwm1 | head -1); echo 1 > ${P}_enable; echo " + v + " > $P")
        } else {
            set("asgard.fan_manual", ""); set("cooling.profile", v)
            backend.shell("systemctl restart fancontrol")
        }
    }

    // Groups of rows for a category (or the open sub-page).
    function groups() {
        rev                                                   // re-evaluate after changes
        if (stack.length) return stack[stack.length - 1].build()
        const user = get("global.retroachievements.username")
        switch (categories[cat].title) {
        case "General": return [
            [link("user", "Profile", backend.hostname + "  ·  RetroAchievements: " + (user || "not signed in"), profilePage)],
            [action("terminal", "Classic settings", "Game and system options, LEDs (Thor Settings)", () => backend.openSettings({}, "main"))]]
        case "Appearance": return [
            [choice("palette", "Accent colour", "Selection glow and highlights", "asgard.accent", "aurora",
                    [["Aurora", "aurora"], ["Sunset", "sunset"], ["Mint", "mint"], ["Gold", "gold"]], v => Theme.accent = v)],
            [toggle("sparkle", "Animations", "Motion when moving and opening", "asgard.animations", "1",
                    () => Theme.animations = get("asgard.animations", "1") === "1")]]
        case "Library": return [
            [link("gamepad", "Consoles", "Emulator and core for each system", consolesPage)],
            [action("refresh", "Rescan library", backend.systems.length + " systems", () => backend.rescan())]]
        case "Achievements": return [
            [toggle("trophy", "RetroAchievements", "In supported emulators", "global.retroachievements", "0"),
             toggle("trophy", "Hardcore mode", "No savestates, rewind or cheats; earns hardcore unlocks",
                    "global.retroachievements.hardcore", "0")],
            [info("user", "Account", (user || "Not signed in") + "  ·  web API key " +
                  (get("global.retroachievements.webapikey") ? "set" : "missing (asgard.yml)"))]]
        case "Audio": return [
            [choice("speaker", "Volume", "Speaker and headphones", "audio.volume", "50",
                    [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100].map(v => [v + "%", "" + v]), v => backend.shell("volume " + v))]]
        case "Display": return [
            [choice("display", "Brightness", "Both screens", "system.brightness", "50",
                    [10, 20, 30, 40, 50, 60, 70, 80, 90, 100].map(v => [v + "%", "" + v]), v => backend.shell("brightness set " + v)),
             choice("moon", "Screens off after", "Without input (OLED care)", "asgard.idle_blank", "300",
                    [["2 min", "120"], ["5 min", "300"], ["10 min", "600"], ["Never", "0"]],
                    () => backend.shell("systemctl restart thor-idle-blank"))]]
        case "Performance": return [
            [toggle("chip", "CPU clock cap", "~75% top clock: cooler and longer battery", "asgard.cpu_cap", "1",
                    () => backend.shell("/usr/lib/autostart/common/090-asgard-tuning")),
             { kind: "choice", icon: "fan", title: "Fan", sub: "Curve, or a fixed speed",
               value: (fanModes.find(m => m[1] === fanNow()) || fanModes[1])[0],
               step: d => { const i = Math.max(0, fanModes.findIndex(m => m[1] === fanNow()));
                            setFan(fanModes[(i + d + fanModes.length) % fanModes.length][1]) } }],
            [choice("battery", "Charge limit", "Stop charging at 80% (needs kernel patch 9003 to work)", "asgard.charge_limit", "80",
                    [["80%", "80"], ["Off", "100"]],
                    v => backend.shell("echo " + v + " > /sys/class/power_supply/battery/charge_control_end_threshold")),
             choice("moon", "Sleep mode", "What the power button does", "system.suspendmode", "mem",
                    [["Sleep", "mem"], ["Light sleep", "freeze"], ["Screen off only", "off"]], v => backend.shell("suspendmode " + v))]]
        case "Network": return [
            [action("wifi", "Wi-Fi", get("wifi.ssid") || "Not connected", () => backend.openSettings({}, "wifi")),
             action("bluetooth", "Bluetooth", "Pair controllers and headphones", () => backend.openSettings({}, "bluetooth"))],
            [toggle("terminal", "SSH", "Remote shell", "ssh.enabled", "0",
                    () => backend.shell("systemctl " + (get("ssh.enabled") === "1" ? "start" : "stop") + " sshd")),
             action("refresh", "Updates", "Check for a new build", () => backend.openSettings({}, "updates"))]]
        case "About": {
            const os = backend.osInfo()
            return [[info("info", "Asgard OS", "ROCKNIX " + (os.VERSION || "") + "  ·  built " + (os.BUILD_DATE || "")),
                     info("chip", "Device", "AYN Thor  ·  " + (os.HW_DEVICE || "SM8550")),
                     info("gamepad", "Library", backend.systems.length + " systems")]]
        }
        }
        return []
    }
    function profilePage() {
        return [[info("user", "Name", backend.hostname + "  (system.hostname in asgard.yml)"),
                 info("trophy", "RetroAchievements", get("global.retroachievements.username") || "Not signed in"),
                 info("list", "ScreenScraper", get("screenscraper.username") || "Not set (asgard.yml)")]]
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
        rows.push(action("refresh", "Use ROCKNIX default", s.emulator + " / " + s.core,
                         () => { set(s.name + ".emulator", ""); set(s.name + ".core", "") }))
        return [rows]
    }

    readonly property var page: groups()
    readonly property var flat: { const out = []; for (const g of page) for (const r of g) out.push(r); return out }

    function openRow(r) {
        if (!r) return
        if (r.kind === "link") {
            const build = typeof r.page === "function" && r.page.length === 0 ? r.page : null
            if (build) { stack = stack.concat([{ title: r.title, build: build }]); row = 0 }
            else { r.page(); }
            rev++
        } else if (r.kind === "toggle") r.activate()
        else if (r.kind === "choice") r.step(1)
        else if (r.kind === "action") r.run()
    }

    // Returns true if the button was used.
    function nav(b) {
        if (!open) return false
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
            if (stack.length) { stack = stack.slice(0, -1); row = 0 }
            else zone = "side"
        }
        return true
    }

    // --- look -----------------------------------------------------------------------------------------------------
    visible: open
    Rectangle { anchors.fill: parent; color: "#80000000"; MouseArea { anchors.fill: parent } }

    Rectangle {
        id: sheet
        x: 36; y: 36; width: parent.width - 72; height: parent.height - 72; radius: 44
        color: "#ebedf2"; border.color: "#ffffff"; border.width: 2

        // categories
        Rectangle {
            id: side
            x: 22; y: 22; width: 340; height: parent.height - 44; radius: 32; color: "#e1e3ea"
            Text {
                x: 32; y: 26; text: settings.stack.length ? "‹  " + settings.categories[settings.cat].title : "Settings"
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
                            onClicked: { settings.cat = index; settings.stack = []; settings.zone = "list"; settings.row = 0 }
                        }
                    }
                }
            }
        }

        // close
        Rectangle {
            anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 22
            width: 60; height: 60; radius: 30; color: "#d6d8e0"
            Text { anchors.centerIn: parent; text: "×"; font.family: Theme.font; font.pixelSize: 44; font.weight: Font.Black; color: settings.ink }
            MouseArea { anchors.fill: parent; onClicked: settings.close() }
        }

        // rows
        Flickable {
            id: list
            x: side.x + side.width + 26; y: 96; width: parent.width - x - 26; height: parent.height - y - 22
            clip: true; interactive: false
            contentHeight: groupsCol.height
            contentY: {
                const r = rowItems[settings.row]
                if (!r || settings.zone !== "list") return 0
                return Math.max(0, Math.min(contentHeight - height, r.mapToItem(groupsCol, 0, 0).y - height / 2 + 60))
            }
            Behavior on contentY { NumberAnimation { duration: Theme.anim } }
            property var rowItems: []

            Column {
                id: groupsCol
                width: list.width; spacing: 22
                Repeater {
                    model: settings.page
                    Rectangle {
                        id: group
                        readonly property int base: { let n = 0; for (let g = 0; g < index; g++) n += settings.page[g].length; return n }
                        width: groupsCol.width; height: rows.height; radius: 28; color: settings.card
                        Column {
                            id: rows
                            width: parent.width
                            Repeater {
                                model: modelData
                                Item {
                                    readonly property int flatIndex: group.base + index
                                    readonly property bool sel: settings.zone === "list" && flatIndex === settings.row
                                    Component.onCompleted: { const a = list.rowItems.slice(); a[flatIndex] = this; list.rowItems = a }
                                    width: rows.width; height: 112
                                    Rectangle {
                                        anchors.fill: parent; anchors.margins: 6; radius: 22
                                        color: parent.sel ? "#e6ecff" : "transparent"
                                        border.color: parent.sel ? Theme.selA : "transparent"; border.width: 3
                                    }
                                    Rectangle {  // separator
                                        visible: index > 0; x: 28; width: parent.width - 56; height: 2; color: settings.line
                                    }
                                    Image {
                                        x: 34; anchors.verticalCenter: parent.verticalCenter; width: 44; height: 44
                                        source: "icons/settings/" + modelData.icon + ".svg"; sourceSize: Qt.size(88, 88)
                                    }
                                    Column {
                                        x: 104; anchors.verticalCenter: parent.verticalCenter
                                        width: parent.width - x - ({ link: 100, action: 100, toggle: 140, choice: 230 }[modelData.kind] || 30)
                                        Text {
                                            width: parent.width; elide: Text.ElideRight; text: modelData.title
                                            font.family: Theme.font; font.pixelSize: 32; font.weight: Font.Black; color: settings.ink
                                        }
                                        Text {
                                            width: parent.width; elide: Text.ElideRight; text: modelData.sub || ""; visible: text !== ""
                                            font.family: Theme.font; font.pixelSize: 24; font.weight: Font.Bold; color: settings.inkDim
                                        }
                                    }
                                    // right side: chevron (link/action), switch (toggle), value (choice)
                                    Rectangle {
                                        visible: modelData.kind === "link" || modelData.kind === "action"
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
                                        onClicked: { settings.zone = "list"; settings.row = parent.flatIndex; settings.openRow(modelData) }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
        // page title on the right when a sub-page is open
        Text {
            x: list.x + 8; y: 30; visible: true
            text: settings.stack.length ? settings.stack[settings.stack.length - 1].title : settings.categories[settings.cat].title
            font.family: Theme.font; font.pixelSize: 40; font.weight: Font.Black; color: settings.ink
        }
    }
}
