import QtQuick

// Little shoulder-button label ("LT", "RB") that sits on a pill's rim.
Rectangle {
    property alias text: label.text
    width: label.implicitWidth + 22; height: 42; radius: 10
    color: Theme.tagBg
    border.color: "#9a9ab5"; border.width: 2
    Text {
        id: label; anchors.centerIn: parent
        font.family: Theme.font; font.pixelSize: 24; font.weight: Font.Black; color: Theme.tagText
    }
}
