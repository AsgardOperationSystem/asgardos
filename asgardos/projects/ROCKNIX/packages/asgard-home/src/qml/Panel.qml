import QtQuick
import QtQuick.Window

// Thor Panel (asgard-panel --panel): the AYN button's quick panel on the bottom screen, in Settings' look. Page 1:
// FPS, quick toggles in AYN's order, temperature, fan (a control: left / right / A step its mode), CPU/GPU/PWR/RAM
// gauges; page 2: volume and per-screen brightness, with a lock that moves both screens together. `panel` asks
// thor_panel.py (panel.cpp) for the status every 2 s and runs the toggles. D-pad + A or touch; LB / RB = page. The
// pad is grabbed (the paused game never sees it); only the AYN button closes it (thor_ayn_button.py), or Quit game.
Window {
    id: win
    title: "Thor Panel (Bottom)"   // "Bottom": ROCKNIX's sway rules put it on DSI-1; thor-sway-rotate.sh makes it fullscreen
    width: 1240; height: 1080; color: "#0b0c14"; visible: !shotMode

    readonly property color ink: "#2a2b3d"
    readonly property color inkDim: "#6f7186"
    readonly property color card: "#fbfbfd"
    readonly property color off: "#e1e3ea"

    property var s: ({})                     // thor_panel.py's status
    property int page: 0
    property int sel: 0                      // page 1: tiles 0-7, 8 = the fan card
    property int sel2: 0                     // page 2: sliders 0-2, 3 = the lock
    property var live: ({})                  // slider -> [value, time]: what was just set, shown before status has it
    property string toast: ""
    property string clock: Qt.formatTime(new Date(), "h:mm")

    readonly property var icons: ({ wifi: "wifi", airplane: "airplane", vibrate: "vibrate", led: "bulb", shot: "camera",
                                    clean: "broom", task: "power", fpsmode: "display" })
    readonly property var tiles: s.toggles || ["Wi-Fi", "Airplane mode", "Vibration", "Ambient LED", "Screenshot",
        "Clean memory", "Quit game", "120 Hz"].map((l, i) => ({ key: Object.keys(icons)[i], label: l, on: false }))
    readonly property var sliders: [{ key: "vol", title: "Volume" }, { key: "top", title: "Top screen" },
                                    { key: "bottom", title: "Bottom screen" }]

    function poll() {
        panel.call("status", "", j => { const d = JSON.parse(j); if (d && !d.error) { s = d; Theme.accent = d.accent } })
    }
    function act(key) {
        panel.call(key, "", j => { const m = JSON.parse(j); if (m === "close") Qt.quit(); else if (m) say(m); poll() })
    }
    function say(m) { toast = m; toastTimer.restart() }
    function value(key) {
        const l = live[key]
        return l && Date.now() - l[1] < 1500 ? l[0] : s[key] !== undefined ? s[key] : 50
    }
    function slide(key, v) {
        v = Math.round(Math.max(0, Math.min(100, v)))
        const l = Object.assign({}, live)
        for (const k of key !== "vol" && s.linked !== false ? ["top", "bottom"] : [key]) l[k] = [v, Date.now()]
        live = l
        panel.call(key, "" + v, null)        // thor_panel.py applies the newest value per slider
    }

    Timer { interval: 2000; running: true; repeat: true; triggeredOnStart: true; onTriggered: win.poll() }
    Timer { interval: 5000; running: true; repeat: true; onTriggered: win.clock = Qt.formatTime(new Date(), "h:mm") }
    Timer { id: toastTimer; interval: 2000; onTriggered: win.toast = "" }

    Connections {
        target: pad
        function onPressed(b) {
            if (b === "lb" || b === "rb") { win.page = 1 - win.page; return }
            if (win.page) {
                if (b === "up" || b === "down") win.sel2 = (win.sel2 + (b === "down" ? 1 : 3)) % 4
                else if (win.sel2 === 3 && (b === "left" || b === "right" || b === "a")) win.act("lock")
                else if (b === "left" || b === "right") {
                    const k = win.sliders[win.sel2].key
                    win.slide(k, win.value(k) + (b === "right" ? 5 : -5))
                }
                return
            }
            const i = win.sel
            if (i === 8) {                   // the fan card
                if (b === "up") win.sel = 4
                else if (b === "left") win.act("fan-")
                else if (b === "right" || b === "a") win.act("fan")
            }
            else if (b === "left" && i % 4) win.sel = i - 1
            else if (b === "right" && i % 4 < 3) win.sel = i + 1
            else if (b === "down") win.sel = i < 4 ? i + 4 : 8
            else if (b === "up" && i >= 4) win.sel = i - 4
            else if (b === "a") win.act(win.tiles[i].key)
        }                                    // B, Start...: nothing (only AYN closes)
    }

    component Card: Rectangle { radius: 28; color: win.card }
    component Selection: Rectangle {         // Settings' selected row
        property bool on
        anchors.fill: parent; anchors.margins: 6; radius: 22
        color: on ? "#e6ecff" : "transparent"; border.color: on ? Theme.selA : "transparent"; border.width: 3
    }
    component Label: Text { font.family: Theme.font; font.weight: Font.Black; color: win.ink }
    component Accent: Gradient {
        orientation: Gradient.Horizontal
        GradientStop { position: 0; color: Theme.selA }
        GradientStop { position: 1; color: Theme.selB }
    }

    Item {
        width: parent.height > 0 ? Math.round(1080 * parent.width / parent.height) : 1240
        height: 1080; anchors.centerIn: parent; scale: parent.height / 1080

        Rectangle {
            id: sheet
            x: 36; y: 36; width: parent.width - 72; height: parent.height - 72; radius: 44
            color: "#ebedf2"; border.color: "white"; border.width: 2

            // status: time, page tabs, network and battery
            Label { x: 40; y: 30; text: win.clock; font.pixelSize: 44 }
            Row {
                anchors.horizontalCenter: parent.horizontalCenter; y: 28; spacing: 12
                Repeater {
                    model: ["Controls", "Sound & light"]
                    Rectangle {
                        width: 220; height: 64; radius: 32
                        color: index === win.page ? "transparent" : win.off
                        gradient: index === win.page ? accent : null
                        Accent { id: accent }
                        Label { anchors.centerIn: parent; text: modelData; font.pixelSize: 26; color: index === win.page ? "white" : win.ink }
                        TapHandler { onTapped: win.page = index }
                    }
                }
            }
            Row {
                anchors.right: parent.right; anchors.rightMargin: 40; y: 40; spacing: 14
                Label { text: (win.s.net || 0).toFixed(1) + " KB/s"; font.pixelSize: 26; font.weight: Font.Bold; color: win.inkDim
                        anchors.verticalCenter: parent.verticalCenter }
                Image { width: 40; height: 40; sourceSize: Qt.size(80, 80); anchors.verticalCenter: parent.verticalCenter
                        source: "icons/settings/battery.svg" }
                Label { text: (win.s.bat || "?") + "%" + (win.s.charging ? " ⚡" : ""); font.pixelSize: 32
                        anchors.verticalCenter: parent.verticalCenter }
            }

            // ---- page 1 ----
            Item {
                anchors.fill: parent; visible: win.page === 0

                Card {                       // FPS
                    x: 24; y: 116; width: 380; height: 440
                    Label { x: 32; y: 28; text: "Current FPS"; font.pixelSize: 28; color: win.inkDim }
                    Row {
                        anchors.horizontalCenter: parent.horizontalCenter; y: 120
                        Label { id: fps; readonly property bool known: win.s.fps !== undefined && win.s.fps !== null
                                text: known ? Math.round(win.s.fps) : "–"; font.pixelSize: 150; color: known ? win.ink : win.inkDim }
                        Label { text: "FPS"; font.pixelSize: 36; color: win.inkDim; anchors.baseline: fps.baseline; leftPadding: 10 }
                    }
                    Label { x: 32; y: 370; width: parent.width - 64; elide: Text.ElideRight; font.pixelSize: 26; font.weight: Font.Bold
                            color: win.inkDim; text: "Top screen at " + (win.tiles[7].on ? 120 : 60) + " Hz" }
                }

                Card {                       // quick toggles, 4 x 2
                    x: 424; y: 116; width: 720; height: 440
                    Grid {
                        x: 0; y: 0; columns: 4
                        Repeater {
                            model: win.tiles
                            Item {
                                width: 180; height: 220
                                Selection { on: win.sel === index }
                                Rectangle {
                                    anchors.horizontalCenter: parent.horizontalCenter; y: 24
                                    width: 108; height: 108; radius: 54
                                    color: modelData.on ? "transparent" : win.off
                                    gradient: modelData.on ? tileOn : null
                                    Accent { id: tileOn }
                                    Image { anchors.centerIn: parent; width: 52; height: 52; sourceSize: Qt.size(104, 104)
                                            source: "icons/settings/" + win.icons[modelData.key] + ".svg" }
                                }
                                Label {
                                    x: 8; y: 142; width: parent.width - 16; horizontalAlignment: Text.AlignHCenter
                                    wrapMode: Text.WordWrap; maximumLineCount: 2; elide: Text.ElideRight; lineHeight: 0.9
                                    text: modelData.label; font.pixelSize: 25; font.weight: Font.ExtraBold
                                }
                                TapHandler { onTapped: { win.sel = index; win.act(modelData.key) } }
                            }
                        }
                    }
                }

                Card {                       // temperature
                    x: 24; y: 576; width: 180; height: 348
                    Image { x: 24; y: 26; width: 40; height: 40; sourceSize: Qt.size(80, 80); source: "icons/settings/thermo.svg" }
                    Label { x: 70; y: 28; text: "Temp"; font.pixelSize: 28; color: win.inkDim }
                    Label { anchors.centerIn: parent; anchors.verticalCenterOffset: 10; font.pixelSize: 58
                            text: Math.round(win.s.temp || 0) + "°C" }
                }
                Card {                       // fan: tap / A = next mode, left / right step
                    x: 224; y: 576; width: 180; height: 348
                    Selection { on: win.sel === 8 }
                    Image { x: 24; y: 26; width: 40; height: 40; sourceSize: Qt.size(80, 80); source: "icons/settings/fan.svg" }
                    Label { x: 70; y: 28; text: "Fan"; font.pixelSize: 28; color: win.inkDim }
                    Label { x: 14; width: parent.width - 28; y: 126; horizontalAlignment: Text.AlignHCenter
                            fontSizeMode: Text.HorizontalFit; minimumPixelSize: 30; font.pixelSize: 50; color: Theme.selB
                            text: win.s.fan_mode || "Smart" }
                    Label { x: 14; width: parent.width - 28; y: 200; horizontalAlignment: Text.AlignHCenter; font.pixelSize: 24
                            font.weight: Font.Bold; color: win.inkDim; text: (win.s.fan_fixed ? "Fixed" : "Curve") }
                    Label { x: 14; width: parent.width - 28; y: 234; horizontalAlignment: Text.AlignHCenter; font.pixelSize: 24
                            font.weight: Font.Bold; color: win.inkDim; text: "now " + (win.s.fan || 0) + "%" }
                    Label { anchors.horizontalCenter: parent.horizontalCenter; y: 284; text: "‹      ›"; font.pixelSize: 30
                            color: Theme.selB; visible: win.sel === 8 }
                    TapHandler { onTapped: { win.sel = 8; win.act("fan") } }
                }

                Card {                       // gauges
                    x: 424; y: 576; width: 720; height: 348
                    Row {
                        Repeater {
                            model: win.s.gauges || []
                            Item {
                                width: 180; height: 348
                                Canvas {
                                    id: ring
                                    x: 15; y: 56; width: 150; height: 150
                                    property real frac: modelData.frac
                                    onFracChanged: requestPaint()
                                    onPaint: {
                                        const c = getContext("2d")
                                        c.reset(); c.lineWidth = 14; c.lineCap = "round"
                                        c.strokeStyle = String(win.off)
                                        c.beginPath(); c.arc(75, 75, 67, 0, 2 * Math.PI); c.stroke()
                                        const g = c.createLinearGradient(0, 0, 150, 150)
                                        g.addColorStop(0, String(Theme.selA)); g.addColorStop(1, String(Theme.selB))
                                        c.strokeStyle = g
                                        c.beginPath(); c.arc(75, 75, 67, -Math.PI / 2, -Math.PI / 2 + 2 * Math.PI * Math.max(0.01, frac)); c.stroke()
                                    }
                                    Column {
                                        anchors.centerIn: parent
                                        Label { anchors.horizontalCenter: parent.horizontalCenter; text: modelData.value; font.pixelSize: 34 }
                                        Label { anchors.horizontalCenter: parent.horizontalCenter; text: modelData.unit; font.pixelSize: 22
                                                font.weight: Font.Bold; color: win.inkDim }
                                    }
                                }
                                Label { anchors.horizontalCenter: parent.horizontalCenter; y: 236; text: modelData.name; font.pixelSize: 30 }
                            }
                        }
                    }
                }
            }

            // ---- page 2: volume and brightness; the lock beside the two screens ----
            Item {
                anchors.fill: parent; visible: win.page === 1

                Repeater {
                    model: win.sliders
                    Card {
                        id: row
                        readonly property int v: win.value(modelData.key)
                        x: 24; y: 116 + index * 270; width: index ? 900 : 1120; height: 248
                        Selection { on: win.sel2 === index }
                        Rectangle {          // icon bubble, as the OSD's
                            x: 30; anchors.verticalCenter: parent.verticalCenter; width: 120; height: 120; radius: 60
                            gradient: Accent {}
                            Image { anchors.centerIn: parent; width: 64; height: 64; sourceSize: Qt.size(128, 128)
                                    source: "icons/osd/" + (modelData.key !== "vol" ? "brightness" : row.v > 0 ? "volume" : "volume-mute") + ".svg" }
                        }
                        Label { x: track.x; y: 54; text: modelData.title; font.pixelSize: 36 }
                        Label { anchors.right: parent.right; anchors.rightMargin: 36; y: 44; text: row.v + "%"; font.pixelSize: 48 }
                        Rectangle {
                            id: track
                            x: 186; y: 150; width: parent.width - x - 50; height: 26; radius: 13; color: win.off
                            Rectangle {
                                width: Math.max(height, parent.width * row.v / 100); height: parent.height; radius: 13
                                visible: row.v > 0; gradient: Accent {}
                            }
                            Rectangle {      // knob
                                x: (parent.width - width) * row.v / 100; anchors.verticalCenter: parent.verticalCenter
                                width: 52; height: 52; radius: 26; color: "white"; border.color: "#c9cbd6"; border.width: 2
                            }
                        }
                        MouseArea {          // tap or drag anywhere on the row
                            anchors.fill: parent
                            function set(m) { win.sel2 = index; win.slide(modelData.key, (m.x - track.x) * 100 / track.width) }
                            onPressed: m => set(m)
                            onPositionChanged: m => set(m)
                        }
                    }
                }

                Card {                       // the lock: linked screens share one brightness
                    readonly property bool linked: win.s.linked !== false
                    x: 944; y: 386; width: 200; height: 518
                    Selection { on: win.sel2 === 3 }
                    Rectangle {
                        anchors.horizontalCenter: parent.horizontalCenter; y: 120; width: 120; height: 120; radius: 60
                        color: parent.linked ? "transparent" : win.off
                        gradient: parent.linked ? lockOn : null
                        Accent { id: lockOn }
                        Image { anchors.centerIn: parent; width: 58; height: 58; sourceSize: Qt.size(116, 116)
                                source: "icons/settings/" + (parent.parent.linked ? "lock" : "unlock") + ".svg" }
                    }
                    Label { anchors.horizontalCenter: parent.horizontalCenter; y: 270; font.pixelSize: 34
                            text: parent.linked ? "Linked" : "Separate" }
                    Label { x: 16; width: parent.width - 32; y: 320; horizontalAlignment: Text.AlignHCenter; wrapMode: Text.WordWrap
                            font.pixelSize: 22; font.weight: Font.Bold; color: win.inkDim
                            text: parent.linked ? "Both screens move together" : "Each screen on its own" }
                    TapHandler { onTapped: { win.sel2 = 3; win.act("lock") } }
                }
            }

            Label {
                anchors.horizontalCenter: parent.horizontalCenter; y: parent.height - 66
                text: "LB / RB  page     ·     AYN  close"; font.pixelSize: 26; font.weight: Font.Bold; color: win.inkDim
            }
        }

        Rectangle {                          // a toggle's message
            anchors.centerIn: parent; width: Math.max(420, msg.width + 100); height: 110; radius: 55
            color: win.ink; opacity: win.toast ? 0.96 : 0; visible: opacity > 0
            Behavior on opacity { NumberAnimation { duration: Theme.anim } }
            Label { id: msg; anchors.centerIn: parent; text: win.toast; font.pixelSize: 38; color: "white" }
        }
    }
}
