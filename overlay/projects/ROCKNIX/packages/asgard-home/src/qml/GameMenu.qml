import QtQuick

// In-game menu on the bottom screen (Home tapped while a game runs; backend.gameMenu). The game is paused while it
// is open. Azahar gets its hotkeys (quick save/load, screens, textures...); other emulators get Resume and Quit.
Item {
    id: menu
    property bool open: backend.gameMenu
    property int sel: 0
    property var game: []                    // running emulator process names, read when the menu opens
    readonly property bool azahar: game.indexOf("azahar") >= 0

    property real openedAt: 0
    onOpenChanged: if (open) { game = backend.runningGame(); sel = 0; openedAt = Date.now() }

    function resume(keys) {                  // close, run the hotkeys, unpause
        backend.gameMenu = false
        for (const k of keys || []) backend.gameKeys(k)
        if (azahar) backend.gameKeys("F4")
    }
    readonly property var items: azahar ? [
        { icon: "gamepad", title: "Resume", sub: "Back to the game", run: () => resume() },
        { icon: "save", title: "Quick save", sub: "Save state to the quick slot", run: () => resume(["Alt+S"]) },
        { icon: "load", title: "Quick load", sub: "Load the quick slot", run: () => resume(["Alt+L"]) },
        { icon: "display", title: "Swap screens", sub: "Top and bottom trade places", run: () => resume(["F9"]) },
        { icon: "list", title: "Change layout", sub: "Next screen layout", run: () => resume(["F10"]) },
        { icon: "palette", title: "Custom textures", sub: "HD texture pack on / off", run: () => resume(["F7"]) },
        { icon: "sparkle", title: "Screenshot", sub: "Saved by Azahar", run: () => resume(["Ctrl+P"]) },
        { icon: "refresh", title: "Restart", sub: "Unsaved progress is lost",
          run: () => { backend.gameMenu = false; backend.gameKeys("F6") } },
        { icon: "power", title: "Quit game", sub: "Back to Asgard Home", run: () => backend.quitGame() }
    ] : [
        { icon: "gamepad", title: "Resume", sub: "Back to the game", run: () => resume() },
        { icon: "power", title: "Quit game", sub: "Back to Asgard Home", run: () => backend.quitGame() }
    ]

    function nav(b) {
        if (!open) return false
        // A short tap of Home comes with an extra event (a long press doesn't) that reached the menu as it opened
        // and resumed the game at once: input in the first 400 ms is ignored.
        if (Date.now() - openedAt < 400) return true
        if (b === "up" && sel >= 2) sel -= 2
        else if (b === "down" && sel + 2 < items.length) sel += 2
        else if (b === "left" && sel % 2) sel--
        else if (b === "right" && sel % 2 === 0 && sel + 1 < items.length) sel++
        else if (b === "a") items[sel].run()
        else if (b === "b" || b === "start") resume()
        return true
    }

    visible: open
    Rectangle { anchors.fill: parent; color: "#0b0c14" }
    Rectangle {
        x: 36; y: 36; width: parent.width - 72; height: parent.height - 72; radius: 44
        color: "#ebedf2"; border.color: "white"; border.width: 2

        Text {
            x: 44; y: 34; text: "Paused"
            font.family: Theme.font; font.pixelSize: 44; font.weight: Font.Black; color: "#2a2b3d"
        }
        Text {
            anchors.right: parent.right; anchors.rightMargin: 44; y: 46
            text: "B  resume"; font.family: Theme.font; font.pixelSize: 28; font.weight: Font.Bold; color: "#6f7186"
        }
        // two columns of big touch targets
        Grid {
            x: 32; y: 120; columns: 2; columnSpacing: 20; rowSpacing: 18
            Repeater {
                model: menu.items
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
                        onClicked: { backend.sound("select"); menu.sel = index; modelData.run() }
                    }
                }
            }
        }
    }
}
