import QtQuick

// Confirm dialog: open(title, text, yes, run) shows Cancel / yes; run() only on yes. D-pad + A/B or touch.
// more (optional): {no: a label for Cancel, other: a middle button's label, otherRun: what it does}.
Item {
    id: dlg
    property var ask: null                   // {title, text, yes, run, no, other, otherRun}
    property int sel: 1                      // 0 = Cancel, the last = the action
    readonly property var buttons: ask ? [ask.no || "Cancel", ...(ask.other ? [ask.other] : []), ask.yes] : []
    readonly property color ink: "#2a2b3d"
    readonly property color inkDim: "#6f7186"
    visible: !!ask

    function open(title, text, yes, run, more) {
        ask = Object.assign({ title: title, text: text, yes: yes, run: run }, more || {}); sel = buttons.length - 1
    }
    function pick(i) {
        const a = ask, last = buttons.length - 1
        ask = null
        if (i === last) a.run()
        else if (i > 0 && a.otherRun) a.otherRun()
    }
    // Returns true if the button was used.
    function nav(b) {
        if (!ask) return false
        if (b === "left") sel = (sel + buttons.length - 1) % buttons.length
        else if (b === "right") sel = (sel + 1) % buttons.length
        else if (b === "b") ask = null
        else if (b === "a") pick(sel)
        return true
    }

    Rectangle { anchors.fill: parent; color: "#99000000"; MouseArea { anchors.fill: parent; onClicked: dlg.ask = null } }
    Rectangle {
        anchors.centerIn: parent; width: dlg.buttons.length > 2 ? 1000 : 760; height: 380; radius: 44; color: "#ebedf2"; border.color: "white"; border.width: 2
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
                model: dlg.buttons
                Rectangle {
                    readonly property bool sel: dlg.sel === index
                    width: Math.max(dlg.buttons.length > 2 ? 210 : 250, label.implicitWidth + 64); height: 92; radius: 46
                    color: sel ? Theme.selB : "#d6d8e0"; border.color: sel ? Theme.selA : "transparent"; border.width: 3
                    Text { id: label; anchors.centerIn: parent; text: modelData; color: parent.sel ? "white" : dlg.ink
                           font.family: Theme.font; font.pixelSize: 32; font.weight: Font.Black }
                    MouseArea { anchors.fill: parent; onClicked: dlg.pick(index) }
                }
            }
        }
    }
}
