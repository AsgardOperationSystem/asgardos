import QtQuick
import QtQuick.Effects

// The big glass card on the top screen: bevelled light rim, lavender glass with a holographic grid and a slow
// sheen, the selection's art inside. Content crossfades + settles in when the selection changes.
Item {
    id: hero
    property var item
    property string placeholder                                      // shown when nothing is selected (tab name)
    readonly property var game: item ? item.game : null
    readonly property var ra: item && item.ra ? item.ra : null       // trophy game / achievement
    readonly property var ach: item && item.ach ? item.ach : null    // one achievement

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
            Rectangle {  // the cover, or an achievement's badge
                visible: hero.game !== null
                x: 56; anchors.bottom: parent.bottom; anchors.bottomMargin: 50
                width: hero.ach ? 280 : 250; height: hero.ach ? 280 : 320; radius: 22
                color: hero.ach && hero.ach.earned ? Theme.goldA : "#ffffff"
                Image {
                    anchors.fill: parent; anchors.margins: 8; fillMode: Image.PreserveAspectCrop; asynchronous: true
                    sourceSize: Qt.size(280, 320)
                    source: hero.ach ? (hero.ach.earned ? hero.ach.badge : hero.ach.badgeLocked)
                                     : hero.game ? (hero.game.cover || (hero.ra ? hero.ra.icon : "")) : ""
                }
            }
            Column {
                visible: hero.game !== null
                x: 340; anchors.bottom: parent.bottom; anchors.bottomMargin: 56; spacing: 6
                width: parent.width - x - 60
                Text {
                    width: parent.width; elide: Text.ElideRight
                    font.family: Theme.font; font.pixelSize: 60; font.weight: Font.Black; color: Theme.text
                    text: hero.ach ? hero.ach.title : hero.ra ? hero.ra.title : hero.game ? hero.game.name : ""
                }
                Text {
                    width: parent.width; elide: Text.ElideRight; wrapMode: Text.WordWrap; maximumLineCount: 2
                    font.family: Theme.font; font.pixelSize: 32; font.weight: Font.Bold; color: Theme.textDim
                    text: hero.ach ? hero.ach.description
                        : hero.ra ? hero.ra.earned + " / " + hero.ra.total + " achievements  ·  " + hero.ra.points + " points"
                        : hero.game ? [hero.game.sysName, hero.game.developer, hero.game.year].filter(s => s).join("  ·  ") : ""
                }
                Text {  // achievement: points and when it was unlocked
                    visible: !!hero.ach
                    font.family: Theme.font; font.pixelSize: 32; font.weight: Font.Black
                    color: hero.ach && hero.ach.earned ? Theme.goldA : Theme.textDim
                    text: hero.ach ? hero.ach.points + " points  ·  " + (hero.ach.earned
                          ? "Unlocked " + hero.ach.date + (hero.ach.hardcore ? "  ·  Hardcore" : "") : "Locked") : ""
                }
                Rectangle {  // trophy game: progress bar
                    visible: !!hero.ra && !hero.ach
                    width: parent.width; height: 18; radius: 9; color: "#44ffffff"
                    Rectangle {
                        height: parent.height; radius: 9
                        width: hero.ra && hero.ra.total ? parent.width * hero.ra.earned / hero.ra.total : 0
                        gradient: Gradient {
                            orientation: Gradient.Horizontal
                            GradientStop { position: 0; color: Theme.goldA }
                            GradientStop { position: 1; color: Theme.goldB }
                        }
                    }
                }
            }
            Text {
                visible: !hero.item
                anchors.centerIn: parent
                font.family: Theme.font; font.pixelSize: 132; font.weight: Font.Black; font.letterSpacing: 6
                color: "#7d74d6"; text: hero.placeholder.toUpperCase()
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
