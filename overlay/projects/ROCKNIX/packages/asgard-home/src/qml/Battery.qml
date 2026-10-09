import QtQuick

// Battery outline with a fill bar; green, amber under 30 %, red under 15 %, bolt while charging.
Item {
    property int level: 100
    property bool charging: false
    width: 62; height: 32
    Rectangle {
        id: body; width: 56; height: 32; radius: 7
        color: "transparent"; border.color: Theme.text; border.width: 3
        Rectangle {
            x: 5; y: 5; height: parent.height - 10; radius: 3
            width: Math.max(4, (parent.width - 10) * Math.min(100, level) / 100)
            color: level < 15 ? "#ff5a5a" : level < 30 ? "#ffb347" : "#5be37d"
        }
    }
    Rectangle { x: 56; y: 10; width: 6; height: 12; radius: 2; color: Theme.text }
    Text {
        visible: charging; anchors.centerIn: body
        font.family: Theme.font; font.pixelSize: 26; font.weight: Font.Black; color: "#ffd84d"; style: Text.Outline
        styleColor: "#1b1b28"; text: "⚡"
    }
}
