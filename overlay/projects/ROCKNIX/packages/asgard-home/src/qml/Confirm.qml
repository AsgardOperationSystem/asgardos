import QtQuick

// Confirm dialog: open(title, text, yes, run) shows Cancel / yes; run() only on yes. D-pad + A/B or touch.
Item {
    id: dlg
    property var ask: null                   // {title, text, yes, run}
    property int sel: 1                      // 0 = Cancel, 1 = the action
    readonly property color ink: "#2a2b3d"
    readonly property color inkDim: "#6f7186"
    visible: !!ask

    function open(title, text, yes, run) { ask = { title: title, text: text, yes: yes, run: run }; sel = 1 }
    function pick(i) { const a = ask; ask = null; if (i === 1) a.run() }
    // Returns true if the button was used.
    function nav(b) {
        if (!ask) return false
        if (b === "left" || b === "right") sel = 1 - sel
        else if (b === "b") ask = null
        else if (b === "a") pick(sel)
        return true
    }

    Rectangle { anchors.fill: parent; color: "#99000000"; MouseArea { anchors.fill: parent; onClicked: dlg.ask = null } }
    Rectangle {
        anchors.centerIn: parent; width: 760; height: 380; radius: 44; color: "#ebedf2"; border.color: "white"; border.width: 2
        MouseArea { anchors.fill: parent }
        Text {
            x: 48; y: 44; text: dlg.ask ? dlg.ask.title : ""
            font.family: Theme.font; font.pixelSize: 42; font.weight: Font.Black; color: dlg.ink
        }
        Text {
            x: 48; y: 116; width: parent.width - 96; wrapMode: Text.WordWrap; text: dlg.ask ? dlg.ask.text : ""
            font.family: Theme.font; font.pixelSize: 30; font.weight: Font.Bold; color: dlg.inkDim
        }
        Row {
            anchors.right: parent.right; anchors.bottom: parent.bottom; anchors.margins: 40; spacing: 22
            Repeater {
                model: ["Cancel", dlg.ask ? dlg.ask.yes : ""]
                Rectangle {
                    readonly property bool sel: dlg.sel === index
                    width: 250; height: 92; radius: 46
                    color: sel ? Theme.selB : "#d6d8e0"; border.color: sel ? Theme.selA : "transparent"; border.width: 3
                    Text { anchors.centerIn: parent; text: modelData; color: parent.sel ? "white" : dlg.ink
                           font.family: Theme.font; font.pixelSize: 32; font.weight: Font.Black }
                    MouseArea { anchors.fill: parent; onClicked: dlg.pick(index) }
                }
            }
        }
    }
}
