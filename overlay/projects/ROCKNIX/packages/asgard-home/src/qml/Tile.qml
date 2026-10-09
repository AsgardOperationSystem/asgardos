import QtQuick
import QtQuick.Effects

// One cell of the bottom grid. kind: "game" (cover + system badge), "system" (pastel card), "jump" (2-wide
// "Jump back in!" with the last game). The selected tile grows a little and gets the cyan-violet rim + glow.
Item {
    id: tile
    property var item
    property bool selected: false
    readonly property string kind: item ? item.kind : ""
    readonly property var game: item ? item.game : null

    z: selected ? 2 : 1
    scale: selected ? 1.07 : 1.0
    Behavior on scale { NumberAnimation { duration: Theme.anim; easing.type: Easing.OutBack; easing.overshoot: 2.2 } }

    // Glow under the selected tile.
    MultiEffect {
        source: rim; anchors.fill: rim
        shadowEnabled: true; shadowColor: Theme.selA; shadowBlur: 1.0; shadowScale: 1.04
        opacity: tile.selected ? 0.9 : 0
        Behavior on opacity { NumberAnimation { duration: Theme.anim } }
    }
    Rectangle {
        id: rim
        anchors.fill: parent; radius: 30
        gradient: Gradient {
            orientation: Gradient.Horizontal
            GradientStop { position: 0; color: tile.selected ? Theme.selA : Theme.tileRim }
            GradientStop { position: 1; color: tile.selected ? Theme.selB : Theme.tileRim }
        }
    }
    Rounded {
        id: face
        anchors.fill: parent; anchors.margins: tile.selected ? 7 : 5
        radius: 25
        Rectangle { anchors.fill: parent; color: tile.kind === "system" ? Theme.pastel(tile.item.sys.name) : "#2b2c40" }
        Text {  // game without art: its name
            visible: tile.kind === "game" && !(tile.game.cover || tile.game.shot)
            anchors.fill: parent; anchors.margins: 20; anchors.topMargin: 50
            horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
            wrapMode: Text.WordWrap; fontSizeMode: Text.Fit; minimumPixelSize: 20; font.pixelSize: 36
            font.family: Theme.font; font.weight: Font.Black; color: Theme.text
            text: tile.kind === "game" ? tile.game.name : ""
        }

        // game: the cover, filling the face
        Image {
            visible: tile.kind === "game"
            anchors.fill: parent; fillMode: Image.PreserveAspectCrop; asynchronous: true; smooth: true
            sourceSize: Qt.size(320, 320)
            source: tile.kind === "game" ? (tile.game.cover || tile.game.shot) : ""
        }
        // system: faint screenshot watermark + the system's name in its ink colour
        Image {
            visible: tile.kind === "system"
            anchors.fill: parent; fillMode: Image.PreserveAspectCrop; asynchronous: true; opacity: 0.16
            sourceSize: Qt.size(320, 320)
            source: tile.kind === "system" ? (tile.item.sys.cover || "") : ""
        }
        Text {
            visible: tile.kind === "system"
            anchors.fill: parent; anchors.margins: 18
            horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
            wrapMode: Text.WordWrap; fontSizeMode: Text.Fit; minimumPixelSize: 26; font.pixelSize: 58
            font.family: Theme.font; font.weight: Font.Black
            color: tile.kind === "system" ? Theme.ink(tile.item.sys.name) : "transparent"
            text: tile.kind === "system" ? tile.item.sys.name.toUpperCase() : ""
        }
        // jump: last game's screenshot, darkened, its cover on the left, "(A) Jump back in!" pill
        Image {
            visible: tile.kind === "jump"
            anchors.fill: parent; fillMode: Image.PreserveAspectCrop; asynchronous: true
            sourceSize: Qt.size(600, 340)
            source: tile.kind === "jump" ? (tile.game.shot || tile.game.cover) : ""
        }
        Rectangle { visible: tile.kind === "jump"; anchors.fill: parent; color: "#66000000" }
        Rectangle {
            visible: tile.kind === "jump"
            x: 24; anchors.verticalCenter: parent.verticalCenter
            width: parent.height * 0.62; height: parent.height * 0.72; radius: 14
            color: "#ffffff"
            Image {
                anchors.fill: parent; anchors.margins: 6; fillMode: Image.PreserveAspectCrop; asynchronous: true
                sourceSize: Qt.size(200, 240)
                source: tile.kind === "jump" ? (tile.game.cover || tile.game.shot) : ""
            }
        }
        Pill {
            visible: tile.kind === "jump"
            anchors.right: parent.right; anchors.bottom: parent.bottom; anchors.margins: 18
            width: jumpHint.implicitWidth + 36; height: 62; border.width: 2
            Hint { id: jumpHint; anchors.centerIn: parent; glyph: "A"; label: "Jump back in!"; size: 36 }
        }
    }
    // system badge on game tiles (top-left), like iiSU's console badge
    Rectangle {
        visible: tile.kind === "game"
        x: 16; y: 16; width: 40; height: 40; radius: 11
        color: tile.kind === "game" ? Theme.pastel(tile.game.sys) : "transparent"
        border.color: "#ffffff"; border.width: 2
        Text {
            anchors.centerIn: parent
            font.family: Theme.font; font.pixelSize: 15; font.weight: Font.Black
            color: tile.kind === "game" ? Theme.ink(tile.game.sys) : "transparent"
            text: tile.kind === "game" ? tile.game.sys.slice(0, 3).toUpperCase() : ""
        }
    }
}
