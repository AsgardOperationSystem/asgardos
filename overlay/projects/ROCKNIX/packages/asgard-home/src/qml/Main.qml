import QtQuick
import QtQuick.Effects
import QtQuick.Window

// Asgard Home: iiSU-style dual-screen frontend. Top window = hero card + status; bottom window = dock + tile grid.
// Both windows are driven by one nav() from the gamepad (Backend's Gamepad) or the keyboard (desktop).
QtObject {
    id: app

    // --- state ------------------------------------------------------------------------------------------------
    property int tab: 0                      // 0 home, 1 games (systems), 2 trophies, 3 profile, 4 apps
    property var stack: []                   // views opened from a tab: [{items, sel}]
    property var items: homeItems()
    property int sel: 0
    property var pendingRa: null             // trophy game whose achievement list is being fetched
    readonly property var current: items.length ? items[Math.min(sel, items.length - 1)] : null
    readonly property var cells: layout(items)

    function homeItems() {
        const out = []
        const recent = backend.recent
        if (recent.length)
            out.push({ kind: "jump", game: recent[0] })
        for (const s of backend.systems)
            out.push({ kind: "system", sys: s })
        for (const g of recent.slice(1, 9))
            out.push({ kind: "game", game: g })
        return out
    }
    function tabItems(t) {
        if (t === 0) return homeItems()
        if (t === 1) return backend.systems.map(s => ({ kind: "system", sys: s }))
        if (t === 2) return achievements.games.map(e => ({ kind: "ra", game: e.game, ra: e }))
        return []                            // profile / apps: not built yet
    }

    // 4-column flow; "jump" takes two cells. Returns [{col, row, w}] parallel to items.
    function layout(list) {
        const out = []; let col = 0, row = 0
        for (const it of list) {
            const w = it.kind === "jump" ? 2 : 1
            if (col + w > 4) { col = 0; row++ }
            out.push({ col: col, row: row, w: w })
            col += w
            if (col >= 4) { col = 0; row++ }
        }
        return out
    }
    function itemAt(row, col) {
        let best = -1
        for (let i = 0; i < cells.length; i++) {
            const c = cells[i]
            if (c.row !== row) continue
            if (col >= c.col && col < c.col + c.w) return i
            best = i                         // short last row: fall back to its last item
        }
        return best
    }

    function nav(b) {
        if (backend.playing) return
        if (backend.screensOff) { backend.screensOff = false; return }   // any button only wakes the screens
        if (b === "x") { backend.screensOff = true; return }              // X: both OLED panels off
        const c = cells[sel]
        if (b === "left" && sel > 0) sel--
        else if (b === "right" && sel < items.length - 1) sel++
        else if ((b === "up" || b === "down") && c) {
            const i = itemAt(c.row + (b === "up" ? -1 : 1), c.col)
            if (i >= 0) sel = i
        } else if (b === "lb" || b === "rb") {
            tab = (tab + (b === "lb" ? 4 : 1)) % 5
            stack = []; items = tabItems(tab); sel = 0
        } else if (b === "a" && current) {
            if (current.kind === "system") {
                stack = stack.concat([{ items: items, sel: sel }])
                items = backend.games(current.sys.name).map(g => ({ kind: "game", game: g })); sel = 0
            } else if (current.kind === "ra") {
                stack = stack.concat([{ items: items, sel: sel }])
                const picked = current               // items = [] below makes current null
                pendingRa = picked; items = []; sel = 0
                achievements.details(picked.ra.raId)
            } else if (current.kind === "game" || current.kind === "jump") {
                backend.launch(current.game)
            }
        } else if (b === "b" && stack.length) {
            const top = stack[stack.length - 1]
            stack = stack.slice(0, -1); items = top.items; sel = top.sel
        }
    }

    property Connections padInput: Connections { target: pad; function onPressed(button) { app.nav(button) } }
    property Connections library: Connections {
        target: backend
        function onLibraryChanged() { if (!app.stack.length) app.items = app.tabItems(app.tab) }
    }
    property Connections trophies: Connections {
        target: achievements
        function onGamesChanged() { if (app.tab === 2 && !app.stack.length) app.items = app.tabItems(2) }
        function onDetailsReady(raId, d) {
            const p = app.pendingRa
            if (!p || p.ra.raId !== raId || !app.stack.length) return
            app.items = d.achievements.map(a => ({ kind: "ach", ach: a, game: p.game, ra: p.ra }))
        }
    }

    function key(event) {
        const k = { [Qt.Key_Left]: "left", [Qt.Key_Right]: "right", [Qt.Key_Up]: "up", [Qt.Key_Down]: "down",
                    [Qt.Key_Return]: "a", [Qt.Key_Enter]: "a", [Qt.Key_Escape]: "b", [Qt.Key_Backspace]: "b",
                    [Qt.Key_X]: "x", [Qt.Key_Y]: "y", [Qt.Key_Q]: "lb", [Qt.Key_E]: "rb",
                    [Qt.Key_Minus]: "select", [Qt.Key_Plus]: "start", [Qt.Key_Equal]: "start" }[event.key]
        if (k) { nav(k); event.accepted = true }
    }

    readonly property string art: current ? (current.game ? (current.game.shot || current.game.cover || "")
                                                          : (current.sys.cover || "")) : ""

    // --- top screen -----------------------------------------------------------------------------------------
    property Window top: Window {
        title: "Asgard Home"
        width: 1920; height: 1080; color: "#0b0c14"
        visible: !shotMode && !backend.playing

        Backdrop { anchors.fill: parent; source: app.art }
        Item {
            anchors.fill: parent; focus: true
            Keys.onPressed: event => app.key(event)
        }

        // status: who / where (left), time · date · battery (right)
        Pill {
            x: -60; y: 62; width: 660; height: 96
            Text {
                x: 100; anchors.verticalCenter: parent.verticalCenter
                font.family: Theme.font; font.pixelSize: 40; font.weight: Font.Black; color: Theme.text
                text: "●  " + backend.hostname
            }
            Tag { text: "LT"; anchors.right: parent.right; anchors.rightMargin: 34; y: -22 }
        }
        Pill {
            x: parent.width - width + 60; y: 62; width: statusRow.implicitWidth + 140; height: 96
            Row {
                id: statusRow
                x: 50; anchors.verticalCenter: parent.verticalCenter; spacing: 22
                property date now: new Date()
                Timer { interval: 1000; running: true; repeat: true; onTriggered: statusRow.now = new Date() }
                Text {
                    font.family: Theme.font; font.pixelSize: 40; font.weight: Font.Black; color: Theme.text
                    text: Qt.formatTime(statusRow.now, "hh:mm") + "  |  " + Qt.formatDate(statusRow.now, "MM/dd") +
                          (backend.battery >= 0 ? "  |  " + backend.battery + "%" : "")
                }
                Battery {
                    visible: backend.battery >= 0; anchors.verticalCenter: parent.verticalCenter
                    level: backend.battery; charging: backend.charging
                }
            }
            Tag { text: "RT"; x: 34; y: -22 }
        }

        HeroCard {
            x: 385; y: 232; width: 1150; height: 650
            item: app.current
            placeholder: ["Home", "Games", "Trophies", "Profile", "Apps"][app.tab]
        }

        Pill {
            x: parent.width - width + 60; y: 984; width: hints.implicitWidth + 130; height: 92
            Row {
                id: hints
                x: 40; anchors.verticalCenter: parent.verticalCenter; spacing: 30
                Hint {
                    visible: !!app.current && app.current.kind !== "ach"
                    glyph: "A"; label: app.current && (app.current.kind === "system" || app.current.kind === "ra") ? "Open" : "Play"
                }
                Hint { glyph: "B"; label: "Back" }
                Hint { glyph: "X"; label: "Screens off" }
                Hint { glyph: "−"; label: "Details" }
                Hint { glyph: "+"; label: "Menu" }
            }
        }
    }

    // --- bottom screen --------------------------------------------------------------------------------------
    property Window bottom: Window {
        title: "Asgard Home (Bottom)"
        width: 1240; height: 1080; color: "#0b0c14"
        visible: !shotMode && !backend.playing

        Backdrop { anchors.fill: parent; source: app.art; dim: 0.62 }
        Item {
            anchors.fill: parent; focus: true
            Keys.onPressed: event => app.key(event)
        }

        Dock { x: 10; y: 28; current: app.tab }
        Rectangle {  // avatar
            x: 1010; y: 20; width: 166; height: 166; radius: 83
            color: "#2b2c40"; border.color: Theme.pillRim; border.width: 4
            Image { anchors.fill: parent; anchors.margins: 10; source: "icons/profile.svg"; sourceSize: Qt.size(300, 300) }
        }

        Rectangle {  // the glass panel holding the grid
            id: panel
            x: 0; y: 214; width: parent.width; height: parent.height - y + 60; radius: 48
            color: Theme.panel; border.color: Theme.panelRim; border.width: 3
            clip: true

            readonly property int pad: 46
            readonly property int tile: 253
            readonly property int gap: 44

            Flickable {
                id: flick
                anchors.fill: parent; interactive: false
                contentHeight: (app.cells.length ? app.cells[app.cells.length - 1].row + 1 : 0) * (panel.tile + panel.gap) + panel.pad * 2
                // The selected row stays the second visible row once there is one above it.
                contentY: app.cells.length ? Math.max(0, Math.min((app.cells[Math.min(app.sel, app.cells.length - 1)].row - 1)
                          * (panel.tile + panel.gap), contentHeight - (1080 - 214) + 20)) : 0
                Behavior on contentY { NumberAnimation { duration: 260; easing.type: Easing.OutCubic } }

                Repeater {
                    model: app.items
                    Tile {
                        // while items change, old delegates briefly see the new (shorter) layout
                        readonly property var cell: app.cells[index] || ({ col: 0, row: 0, w: 1 })
                        item: modelData
                        selected: index === app.sel
                        near: y + height > flick.contentY - 400 && y < flick.contentY + flick.height + 400
                        x: panel.pad + cell.col * (panel.tile + panel.gap)
                        y: panel.pad + cell.row * (panel.tile + panel.gap)
                        width: cell.w * panel.tile + (cell.w - 1) * panel.gap
                        height: panel.tile
                    }
                }
            }
            Text {
                visible: app.items.length === 0
                anchors.centerIn: parent
                font.family: Theme.font; font.pixelSize: 48; font.weight: Font.Black; color: Theme.textDim
                text: app.tab === 2 ? (achievements.status || (app.stack.length ? "Loading…" : "No trophies yet")) : "Coming soon"
                width: parent.width - 120; horizontalAlignment: Text.AlignHCenter; wrapMode: Text.WordWrap
            }
        }
    }
}
