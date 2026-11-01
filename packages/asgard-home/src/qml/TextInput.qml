import QtQuick
import QtQuick.Window

// A game's text prompt on the bottom screen (asgard-text-input, started by thor_text_input.py for Eden Duo's software
// keyboard): Home's keyboard alone in a window, the pad grabbed. Done: the text goes to stdout, exit 0 (main.cpp).
// Backing out: exit 1.
Window {
    id: root
    title: "Asgard Text Input (Bottom)"   // "Bottom": ROCKNIX's sway rules; # thor-text-input in thor-sway-rotate.sh
    width: 1240; height: 1080; color: "#0b0c14"; visible: !shotMode

    property string result: ""
    property bool submitted: false

    Component.onCompleted: {
        if (textInput.accent) Theme.accent = textInput.accent
        keyboard.ask(textInput.title || "Enter text", textInput.initial, textInput.secret, v => {
            root.result = v
            root.submitted = true
            Qt.exit(0)
        })
        if (textInput.digits) keyboard.kr = 0     // the keys it takes
    }
    Connections {
        target: pad
        function onPressed(b) { keyboard.nav(b) }
    }
    Keyboard {
        id: keyboard
        anchors.fill: parent
        maxLength: textInput.maxLength
        minLength: textInput.minLength
        allowed: textInput.digits ? "0123456789" : ""
        canCancel: !textInput.noCancel
        bottomGap: 155                            // alone on the screen: centred
        onOpenChanged: if (!open) Qt.callLater(() => { if (!root.submitted) Qt.exit(1) })
    }
}
