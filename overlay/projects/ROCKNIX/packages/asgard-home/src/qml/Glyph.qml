import QtQuick

// Face-button glyph: a white ring with the button's letter or sign.
Rectangle {
    property alias text: label.text
    property string icon: ""        // icons/<icon>.svg instead of a letter (Home)
    property int size: 44
    width: size; height: size; radius: size / 2
    color: "transparent"; border.color: Theme.text; border.width: 3
    Text {
        id: label; anchors.centerIn: parent; anchors.verticalCenterOffset: -1
        font.family: Theme.font; font.pixelSize: parent.size * 0.62; font.weight: Font.Black; color: Theme.text
    }
    Image {
        visible: parent.icon !== ""; anchors.centerIn: parent; width: parent.size * 0.56; height: width
        source: parent.icon ? "icons/" + parent.icon + ".svg" : ""; sourceSize: Qt.size(width * 2, height * 2)
    }
}
