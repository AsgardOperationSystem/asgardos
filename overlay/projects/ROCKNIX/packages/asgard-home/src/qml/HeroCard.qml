import QtQuick
import QtQuick.Effects

// The big glass card on the top screen: bevelled light rim, lavender glass with a holographic grid and a slow
// sheen, the selection's art inside. Content crossfades + settles in when the selection changes.
Item {
    id: hero
    property var item
    readonly property var game: item ? item.game : null

    onItemChanged: settle.restart()
    SequentialAnimation {
        id: settle
        PropertyAction { target: content; property: "scale"; value: 0.965 }
        PropertyAction { target: content; property: "opacity"; value: 0.35 }
        ParallelAnimation {
            NumberAnimation { target: content; property: "scale"; to: 1; duration: 260; easing.type: Easing.OutCubic }
            NumberAnimation { target: content; property: "opacity"; to: 1; duration: 200 }
        }
    }

    MultiEffect {  // soft drop shadow
        source: glass; anchors.fill: glass
        shadowEnabled: true; shadowColor: "#000000"; shadowOpacity: 0.55; shadowBlur: 1.0; shadowVerticalOffset: 14
    }
    Rectangle {  // the rim: bright top-left, dimmer bottom-right
        id: glass
        anchors.fill: parent; radius: 84
        gradient: Gradient {
            GradientStop { position: 0; color: "#f2ffffff" }
            GradientStop { position: 1; color: "#8fb9b4ff" }
        }
    }
    Rounded {
        id: face
        anchors.fill: parent; anchors.margins: 9; radius: 76
        Rectangle {
            anchors.fill: parent
            gradient: Gradient {
                GradientStop { position: 0; color: "#c8ffffff" }
                GradientStop { position: 0.55; color: "#a7d9d6ff" }
                GradientStop { position: 1; color: "#b79d93ff" }
            }
        }

        Item {
            id: content
            anchors.fill: parent
            // system: big name + count; game / jump: screenshot, cover, title, details
            Image {
                anchors.fill: parent; fillMode: Image.PreserveAspectCrop; asynchronous: true
                sourceSize: Qt.size(1150, 650)
                opacity: hero.game ? 0.9 : 0.22
                source: hero.game ? (hero.game.shot || hero.game.cover) : (hero.item && hero.item.sys ? hero.item.sys.cover || "" : "")
            }
            Rectangle {  // readable lower third over game art
                visible: hero.game !== null
                anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom
                height: parent.height * 0.55
                gradient: Gradient {
                    GradientStop { position: 0; color: "#00101020" }
                    GradientStop { position: 1; color: "#d8101020" }
                }
            }
            Rectangle {
                visible: hero.game !== null
                x: 56; anchors.bottom: parent.bottom; anchors.bottomMargin: 50
                width: 250; height: 320; radius: 22; color: "#ffffff"
                Image {
                    anchors.fill: parent; anchors.margins: 8; fillMode: Image.PreserveAspectCrop; asynchronous: true
                    sourceSize: Qt.size(250, 320)
                    source: hero.game ? (hero.game.cover || "") : ""
                }
            }
            Column {
                visible: hero.game !== null
                x: 340; anchors.bottom: parent.bottom; anchors.bottomMargin: 56; spacing: 6
                width: parent.width - x - 60
                Text {
                    width: parent.width; elide: Text.ElideRight
                    font.family: Theme.font; font.pixelSize: 60; font.weight: Font.Black; color: Theme.text
                    text: hero.game ? hero.game.name : ""
                }
                Text {
                    width: parent.width; elide: Text.ElideRight
                    font.family: Theme.font; font.pixelSize: 32; font.weight: Font.Bold; color: Theme.textDim
                    text: hero.game ? [hero.game.sysName, hero.game.developer, hero.game.year].filter(s => s).join("  ·  ") : ""
                }
            }
            Column {
                visible: hero.item && hero.item.kind === "system"
                anchors.centerIn: parent; spacing: 4
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    font.family: Theme.font; font.pixelSize: 132; font.weight: Font.Black; font.letterSpacing: 6
                    color: hero.item && hero.item.sys ? Theme.ink(hero.item.sys.name) : "transparent"
                    text: hero.item && hero.item.sys ? hero.item.sys.name.toUpperCase() : ""
                }
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    font.family: Theme.font; font.pixelSize: 44; font.weight: Font.ExtraBold; color: "#3b3a66"
                    text: hero.item && hero.item.sys ? hero.item.sys.fullname : ""
                }
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    font.family: Theme.font; font.pixelSize: 32; font.weight: Font.Bold; color: "#5b5a88"
                    text: hero.item && hero.item.sys ? hero.item.sys.count + " games" : ""
                }
            }
        }

        // holographic grid
        Canvas {
            anchors.fill: parent; opacity: hero.game ? 0.09 : 0.22
            Behavior on opacity { NumberAnimation { duration: Theme.fade } }
            onPaint: {
                const c = getContext("2d"); c.strokeStyle = "#ffffff"; c.lineWidth = 1.5
                for (let x = 0; x < width; x += 34) { c.beginPath(); c.moveTo(x, 0); c.lineTo(x, height); c.stroke() }
                for (let y = 0; y < height; y += 34) { c.beginPath(); c.moveTo(0, y); c.lineTo(width, y); c.stroke() }
            }
        }
        // slow diagonal sheen
        Rectangle {
            width: parent.width * 0.35; height: parent.height * 3; y: -parent.height; rotation: 22
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0; color: "#00ffffff" }
                GradientStop { position: 0.5; color: "#2effffff" }
                GradientStop { position: 1; color: "#00ffffff" }
            }
            NumberAnimation on x { from: -face.width * 0.6; to: face.width * 1.3; duration: 6500; loops: Animation.Infinite }
        }
        // inner bevel highlight
        Rectangle {
            anchors.fill: parent; radius: face.radius; color: "transparent"
            border.color: "#80ffffff"; border.width: 3
        }
    }
}
