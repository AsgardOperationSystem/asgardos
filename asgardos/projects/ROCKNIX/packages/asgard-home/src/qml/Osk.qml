import QtQuick
import QtQuick.Window

// Asgard Keyboard (asgard-home --osk <app_id>): the bottom screen's touch keyboard for Tools (Terminal, Firefox).
// `osk` sends the keys (osk.cpp). Shift, Ctrl and Alt hold for the next key; Shift twice locks it. ?123 switches to
// the symbols a shell needs. Touch only: the pad stays the app's.
Window {
    id: kb
    title: "Asgard Keyboard"
    width: 1240; height: 1080; color: "#0b0c14"
    visible: osk.shown && !shotMode

    property int shift: 0                    // 0 off, 1 next key, 2 locked
    property bool ctrl: false
    property bool alt: false
    property bool symbols: false
    readonly property bool upper: shift > 0

    // [label, key, width in units]; key "" = the label itself
    readonly property var topRow: [["Esc", "Esc", 1], ["Tab", "Tab", 1], ["Ctrl", "@ctrl", 1.25], ["Alt", "@alt", 1.25],
                                   ["←", "Left", 1], ["↓", "Down", 1], ["↑", "Up", 1], ["→", "Right", 1]]
    readonly property var letters: ["1234567890", "qwertyuiop", "asdfghjkl", "zxcvbnm"]
    readonly property var syms: ["!@#$%^&*()", "-_=+[]{}\\|", ";:'\"`~<>/", ",.?"]
    function row(i) {
        const keys = (symbols ? syms : letters)[i].split("").map(c => [upper && !symbols ? c.toUpperCase() : c, "", 1])
        if (i === 3) return [["⇧", "@shift", 1.5]].concat(keys).concat([["⌫", "Back", 1.5]])
        return keys
    }
    readonly property var bottomRow: [[symbols ? "abc" : "?123", "@sym", 1.5], ["/", "", 1], ["space", "Space", 4.5],
                                      [".", "", 1], ["Enter", "Enter", 2]]
    readonly property var rows: [topRow, row(0), row(1), row(2), row(3), bottomRow]

    function down(k) {
        if (k[1] === "@shift") shift = shift === 0 ? 1 : shift === 1 ? 2 : 0
        else if (k[1] === "@ctrl") ctrl = !ctrl
        else if (k[1] === "@alt") alt = !alt
        else if (k[1] === "@sym") symbols = !symbols
        else {
            osk.press(k[1] || k[0], shift > 0 && !symbols, ctrl, alt)
            if (shift === 1) shift = 0
            ctrl = false; alt = false
        }
    }
    function lit(k) {
        return k[1] === "@shift" ? shift > 0 : k[1] === "@ctrl" ? ctrl : k[1] === "@alt" ? alt : k[1] === "@sym" ? symbols : false
    }

    Column {
        anchors.fill: parent; anchors.margins: 16; spacing: 12
        Repeater {
            model: kb.rows
            Row {
                id: line
                readonly property var keys: modelData
                readonly property real unit: (kb.width - 32 - 12 * (keys.length - 1)) / keys.reduce((s, k) => s + k[2], 0)
                spacing: 12
                anchors.horizontalCenter: parent.horizontalCenter
                Repeater {
                    model: line.keys
                    Rectangle {
                        id: key
                        readonly property bool special: modelData[1] !== "" && modelData[1] !== "Space"
                        readonly property bool held: area.pressed || kb.lit(modelData)
                        width: line.unit * modelData[2]; height: (kb.height - 32 - 12 * 5) / 6; radius: 26
                        color: held ? "transparent" : special ? "#2a2c40" : Theme.pill
                        border.color: Theme.pillRim; border.width: held ? 0 : 2
                        gradient: held ? sel : null
                        Gradient { id: sel; orientation: Gradient.Horizontal
                            GradientStop { position: 0; color: Theme.selA } GradientStop { position: 1; color: Theme.selB } }
                        Text {
                            anchors.centerIn: parent; text: modelData[0]; color: Theme.text
                            font.family: Theme.font; font.weight: Font.Black
                            font.pixelSize: modelData[0].length > 1 ? 36 : 52
                        }
                        MouseArea {
                            id: area; anchors.fill: parent
                            onPressed: kb.down(modelData)
                            onReleased: osk.release()
                            onCanceled: osk.release()
                        }
                    }
                }
            }
        }
    }
}
