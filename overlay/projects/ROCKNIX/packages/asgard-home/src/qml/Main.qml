import QtQuick
import QtQuick.Effects
import QtQuick.Window

// Asgard Home: iiSU-style dual-screen frontend. Top window = hero card + status; bottom window = dock + tile grid.
// Both windows are driven by one nav() from the gamepad (Backend's Gamepad) or the keyboard (desktop).
QtObject {
    id: app

    // --- state ------------------------------------------------------------------------------------------------
    property int tab: 0                      // 0 home, 1 games (systems), 2 trophies
    property var stack: []                   // views opened from a tab: [{items, sel}]
    property var items: homeItems()
    property int sel: 0
    property var pendingRa: null             // trophy game whose achievement list is being fetched
    // The grid (and Settings) on the top screen by default, the detail card below; L+R swaps them.
    property bool swapped: backend.getSetting("asgard.swap_screens", "1") === "1"
    property bool details: false             // Select: the top card shows the selection's details
    readonly property var current: items.length ? items[Math.min(sel, items.length - 1)] : null
    readonly property var cells: layout(items)
    Component.onCompleted: {
        Theme.accent = backend.getSetting("asgard.accent", "aurora")
        Theme.animations = backend.getSetting("asgard.animations", "1") === "1"
    }

    readonly property bool gameSettingsHere: !!(current && current.game && current.kind !== "jump")

    function homeItems() {
        const out = []
        const bg = backend.background        // a game left with "Back to Home": first, to return to it
        if (bg.path)
            out.push({ kind: "jump", game: bg })
        for (const s of ordered(backend.systems))
            out.push({ kind: "system", sys: s })
        return out
    }
    function tabItems(t) {
        if (t === 0) return homeItems()
        if (t === 1) return ordered(backend.systems).map(s => ({ kind: "system", sys: s }))
        if (t === 2) return achievements.games.map(e => ({ kind: "ra", game: e.game, ra: e }))
        return []                            // profile / apps: not built yet
    }

    // Columns of 253 px tiles with 44 px gaps that fit the grid window (4 on the bottom screen, 6 on the top one).
    readonly property int cols: Math.max(3, Math.floor((Math.round(1080 * bottom.width / Math.max(1, bottom.height)) - 92 + 44) / 297))
    // Flow over `cols` columns; "jump" takes two cells. Returns [{col, row, w}] parallel to items.
    function layout(list) {
        const out = []; let col = 0, row = 0
        for (const it of list) {
            const w = it.kind === "jump" ? 2 : 1
            if (col + w > cols) { col = 0; row++ }
            out.push({ col: col, row: row, w: w })
            col += w
            if (col >= cols) { col = 0; row++ }
        }
        return out
    }
    // --- tile order: Y or a long press lifts the selected tile; the d-pad or a drag moves it, A / letting go /
    // a tap where it should go keeps the order, B cancels. Systems (asgard.order) and each system's games
    // (asgard.order.<system>, file names) have their own order.
    property var order: backend.getSetting("asgard.order", "").split(",").filter(x => x)   // system names
    property string openSys: ""              // the system whose games are shown, "" at the top level
    property bool reordering: false
    property var reorderBackup: null
    function ordered(list) {   // saved order first; systems not in it keep their place after
        const ranked = []
        for (let i = 0; i < list.length; i++) {   // ranks by position: list elements are fresh wrappers each read
            const k = order.indexOf(list[i].name)
            ranked.push({ s: list[i], r: k < 0 ? 1000 + i : k })
        }
        return ranked.sort((a, b) => a.r - b.r).map(x => x.s)
    }
    function orderedGames(sys, games) {   // saved order (file names) first, the rest after in their own order
        const names = backend.getSetting("asgard.order." + sys, "").split("|").filter(x => x)
        const ranked = []
        for (let i = 0; i < games.length; i++) {
            const k = names.indexOf(games[i].path.split("/").pop())
            ranked.push({ g: games[i], r: k < 0 ? 100000 + i : k })
        }
        return ranked.sort((a, b) => a.r - b.r).map(x => x.g)
    }
    readonly property bool canReorder: !!current && ((!stack.length && tab < 2 && current.kind === "system")
                                                     || (openSys !== "" && current.kind === "game"))
    function startReorder() {
        if (!canReorder) return
        reorderBackup = items; reordering = true
    }
    function moveTo(t) {       // only tiles of the same kind trade places (the jump tile stays first)
        if (t < 0 || t >= items.length || t === sel || items[t].kind !== items[sel].kind) return
        const l = items.slice(); const it = l.splice(sel, 1)[0]; l.splice(t, 0, it)
        items = l; sel = t
    }
    function endReorder(keep) {
        reordering = false
        if (!keep) { items = reorderBackup; return }
        if (openSys !== "") {
            backend.setSetting("asgard.order." + openSys, items.map(i => i.game.path.split("/").pop()).join("|"))
            return
        }
        order = items.filter(i => i.kind === "system").map(i => i.sys.name)
        backend.setSetting("asgard.order", order.join(","))
    }

    // asgard-scrape.py: cover + screenshot (libretro; ScreenScraper once a developer ID is set) into ES-DE's media.
    function scrape() {
        const g = current && current.game, m = bottom.gameActionsPanel
        if (!g) return
        const q = v => "'" + String(v).replace(/'/g, "'\\''") + "'"
        m.status = "Scraping " + g.name + "…"
        backend.exec("python3 /usr/share/asgard/asgard-scrape.py " + [g.sys, g.path, g.stem].map(q).join(" "), out => {
            let r
            try { r = JSON.parse(out) } catch (e) { r = { error: "The scraper failed" } }
            m.status = r.error || "Got the " + r.media.join(" and ") + " from " + r.source + (r.matched ? " (" + r.matched + ")" : "")
            if (!r.error) backend.rescan()
        })
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
        if (backend.gameMenu) { backend.sound(b === "a" ? "select" : b === "b" ? "back" : "move"); (swapped ? top.gameMenuPanel : bottom.gameMenuPanel).nav(b); return }
        if (backend.playing) return
        if (backend.screensOff) { backend.screensOff = false; return }   // any button only wakes the screens
        backend.sound(b === "a" ? "select" : b === "b" || b === "x" ? "back" : b === "start" || b === "select"
                      ? (bottom.settingsPanel.open ? "back" : "open") : "move")
        if (bottom.confirmPanel.nav(b)) return
        if (bottom.settingsPanel.nav(b)) return                            // Settings open: it takes the buttons
        if (bottom.powerMenuPanel.nav(b)) return
        if (b === "x") { backend.screensOff = true; return }              // X: both OLED panels off
        // Start: the game's settings in a game list; Settings everywhere else, the "Return to game" tile included.
        if (b === "start") { if (gameSettingsHere) bottom.settingsPanel.showGame(current.game); else bottom.settingsPanel.show(); return }
        if (bottom.gameActionsPanel.nav(b)) return
        // Select: a game's menu (scrape, details); details anywhere else.
        if (b === "select") { if (gameSettingsHere) { bottom.gameActionsPanel.status = ""; bottom.gameActionsPanel.show() } else details = !details; return }
        if (reordering) {
            const rc = cells[sel]
            if (b === "left") moveTo(sel - 1)
            else if (b === "right") moveTo(sel + 1)
            else if ((b === "up" || b === "down") && rc) moveTo(itemAt(rc.row + (b === "up" ? -1 : 1), rc.col))
            else if (b === "a" || b === "y") endReorder(true)
            else if (b === "b") endReorder(false)
            return
        }
        if (b === "y") { startReorder(); return }
        if (b === "lr") { swapScreens(); return }
        if (b === "b" && details) { details = false; return }
        const c = cells[sel]
        if (b === "left" && sel > 0) sel--
        else if (b === "right" && sel < items.length - 1) sel++
        else if ((b === "up" || b === "down") && c) {
            const i = itemAt(c.row + (b === "up" ? -1 : 1), c.col)
            if (i >= 0) sel = i
        } else if (b === "lb" || b === "rb") {
            setTab((tab + (b === "lb" ? 2 : 1)) % 3)
        } else if (b === "a" && current) {
            if (current.kind === "system") {
                stack = stack.concat([{ items: items, sel: sel }])
                openSys = current.sys.name
                items = orderedGames(openSys, backend.games(openSys)).map(g => ({ kind: "game", game: g })); sel = 0
            } else if (current.kind === "ra") {
                stack = stack.concat([{ items: items, sel: sel }])
                const picked = current               // items = [] below makes current null
                pendingRa = picked; items = []; sel = 0
                achievements.details(picked.ra.raId)
            } else if (current.kind === "jump") {
                backend.resumeGame()
            } else if (current.kind === "game") {
                const bg = backend.background, g = current.game
                if (!bg.path) backend.launch(g)
                else if (bg.path === g.path) backend.resumeGame()
                else bottom.confirmPanel.open("Close " + bg.name + "?", bg.name + " is in the background. Close it to start "
                                              + g.name + "; unsaved progress is lost.", "Close it",
                                              () => { pendingLaunch = g; backend.quitGame() })
            }
        } else if (b === "b" && stack.length) {
            const top = stack[stack.length - 1]
            stack = stack.slice(0, -1); items = top.items; sel = top.sel; openSys = ""
        }
    }

    // The game picked after "Close it": started once the background game has exited.
    property var pendingLaunch: null
    property Connections bgGame: Connections { target: backend; function onPlayingChanged() { app.gameStateChanged() } }
    function gameStateChanged() {
        if (!stack.length && tab === 0) items = tabItems(0)   // the Return tile comes and goes
        if (pendingLaunch && !backend.playing && !backend.background.path) {
            const g = pendingLaunch; pendingLaunch = null
            Qt.callLater(() => backend.launch(g))
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

    // The two windows trade titles, and so screens: sway's assign rules place them by title whenever they map
    // (after every game), and they are moved now. The choice survives restarts (asgard.swap_screens).
    function swapScreens() {
        swapped = !swapped
        backend.setSetting("asgard.swap_screens", swapped ? "1" : "0")
        backend.shell("sleep 0.3; swaymsg '[title=\"^Asgard Home$\"] move container to output DSI-2, fullscreen enable';"
                      + " swaymsg '[title=\"^Asgard Home .Bottom.$\"] move container to output DSI-1, fullscreen enable'")
    }

    function setTab(t) {
        tab = t; stack = []; items = tabItems(t); sel = 0; openSys = ""
    }
    // Bottom touchscreen: a tap opens the tile, like moving there and pressing A.
    function tap(i) {
        if (backend.playing) return
        if (backend.screensOff) { backend.screensOff = false; return }
        if (reordering) { moveTo(i); endReorder(true); return }   // tap where the lifted tile goes
        sel = i
        nav("a")
    }
    function longPress(i) {   // lift the tile (then drag it, or use the d-pad)
        if (backend.playing || reordering) return
        sel = i
        startReorder()
    }

    function key(event) {
        if (debugInput) console.log("input: key", event.key)
        const k = { [Qt.Key_Left]: "left", [Qt.Key_Right]: "right", [Qt.Key_Up]: "up", [Qt.Key_Down]: "down",
                    [Qt.Key_Return]: "a", [Qt.Key_Enter]: "a", [Qt.Key_Escape]: "b", [Qt.Key_Backspace]: "b",
                    [Qt.Key_X]: "x", [Qt.Key_Y]: "y", [Qt.Key_Q]: "lb", [Qt.Key_E]: "rb", [Qt.Key_W]: "lr",
                    [Qt.Key_Minus]: "select", [Qt.Key_Plus]: "start", [Qt.Key_Equal]: "start" }[event.key]
        if (k) { nav(k); event.accepted = true }
    }

    readonly property string art: current ? (current.game ? (current.game.shot || current.game.cover || "")
                                                          : (current.sys.cover || current.sys.art || "")) : ""

    // --- top screen -----------------------------------------------------------------------------------------
    property Window top: Window {
        title: app.swapped ? "Asgard Home (Bottom)" : "Asgard Home"   // sway places our windows by title
        width: app.swapped ? 1240 : 1920; height: 1080; color: "#0b0c14"   // sway's fullscreen sets the real size
        visible: !shotMode && (!backend.playing || (backend.gameMenu && app.swapped))  // swapped: it's below, with the in-game menu
        property alias gameMenuPanel: topGameMenu

        // Laid out 1080 tall and as wide as the screen the window is on (1920 on top, 1240 below; L+R swaps them),
        // scaled to the panel's pixels.
        Item {
            id: topStage
            width: parent.height > 0 ? Math.round(1080 * parent.width / parent.height) : 1920
            height: 1080; anchors.centerIn: parent; scale: parent.height / 1080

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
            }

            PointHandler {
                enabled: debugInput; target: null
                acceptedDevices: PointerDevice.AllDevices
                onActiveChanged: if (active) console.log("input: TOP", point.device.type === PointerDevice.TouchScreen ? "touch" : "pointer",
                                                         Math.round(point.position.x), Math.round(point.position.y))
            }
            // The in-game menu belongs on the physical bottom screen: here when the screens are swapped.
            GameMenu { id: topGameMenu; anchors.fill: parent; z: 200; visible: open && app.swapped }
            HeroCard {
                x: (parent.width - width) / 2; y: 232; width: 1150; height: 650
                item: app.current
                details: app.details
                placeholder: ["Home", "Games", "Trophies"][app.tab]
            }

            Pill {
                x: parent.width - width + 60; y: 984; width: hints.implicitWidth + 130; height: 92
                transformOrigin: Item.Right; scale: Math.min(1, (parent.width + 40) / width)   // narrow (bottom) screen
                Row {
                    id: hints
                    x: 40; anchors.verticalCenter: parent.verticalCenter; spacing: 30
                    Hint { visible: app.reordering; glyph: "✥"; label: "Move" }
                    Hint { visible: app.reordering; glyph: "A"; label: "Done" }
                    Hint { visible: app.reordering; glyph: "B"; label: "Cancel" }
                    Hint {
                        visible: !app.reordering && !!app.current && app.current.kind !== "ach"
                        glyph: "A"; label: app.current && (app.current.kind === "system" || app.current.kind === "ra") ? "Open" : "Play"
                    }
                    Hint { visible: !app.reordering; glyph: "B"; label: "Back" }
                    Hint { visible: !app.reordering; glyph: "X"; label: "Screens off" }
                    Hint { visible: !app.reordering; glyph: "−"; label: "Details" }
                    Hint { visible: !app.reordering && app.canReorder
                           glyph: "Y"; label: "Reorder"; onTapped: app.startReorder() }
                    Hint { visible: !app.reordering; glyph: "LR"; label: "Swap"; onTapped: app.swapScreens() }
                    Hint { visible: !app.reordering; glyph: "+"; label: app.gameSettingsHere ? "Game settings" : "Settings"
                           onTapped: { backend.sound("open"); app.nav("start") } }
                }
            }
        }
    }

    // --- bottom screen --------------------------------------------------------------------------------------
    property Window osd: Osd {}   // volume/brightness slider, over games too

    property Window bottom: Window {
        title: app.swapped ? "Asgard Home" : "Asgard Home (Bottom)"
        width: app.swapped ? 1920 : 1240; height: 1080; color: "#0b0c14"
        visible: !shotMode && (!backend.playing || (backend.gameMenu && !app.swapped))  // the in-game menu shows below
        property alias settingsPanel: settingsPanel
        property alias confirmPanel: confirmPanel
        property alias gameMenuPanel: gameMenuPanel
        property alias powerMenuPanel: powerMenuPanel
        property alias gameActionsPanel: gameActionsPanel

        // Laid out 1080 tall and as wide as the screen the window is on, like the top window; the grid takes as many
        // columns as fit (4 below, 6 on the top screen).
        Item {
            id: bottomStage
            width: parent.height > 0 ? Math.round(1080 * parent.width / parent.height) : 1240
            height: 1080; anchors.centerIn: parent; scale: parent.height / 1080

            Backdrop { anchors.fill: parent; source: app.art; dim: 0.62 }
            Item {
                anchors.fill: parent; focus: true
                Keys.onPressed: event => app.key(event)
            }

            Dock { x: 10; y: 28; current: app.tab; onTabTapped: index => app.setTab(index) }
            // Power: a round button at the right end of the top bar, opening the small power menu.
            Pill {
                id: powerButton
                x: parent.width - width - 24; y: 28; width: 150; height: 150
                Image {
                    anchors.centerIn: parent; width: 72; height: 72
                    source: "icons/power.svg"; sourceSize: Qt.size(144, 144)
                }
                TapHandler { onTapped: { backend.sound("open"); powerMenuPanel.anchorRight = powerButton.x + powerButton.width; powerMenuPanel.show() } }
            }
            // ASGARD_DEBUG_INPUT: log every touch/pointer press the bottom window receives (passive, blocks nothing).
            Component.onCompleted: if (debugInput) console.log("input: debug logging on (bottom window)")
            PointHandler {
                enabled: debugInput; target: null
                acceptedDevices: PointerDevice.AllDevices
                onActiveChanged: if (active) console.log("input:", point.device.type === PointerDevice.TouchScreen ? "touch" : "pointer",
                                                         Math.round(point.position.x), Math.round(point.position.y))
            }

            Rectangle {  // the glass panel holding the grid
                id: panel
                x: 0; y: 214; width: parent.width; height: parent.height - y + 60; radius: 48
                color: Theme.panel; border.color: Theme.panelRim; border.width: 3
                clip: true

                readonly property int pad: 46
                readonly property real xoff: (width - (app.cols * tile + (app.cols - 1) * gap)) / 2   // centre the columns
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

                    // Swipe up/down: on release the selection moves by the rows swiped, and the grid follows it.
                    // While a tile is lifted, dragging moves it to the cell under the finger and letting go keeps it.
                    DragHandler {
                        target: null
                        onCentroidChanged: if (active && app.reordering) {
                            const p = centroid.position   // content coordinates (this handler lives in the content)
                            const col = Math.floor((p.x - panel.xoff) / (panel.tile + panel.gap))
                            const row = Math.floor((p.y - panel.pad) / (panel.tile + panel.gap))
                            if (col >= 0 && col < app.cols && row >= 0) app.moveTo(app.itemAt(row, col))
                        }
                        onActiveChanged: if (!active && app.reordering) app.endReorder(true)
                                         else if (!active && app.cells.length) {
                            const rows = Math.round(-centroid.position.y + centroid.pressPosition.y) / (panel.tile + panel.gap)
                            const step = Math.round(rows)
                            if (!step) return
                            const c = app.cells[app.sel], last = app.cells[app.cells.length - 1].row
                            const i = app.itemAt(Math.max(0, Math.min(last, c.row + step)), c.col)
                            if (i >= 0) app.sel = i
                        }
                    }

                    Repeater {
                        model: app.items
                        Tile {
                            // while items change, old delegates briefly see the new (shorter) layout
                            readonly property var cell: app.cells[index] || ({ col: 0, row: 0, w: 1 })
                            item: modelData
                            selected: index === app.sel
                            lifted: app.reordering && index === app.sel
                            near: y + height > flick.contentY - 400 && y < flick.contentY + flick.height + 400
                            onTapped: app.tap(index)
                            onLongPressed: app.longPress(index)
                            x: panel.xoff + cell.col * (panel.tile + panel.gap)
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

            // Every system's artwork and logo stays decoded (same source and size as the tiles, so they share the cache
            // entry): going back to the systems grid used to reload them from disk, a visible blink of empty tiles.
            Repeater {
                model: backend.systems
                Item {
                    visible: false
                    Image { asynchronous: true; sourceSize: Qt.size(320, 0); source: modelData.art || modelData.cover || "" }
                    Image { asynchronous: true; sourceSize: Qt.size(400, 0); source: modelData.logo || "" }
                }
            }
            Settings { id: settingsPanel; anchors.fill: parent; z: 100 }
            Confirm { id: confirmPanel; anchors.fill: parent; z: 150 }
            GameMenu { id: gameMenuPanel; anchors.fill: parent; z: 200; visible: open && !app.swapped }
            PowerMenu { id: powerMenuPanel; anchors.fill: parent; z: 150 }
            PowerMenu {
                id: gameActionsPanel; anchors.fill: parent; z: 150; anchorRight: parent.width - 24
                items: [{ icon: "refresh", title: "Scrape this game", keep: true, run: app.scrape },
                        { icon: "info", title: "Details", run: () => app.details = !app.details }]
            }
        }
    }
}
