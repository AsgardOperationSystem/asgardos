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
    readonly property bool azahar: game.indexOf("azahar") >= 0
    readonly property bool eden: game.indexOf("eden") >= 0
    readonly property bool retroarch: game.indexOf("retroarch") >= 0
    readonly property bool steam: game.indexOf("steam") >= 0
    readonly property bool wwhd: game.indexOf("wwhd") >= 0

    property real openedAt: 0
    onOpenChanged: if (open) { game = backend.runningGame(); group = null; sel = 0; openedAt = Date.now() }

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
    readonly property var shown: group ? [{ icon: "list", title: "Back", sub: group.title, run: () => back() }]
                                         .concat(group.items) : items
    function activate(i) {
        const it = shown[i]
        if (it.items) { group = it; groupSel = i; sel = 1 } else it.run()
    }
    function back() { sel = groupSel; group = null }

    function nav(b) {
        if (!open) return false
        // A short tap of Home comes with an extra event (a long press doesn't) that reached the menu as it opened
        // and resumed the game at once: input in the first 400 ms is ignored.
        if (Date.now() - openedAt < 400) return true
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
            x: 32; y: 120; columns: 2; columnSpacing: 20; rowSpacing: 18
            Repeater {
                model: menu.shown
                Rectangle {
                    readonly property bool on: index === menu.sel
                    width: (menu.width - 72 - 64 - 20) / 2; height: 150; radius: 30
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
}
