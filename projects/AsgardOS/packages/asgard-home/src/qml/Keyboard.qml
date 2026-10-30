import QtQuick

// On-screen keyboard (Wi-Fi passwords, hostname). D-pad moves, A types, B deletes, Y space, X shift, + done.
// Touch works too. ask(title, text, secret, done) opens it; done(text) runs on Done, nothing on cancel.
Item {
    id: kb
    property bool open: false
    property string title: ""
    property string text: ""
    property bool secret: false
    property bool reveal: false
    property var done: null
    property int mode: 0                      // 0 lower, 1 upper, 2 symbols
    property int kr: 0
    property int kc: 0

    readonly property var layouts: [
        ["1234567890", "qwertyuiop", "asdfghjkl-", "zxcvbnm_.@"],
        ["1234567890", "QWERTYUIOP", "ASDFGHJKL-", "ZXCVBNM_.@"],
        ["1234567890", "!#$%&*()+=", "/\\:;'\"?,<>", "[]{}~^`|_."]]
    // last row: special keys
    readonly property var specials: [["⇧", "shift", 1.5], ["?123", "sym", 1.5], ["space", "space", 4], ["⌫", "del", 1.5], ["Done", "ok", 1.5]]
    readonly property var rows: layouts[mode].map(r => r.split("")).concat([specials])

    function ask(t, value, isSecret, cb) {
        title = t; text = value || ""; secret = !!isSecret; reveal = false; done = cb
        mode = 0; kr = 1; kc = 0; open = true
    }
    function press(k) {
        if (k === "shift") mode = mode === 1 ? 0 : 1
        else if (k === "sym") mode = mode === 2 ? 0 : 2
        else if (k === "space") text += " "
        else if (k === "del") text = text.slice(0, -1)
        else if (k === "ok") { open = false; if (done) done(text) }
        else { text += k; if (mode === 1) mode = 0 }
    }
    function nav(b) {
        if (!open) return false
        const row = rows[kr]
        if (b === "up" || b === "down") {
            const nr = (kr + (b === "up" ? rows.length - 1 : 1)) % rows.length
            // keep roughly the same column when moving between the letter rows and the special row
            kc = nr === rows.length - 1 ? [0, 0, 1, 1, 2, 2, 2, 2, 3, 4][kc]
               : kr === rows.length - 1 ? [0, 2, 5, 7, 9][kc] : kc
            kr = nr
        }
        else if (b === "left") kc = (kc + row.length - 1) % row.length
        else if (b === "right") kc = (kc + 1) % row.length
        else if (b === "a") press(kr === rows.length - 1 ? row[kc][1] : row[kc])
        else if (b === "b") { if (text.length) press("del"); else open = false }
        else if (b === "y") press("space")
        else if (b === "x") press("shift")
        else if (b === "start") press("ok")
        else if (b === "select") reveal = !reveal
        return true
    }

    visible: open
    Rectangle { anchors.fill: parent; color: "#99000000"; MouseArea { anchors.fill: parent } }

    Rectangle {
        anchors.horizontalCenter: parent.horizontalCenter; anchors.bottom: parent.bottom; anchors.bottomMargin: 36
        width: parent.width - 72; height: 770; radius: 44; color: "#ebedf2"; border.color: "white"; border.width: 2

        Text {
            x: 40; y: 28; text: kb.title
            font.family: Theme.font; font.pixelSize: 36; font.weight: Font.Black; color: "#2a2b3d"
        }
        Rectangle {  // the field
            x: 32; y: 88; width: parent.width - 64; height: 92; radius: 24; color: "white"
            border.color: Theme.selA; border.width: 3
            Text {
                x: 28; anchors.verticalCenter: parent.verticalCenter; width: parent.width - 200; elide: Text.ElideLeft
                text: (kb.secret && !kb.reveal ? "•".repeat(kb.text.length) : kb.text) + "▏"
                font.family: Theme.font; font.pixelSize: 38; font.weight: Font.ExtraBold; color: "#2a2b3d"
            }
            Text {
                visible: kb.secret; anchors.right: parent.right; anchors.rightMargin: 28; anchors.verticalCenter: parent.verticalCenter
                text: kb.reveal ? "Hide (−)" : "Show (−)"; color: "#6f7186"
                font.family: Theme.font; font.pixelSize: 24; font.weight: Font.Bold
                MouseArea { anchors.fill: parent; anchors.margins: -16; onClicked: kb.reveal = !kb.reveal }
            }
        }
        Column {
            anchors.horizontalCenter: parent.horizontalCenter; y: 206; spacing: 10
            Repeater {
                model: kb.rows
                Row {
                    id: keyRow
                    readonly property int r: index
                    readonly property bool special: index === kb.rows.length - 1
                    spacing: 10
                    Repeater {
                        model: modelData
                        Rectangle {
                            readonly property bool sel: kb.kr === keyRow.r && kb.kc === index
                            readonly property string key: keyRow.special ? modelData[1] : modelData
                            readonly property bool active: (key === "shift" && kb.mode === 1) || (key === "sym" && kb.mode === 2)
                            width: keyRow.special ? modelData[2] * 106 - 10 : 106 - 10
                            height: 86; radius: 20
                            color: sel ? Theme.selB : active ? "#cfd2dc" : key === "ok" ? "#2a2b3d" : "white"
                            border.color: sel ? Theme.selA : "#d6d8e0"; border.width: sel ? 4 : 2
                            Text {
                                anchors.centerIn: parent; text: keyRow.special ? modelData[0] : modelData
                                font.family: Theme.font; font.pixelSize: keyRow.special ? 30 : 38; font.weight: Font.Black
                                color: parent.sel || parent.key === "ok" ? "white" : "#2a2b3d"
                            }
                            MouseArea {
                                anchors.fill: parent
                                onClicked: { kb.kr = keyRow.r; kb.kc = index; kb.press(parent.key) }
                            }
                        }
                    }
                }
            }
        }
        Text {
            anchors.horizontalCenter: parent.horizontalCenter; anchors.bottom: parent.bottom; anchors.bottomMargin: 22
            text: "A type   ·   B delete   ·   Y space   ·   X shift   ·   + done"
            font.family: Theme.font; font.pixelSize: 24; font.weight: Font.Bold; color: "#6f7186"
        }
    }
}
