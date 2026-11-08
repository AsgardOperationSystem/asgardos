import QtQuick

// In-game menu on the bottom screen (Home tapped while a game runs; backend.gameMenu). The game is paused while it
// is open. Azahar and Eden get their hotkeys (quick save/load, screens, docked mode...), RetroArch its network
// commands and its own menu (on the top screen, in its window), Steam its overlay and Quick Access (not paused: Steam
// has no pause); others get Resume and Quit.
Item {
    id: menu
    property bool open: backend.gameMenu
    property int sel: 0
    property var game: []                    // running emulator process names, read when the menu opens
    property var settings: null              // the Settings panel: its option rows are the Performance page's
    property var launched: ({})              // the running game (backend.launchedGame), read when the menu opens
    property bool screenChanged: false       // a screen row changed: applied the same way
    property bool perfChanged: false         // a Performance row changed: apply it on leaving the page or the menu
    readonly property bool azahar: game.indexOf("azahar") >= 0
    readonly property bool eden: game.indexOf("eden") >= 0
    readonly property bool retroarch: game.indexOf("retroarch") >= 0
    readonly property bool steam: game.indexOf("steam") >= 0
    readonly property bool wwhd: game.indexOf("wwhd") >= 0

    property real openedAt: 0
    onOpenChanged: {
        if (open) {
            game = backend.runningGame(); launched = backend.launchedGame(); group = null; parents = []; sel = 0; openedAt = Date.now()
            if (hasPerf()) settings.features(perfEmu(), perfCore())   // loaded here: not from the page's binding
            if (settings) settings.eqRefresh()                        // the Sound page: what plays now, and its EQ
        } else {
            applyPerf()
            if (networkOpen) network.item.close()   // the game resumed or ended under it: stop a Bluetooth scan
        }
    }

    // Performance: the game's CPU and GPU caps and its screens, saved to its own keys as in its Settings page, so the next launch
    // loads them. Games only: a tool has no keys to save to.
    function hasPerf() { return game.length > 0 && !!launched.path }
    function perfFile() { return launched.path.split("/").pop() }
    function perfPrefix() { return launched.sys + '["' + perfFile() + '"]' }
    function perfEmu() { return settings.get(perfPrefix() + ".emulator", settings.get(launched.sys + ".emulator", launched.emulator)) }
    function perfCore() { return settings.get(perfPrefix() + ".core", settings.get(launched.sys + ".core", launched.core)) }
    function perfPage() {
        settings.rev                         // re-evaluate after changes
        const rows = settings.perfRows(perfPrefix(), perfEmu(), perfCore(), launched.sys)
        if (!rows) return [{ icon: "refresh", title: "Loading…", sub: "", run: () => {} }]
        return rows.map(r => {
            const step = d => { r.step(d); perfChanged = true }
            return { icon: "chip", title: r.title, sub: "‹  " + r.value + "  ›", step: step, run: () => step(1) }
        })
    }
    function screenPage(keys) {
        settings.rev
        const rows = settings.screenRows(perfPrefix(), perfEmu(), perfCore(), launched.sys, keys)
        if (!rows) return [{ icon: "refresh", title: "Loading…", sub: "", run: () => {} }]
        return rows.map(r => {
            const step = d => { r.step(d); screenChanged = true }
            return { icon: "display", title: r.title, sub: "‹  " + r.value + "  ›", step: step, run: () => step(1) }
        })
    }
    // Five rows to a page, Back among them, so a screen's colour is a page of its own.
    function colourTile(screen) {
        return { icon: "display", title: "Colour", sub: "Warmth, tint and contrast",
                 page: () => screenPage([screen + "_warmth", screen + "_tint", screen + "_contrast"]) }
    }
    function topScreenPage() { return screenPage(["top_refresh", "top_brightness", "top_ultra_black"]).concat([colourTile("top")]) }
    function bottomScreenPage() { return screenPage(["bottom_refresh", "bottom_brightness"]).concat([colourTile("bottom")]) }
    function perfTiles() {
        return [{ icon: "chip", title: "CPU and GPU", sub: "Clocks and cores", page: perfPage,
                  note: "Applies when you leave · A core type turned back on needs a game restart" },
                { icon: "display", title: "Top screen", sub: "Refresh, brightness, colour", page: topScreenPage, note: "Applies when you leave" },
                { icon: "display", title: "Bottom screen", sub: "Refresh, brightness, colour", page: bottomScreenPage, note: "Applies when you leave" }]
    }
    // Applied once, on the way out: the game is paused meanwhile, and each apply stops autotune and cycles the cores.
    // Guarded by the profile's marker: a game that ended with the menu open has had its restore already.
    function applyPerf() {
        const args = settings.q(launched.sys) + " " + settings.q(perfFile())
        if (perfChanged) {
            perfChanged = false
            backend.shell("[ -f /run/asgard-perf.saved ] && /usr/share/asgard/asgard-perf-profile.sh cpu " + args)
        }
        if (screenChanged) {
            screenChanged = false
            backend.shell("[ -f /run/asgard-perf.saved ] && /usr/share/asgard/asgard-perf-profile.sh screens " + args)
        }
    }

    // Wi-Fi and Bluetooth (MENU-6): Settings' own pages, on the menu's screen. The menu is in whichever window is on the
    // physical bottom screen and Settings in the other, so it has its own Settings, made the first time it's used.
    // Its tiles are a getter: read each time the sub-grid is shown, and again when the page closes (networkOpen is a
    // dependency of `shown`), so On / Off follows what was switched there rather than the menu's opening.
    function networkTile() {
        return { icon: "wifi", title: "Wi-Fi and Bluetooth", sub: "Networks, headphones, controllers", get items() {
            networkOpen
            return [
                { icon: "wifi", title: "Wi-Fi", sub: backend.getSetting("wifi.enabled", "1") === "1" ? "On" : "Off",
                  run: () => openNetwork("Wi-Fi") },
                { icon: "bluetooth", title: "Bluetooth", sub: backend.getSetting("bluetooth.enabled", "") === "1" ? "On" : "Off",
                  run: () => openNetwork("Bluetooth") }] } }
    }
    // Sound (SND-7): the EQ of the output that plays (the speaker, or the headphones in the jack) and its bass, mid and
    // treble, Settings' own rows, heard at once: set on the running EQ with no gap in the game's sound. Four rows and
    // Back fill the page. Bluetooth has no EQ, so it shows the speaker's and Back says so.
    function soundOut() {
        const e = settings.live.eq
        return e && e.output === "headphones" ? "headphones" : "speaker"
    }
    function soundPage() {
        settings.rev                         // re-evaluate after changes
        if (!settings.live.eq) return [{ icon: "refresh", title: "Loading…", sub: "", run: () => {} }]
        return settings.soundRows(soundOut()).map(r => ({ icon: "speaker", title: r.title, sub: "‹  " + r.value + "  ›",
                                                          step: r.step, run: () => r.step(1) }))
    }
    readonly property var soundTile: ({ icon: "speaker", title: "Sound", sub: "EQ, bass, mid and treble", page: () => soundPage(),
        get note() {
            settings.rev
            const e = settings.live.eq
            return e && e.output === "bluetooth" ? "Bluetooth has no EQ; these are the speaker's" : "Sound"
        } })
    function openNetwork(title) { network.active = true; network.item.showNetwork(title) }
    readonly property bool networkOpen: network.status === Loader.Ready && network.item.open

    function resume(keys) {                  // close, run the hotkeys, unpause
        backend.gameMenu = false
        for (const k of keys || []) backend.gameKeys(k)
        if (azahar || eden) backend.gameKeys("F4")
        if (retroarch) backend.retroarch("PAUSE_TOGGLE")
    }
    function raResume(cmd) {                 // a RetroArch command (it runs while paused), then unpause
        backend.retroarch(cmd)
        resume()
    }
    // The rarer and riskier actions sit in sub-grids (a tile with `items`), so a menu stays within the 5 rows the
    // bottom screen fits. Exit groups Back to Home, Restart, Quit and save log and Quit: Back to Home and the log
    // only for games (tools have no kill data to freeze); Back to Home resumes first so the menu's own pause
    // (RetroArch, Azahar, Eden) is undone. "Quit and save log" is for a hung game: keeps its log and a core dump.
    function withExit(list, restart, quit) {
        if (hasPerf())
            list = list.concat([{ icon: "gauge", title: "Performance", sub: "CPU, GPU and screens for this game", items: perfTiles() }])
        list = list.concat(settings ? [soundTile] : []).concat([networkTile()])
        const exit = (game.length ? [{ icon: "home", title: "Back to Home", sub: "The game waits in the background",
                                       run: () => { resume(); backend.toBackground() } }] : [])
            .concat(restart ? [restart] : [])
            .concat(game.length ? [{ icon: "save", title: "Quit and save log",
                                     sub: "For a hang: keeps its log and a core dump",
                                     run: () => backend.quitGame(true) }] : [])
            .concat([quit])
        return list.concat(exit.length > 1 ? [{ icon: "power", title: "Exit", items: exit,
                                                sub: restart ? "Home, restart or quit" : "Home or quit" }] : exit)
    }
    readonly property var quitGame: ({ icon: "power", title: "Quit game", sub: "Back to Asgard Home",
                                       run: () => backend.quitGame() })
    readonly property var restartKey: ({ icon: "refresh", title: "Restart", sub: "Unsaved progress is lost",
                                         run: () => { backend.gameMenu = false; backend.gameKeys("F6") } })
    readonly property var items: azahar ? withExit([
        { icon: "gamepad", title: "Resume", sub: "Back to the game", run: () => resume() },
        { icon: "save", title: "Quick save", sub: "Save state to the quick slot", run: () => resume(["Alt+S"]) },
        { icon: "load", title: "Quick load", sub: "Load the quick slot", run: () => resume(["Alt+L"]) },
        { icon: "display", title: "Screen", sub: "Swap, layout, HD textures", items: [
            { icon: "display", title: "Swap screens", sub: "Top and bottom trade places", run: () => resume(["F9"]) },
            { icon: "list", title: "Change layout", sub: "Next screen layout", run: () => resume(["F10"]) },
            { icon: "palette", title: "Custom textures", sub: "HD texture pack on / off", run: () => resume(["F7"]) }
        ] },
        { icon: "sparkle", title: "Screenshot", sub: "Saved by Azahar", run: () => resume(["Ctrl+P"]) }
    ], restartKey, quitGame) : steam ? withExit([
        { icon: "gamepad", title: "Resume", sub: "Back to the game", run: () => resume() },
        { icon: "list", title: "Steam overlay", sub: "Opens on the top screen",
          run: () => { backend.gameMenu = false; backend.padChord(["Gamepad:Button:Guide"]) } },
        { icon: "gear", title: "Quick Access", sub: "Steam's side menu",
          run: () => { backend.gameMenu = false; backend.padChord(["Gamepad:Button:QuickAccess"]) } }
    ], null, { icon: "power", title: "Exit Steam", sub: "Closes Steam and its game", run: () => backend.quitGame() })
    : retroarch ? withExit([
        { icon: "gamepad", title: "Resume", sub: "Back to the game", run: () => resume() },
        // Unpause first: RetroArch keeps a paused game paused after its menu closes.
        { icon: "list", title: "RetroArch menu", sub: "Opens on the top screen",
          run: () => { backend.gameMenu = false; backend.retroarch("PAUSE_TOGGLE"); backend.retroarch("MENU_TOGGLE") } },
        { icon: "save", title: "Quick save", sub: "Save state to the current slot", run: () => raResume("SAVE_STATE") },
        { icon: "load", title: "Quick load", sub: "Load the current slot", run: () => raResume("LOAD_STATE") },
        { icon: "sparkle", title: "Screenshot", sub: "Saved by RetroArch", run: () => raResume("SCREENSHOT") }
    ], { icon: "refresh", title: "Restart", sub: "Unsaved progress is lost", run: () => raResume("RESET") }, quitGame)
    : eden ? withExit([
        // No save states on Switch emulators: games save themselves.
        { icon: "gamepad", title: "Resume", sub: "Back to the game", run: () => resume() },
        { icon: "display", title: "Docked mode", sub: "Docked (sharper) / handheld (faster)", run: () => resume(["F10"]) },
        { icon: "gauge", title: "Speed limit", sub: "Unlock / restore the frame limit", run: () => resume(["Ctrl+U"]) },
        { icon: "chip", title: "Performance overlay", sub: "FPS and frame times", run: () => resume(["Ctrl+V"]) },
        { icon: "sparkle", title: "Screenshot", sub: "Saved by Eden", run: () => resume(["Ctrl+P"]) }
    ], restartKey, quitGame) : wwhd ? withExit([
        // Wind Waker HD's settings overlay (F1 in its TV window: graphics, display, GamePad screen, save states).
        { icon: "gamepad", title: "Resume", sub: "Back to the game", run: () => resume() },
        { icon: "gear", title: "Wind Waker HD settings", sub: "Opens on the top screen", run: () => resume(["F1"]) }
    ], null, quitGame) : withExit([
        { icon: "gamepad", title: "Resume", sub: "Back to the game", run: () => resume() }
    ], null, quitGame)

    property var group: null                 // the open sub-grid's tile, or null for the top level
    property int groupSel: 0                 // its index, to come back to it
    property var parents: []                 // the groups above it, each with its index
    readonly property bool onPage: !!group && !!group.page   // one column: left / right step the values
    readonly property var shown: group ? [{ icon: "list", title: "Back", sub: group.note || group.title, run: () => back() }]
                                         .concat(group.page ? group.page() : group.items) : items
    function activate(i) {
        const it = shown[i]
        if (it.items || it.page) { parents = parents.concat([{ group: group, sel: groupSel }]); group = it; groupSel = i; sel = 1 } else it.run()
    }
    function back() {
        const up = parents[parents.length - 1]
        sel = groupSel; group = up.group; groupSel = up.sel; parents = parents.slice(0, -1)
        applyPerf()
    }

    function nav(b) {
        if (!open) return false
        // A short tap of Home comes with an extra event (a long press doesn't) that reached the menu as it opened
        // and resumed the game at once: input in the first 400 ms is ignored.
        if (Date.now() - openedAt < 400) return true
        if (networkOpen) { network.item.nav(b); return true }   // B there closes it, back to this menu
        if (onPage && (b === "up" || b === "down" || b === "left" || b === "right")) {
            if (b === "up" && sel > 0) sel--
            else if (b === "down" && sel + 1 < shown.length) sel++
            else if ((b === "left" || b === "right") && shown[sel].step) shown[sel].step(b === "left" ? -1 : 1)
            return true
        }
        if (b === "up" && sel >= 2) sel -= 2
        else if (b === "down" && sel + 2 < shown.length) sel += 2
        else if (b === "left" && sel % 2) sel--
        else if (b === "right" && sel % 2 === 0 && sel + 1 < shown.length) sel++
        else if (b === "a") activate(sel)
        else if (b === "b" && group) back()
        else if (b === "b" || b === "start") resume()
        return true
    }

    visible: open
    Rectangle { anchors.fill: parent; color: "#0b0c14" }
    Rectangle {
        x: 36; y: 36; width: parent.width - 72; height: parent.height - 72; radius: 44
        color: "#ebedf2"; border.color: "white"; border.width: 2

        Text {
            id: pausedTitle
            x: 44; y: 34; text: "Paused"
            font.family: Theme.font; font.pixelSize: 44; font.weight: Font.Black; color: "#2a2b3d"
        }
        Text {                               // the game's rate over the last few seconds before the pause
            visible: backend.pauseFps >= 0
            anchors.left: pausedTitle.right; anchors.leftMargin: 24; anchors.baseline: pausedTitle.baseline
            text: backend.pauseFps + " FPS"; font.family: Theme.font; font.pixelSize: 28; font.weight: Font.Bold
            color: "#6f7186"
        }
        Text {
            anchors.right: parent.right; anchors.rightMargin: 44; y: 46
            text: group ? "B  back" : "B  resume"; font.family: Theme.font; font.pixelSize: 28; font.weight: Font.Bold; color: "#6f7186"
        }
        // two columns of big touch targets
        Grid {
            x: 32; y: 120; columns: menu.onPage ? 1 : 2; columnSpacing: 20; rowSpacing: 18
            Repeater {
                model: menu.shown
                Rectangle {
                    readonly property bool on: index === menu.sel
                    width: menu.onPage ? menu.width - 72 - 64 : (menu.width - 72 - 64 - 20) / 2; height: 150; radius: 30
                    color: on ? "#e6ecff" : "#fbfbfd"
                    border.color: on ? Theme.selA : "transparent"; border.width: 3
                    Image {
                        x: 30; anchors.verticalCenter: parent.verticalCenter; width: 52; height: 52
                        source: "icons/settings/" + modelData.icon + ".svg"; sourceSize: Qt.size(104, 104)
                    }
                    Column {
                        x: 104; anchors.verticalCenter: parent.verticalCenter; width: parent.width - x - 24
                        Text {
                            width: parent.width; elide: Text.ElideRight; text: modelData.title
                            font.family: Theme.font; font.pixelSize: 34; font.weight: Font.Black
                            color: modelData.icon === "power" ? "#c2334d" : "#2a2b3d"
                        }
                        Text {
                            width: parent.width; elide: Text.ElideRight; text: modelData.sub
                            font.family: Theme.font; font.pixelSize: 22; font.weight: Font.Bold; color: "#6f7186"
                        }
                    }
                    MouseArea {
                        anchors.fill: parent
                        onClicked: { backend.sound("select"); menu.sel = index; menu.activate(index) }
                    }
                }
            }
        }
    }
    Loader { id: network; anchors.fill: parent; active: false; z: 10; sourceComponent: Settings {} }
}
