import QtQuick
import QtQuick.Effects

// One cell of the bottom grid. kind: "game" (cover + system badge), "system" (pastel card), "jump" (2-wide
// "Return to game", the game in the background), "ra" (trophy game: cover + progress), "ach" (one achievement's badge).
// The selected tile grows a little and gets the cyan-violet rim + glow; a mastered set has a gold rim.
Item {
    id: tile
    property var item
    property bool selected: false
    property bool lifted: false   // being moved (reorder): bigger, and it wobbles
    property bool near: true      // inside or close to the visible part of the grid: only then load art and effects
    signal tapped()               // touchscreen
    signal longPressed()          // touchscreen: lift the tile to reorder it

    // A handler, not a MouseArea: a MouseArea takes the touch on press, so a swipe that starts on a tile never
    // reached the grid's DragHandler (no scrolling). TapHandler lets a drag past the threshold go to it.
    TapHandler { onTapped: tile.tapped(); onLongPressed: tile.longPressed() }
    readonly property string kind: item ? item.kind : ""
    readonly property var game: item ? item.game : null
    readonly property bool badged: kind === "game" || kind === "ra"   // gets the little system badge
    readonly property bool mastered: kind === "ra" && item.ra.total > 0 && item.ra.earned >= item.ra.total

    z: selected ? 2 : 1
    scale: lifted ? 1.14 : selected ? 1.07 : 1.0
    rotation: 0
    SequentialAnimation on rotation {
        running: tile.lifted; loops: Animation.Infinite
        onRunningChanged: if (!running) tile.rotation = 0
        NumberAnimation { to: 2; duration: 120 }
        NumberAnimation { to: -2; duration: 240 }
        NumberAnimation { to: 0; duration: 120 }
    }
    Behavior on scale { NumberAnimation { duration: Theme.anim; easing.type: Easing.OutBack; easing.overshoot: 2.2 } }

    // Glow under the selected tile (only that one carries the effect).
    Loader {
        active: tile.selected
        anchors.fill: rim
        sourceComponent: MultiEffect {
            source: rim
            shadowEnabled: true; shadowColor: Theme.selA; shadowBlur: 1.0; shadowScale: 1.04
            opacity: 0.9
        }
    }
    Rectangle {
        id: rim
        anchors.fill: parent; radius: 30
        gradient: Gradient {
            orientation: Gradient.Horizontal
            GradientStop { position: 0; color: tile.selected ? Theme.selA : tile.mastered ? Theme.goldA : Theme.tileRim }
            GradientStop { position: 1; color: tile.selected ? Theme.selB : tile.mastered ? Theme.goldB : Theme.tileRim }
        }
    }
    Rounded {
        id: face
        visible: tile.near                       // far tiles: just the rim, no art, no mask layer
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

        // game / trophy game: the cover, filling the face
        Image {
            visible: tile.kind === "game" || tile.kind === "ra"
            anchors.fill: parent; fillMode: Image.PreserveAspectCrop; asynchronous: true; smooth: true
            sourceSize: Qt.size(320, 320)
            source: !tile.near ? "" : visible ? (tile.game.cover || tile.game.shot || (tile.kind === "ra" ? tile.item.ra.icon : "")) : ""
        }
        // trophy game: progress bar + "earned / total" along the bottom
        Rectangle {
            visible: tile.kind === "ra"
            anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom; height: 62
            color: "#cc12131f"
            Rectangle {
                x: 14; anchors.verticalCenter: parent.verticalCenter; width: parent.width - 120; height: 12; radius: 6
                color: "#44ffffff"
                Rectangle {
                    height: parent.height; radius: 6
                    width: tile.kind === "ra" && tile.item.ra.total ? parent.width * tile.item.ra.earned / tile.item.ra.total : 0
                    gradient: Gradient {
                        orientation: Gradient.Horizontal
                        GradientStop { position: 0; color: tile.mastered ? Theme.goldA : Theme.selA }
                        GradientStop { position: 1; color: tile.mastered ? Theme.goldB : Theme.selB }
                    }
                }
            }
            Text {
                anchors.right: parent.right; anchors.rightMargin: 14; anchors.verticalCenter: parent.verticalCenter
                font.family: Theme.font; font.pixelSize: 24; font.weight: Font.Black; color: Theme.text
                text: tile.kind === "ra" ? tile.item.ra.earned + "/" + tile.item.ra.total : ""
            }
        }
        // achievement: its badge, greyed while locked, points in the corner
        Image {
            visible: tile.kind === "ach"
            anchors.fill: parent; anchors.margins: 14; fillMode: Image.PreserveAspectFit; asynchronous: true; smooth: true
            sourceSize: Qt.size(128, 128)
            source: !tile.near ? "" : visible ? (tile.item.ach.earned ? tile.item.ach.badge : tile.item.ach.badgeLocked) : ""
            opacity: tile.kind === "ach" && !tile.item.ach.earned ? 0.55 : 1
        }
        Pill {
            visible: tile.kind === "ach"
            anchors.right: parent.right; anchors.bottom: parent.bottom; anchors.margins: 10
            width: pts.implicitWidth + 26; height: 42; border.width: 2
            Text {
                id: pts; anchors.centerIn: parent
                font.family: Theme.font; font.pixelSize: 22; font.weight: Font.Black
                color: tile.kind === "ach" && tile.item.ach.earned ? Theme.goldA : Theme.textDim
                text: tile.kind === "ach" ? tile.item.ach.points : ""
            }
        }
        // system: Art Book Next artwork with the white logo over a dark fade; the name in its ink colour if no art
        readonly property bool sysArt: tile.kind === "system" && !!tile.item.sys.art
        Image {
            visible: tile.kind === "system"
            anchors.fill: parent; fillMode: Image.PreserveAspectCrop; asynchronous: true
            opacity: face.sysArt ? 1 : 0.16
            sourceSize: Qt.size(320, 0)
            source: !tile.near ? "" : tile.kind === "system" ? (tile.item.sys.art || tile.item.sys.cover || "") : ""
        }
        Rectangle {
            visible: face.sysArt
            anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom; height: parent.height * 0.55
            gradient: Gradient {
                GradientStop { position: 0; color: "#00101020" }
                GradientStop { position: 1; color: "#e0101020" }
            }
        }
        Image {
            visible: face.sysArt && !!tile.item.sys.logo
            anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom
            anchors.margins: 22; height: parent.height * 0.3
            fillMode: Image.PreserveAspectFit; asynchronous: true; smooth: true
            sourceSize: Qt.size(400, 0)
            source: !tile.near ? "" : (visible ? tile.item.sys.logo : "")
        }
        Text {
            visible: tile.kind === "system" && !(face.sysArt && tile.item.sys.logo)
            anchors.fill: parent; anchors.margins: 18
            horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
            wrapMode: Text.WordWrap; fontSizeMode: Text.Fit; minimumPixelSize: 26; font.pixelSize: 58
            font.family: Theme.font; font.weight: Font.Black
            color: tile.kind === "system" ? Theme.ink(tile.item.sys.name) : "transparent"
            text: tile.kind === "system" ? tile.item.sys.name.toUpperCase() : ""
        }
        // jump: the background game's screenshot, darkened, its cover on the left, "(A) Return to game" pill
        Image {
            visible: tile.kind === "jump"
            anchors.fill: parent; fillMode: Image.PreserveAspectCrop; asynchronous: true
            sourceSize: Qt.size(600, 340)
            source: !tile.near ? "" : tile.kind === "jump" ? (tile.game.shot || tile.game.cover) : ""
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
                source: !tile.near ? "" : tile.kind === "jump" ? (tile.game.cover || tile.game.shot) : ""
            }
        }
        Pill {
            visible: tile.kind === "jump"
            anchors.right: parent.right; anchors.bottom: parent.bottom; anchors.margins: 18
            width: jumpHint.implicitWidth + 36; height: 62; border.width: 2
            Hint { id: jumpHint; anchors.centerIn: parent; glyph: "A"; label: "Return to game"; size: 36 }
        }
    }
    // system badge on game tiles (top-left), like iiSU's console badge
    Rectangle {
        visible: tile.badged && tile.near
        x: 16; y: 16; width: 40; height: 40; radius: 11
        color: tile.badged ? Theme.pastel(tile.game.sys) : "transparent"
        border.color: "#ffffff"; border.width: 2
        Text {
            anchors.centerIn: parent
            font.family: Theme.font; font.pixelSize: 15; font.weight: Font.Black
            color: tile.badged ? Theme.ink(tile.game.sys) : "transparent"
            text: tile.badged ? tile.game.sys.slice(0, 3).toUpperCase() : ""
        }
    }
}
