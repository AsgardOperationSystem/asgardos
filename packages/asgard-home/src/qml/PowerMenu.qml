import QtQuick

// Small menu card: the power button's (sleep, restart, power off) by default, or any items (the game menu on
// Select). Touch or d-pad + A, B closes. An item with keep: true leaves the card open; status shows under the items.
Item {
    id: menu
    property bool open: false
    property int sel: 0
    property real anchorRight: 0          // x of the button's right edge, so the card hangs under it
    property string status: ""
    property var items: [
        { icon: "moon", title: "Sleep", run: () => backend.shell("python3 /usr/share/asgard/asgard-transfers.py sleep") },   // XFER-3
        { icon: "refresh", title: "Restart", run: () => backend.shell("systemctl reboot") },
        { icon: "power", title: "Power off", run: () => backend.shell("systemctl poweroff") }
    ]

    function show() { sel = 0; open = true }
    function pick(i) { if (!items[i].keep) open = false; items[i].run() }
    function nav(b) {
        if (!open) return false
        if (b === "up") sel = (sel + items.length - 1) % items.length
        else if (b === "down") sel = (sel + 1) % items.length
        else if (b === "a") pick(sel)
        else if (b === "b" || b === "start") open = false
        return true
    }

    visible: open
    Rectangle { anchors.fill: parent; color: "#80000000"; MouseArea { anchors.fill: parent; onClicked: menu.open = false } }

    Rectangle {
        id: card
        x: menu.anchorRight - width; y: 190; width: 470; height: col.height + 36; radius: 40
        color: "#ebedf2"; border.color: "white"; border.width: 2
        MouseArea { anchors.fill: parent }   // taps on the card don't close it
        Column {
            id: col
            x: 18; y: 18; width: parent.width - 36; spacing: 6
            Repeater {
                model: menu.items
                Rectangle {
                    readonly property bool on: index === menu.sel
                    width: col.width; height: 110; radius: 28
                    color: on ? "#e6ecff" : "transparent"
                    border.color: on ? Theme.selA : "transparent"; border.width: 3
                    Image {
                        x: 30; anchors.verticalCenter: parent.verticalCenter; width: 48; height: 48
                        source: "icons/settings/" + modelData.icon + ".svg"; sourceSize: Qt.size(96, 96)
                    }
                    Text {
                        x: 104; anchors.verticalCenter: parent.verticalCenter; text: modelData.title
                        font.family: Theme.font; font.pixelSize: 36; font.weight: Font.Black
                        color: modelData.icon === "power" ? "#c2334d" : "#2a2b3d"
                    }
                    MouseArea {
                        anchors.fill: parent
                        onClicked: { backend.sound("select"); menu.sel = index; menu.pick(index) }
                    }
                }
            }
            Text {
                visible: menu.status !== ""; width: col.width; leftPadding: 30; rightPadding: 30; topPadding: 6; bottomPadding: 6
                text: menu.status; wrapMode: Text.Wrap
                font.family: Theme.font; font.pixelSize: 28; font.weight: Font.Bold; color: "#4a4b5d"
            }
        }
    }
}
