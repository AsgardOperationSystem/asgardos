import QtQuick
import QtQuick.Window

// Volume/brightness slider over everything, games included: a layer-shell overlay surface (set up in main.cpp by
// objectName), on the top panel, never focused or touched. asgard-osd (input_sense) sends "osd Volume 60".
Window {
    id: osd
    objectName: "osd"
    width: 640; height: 150
    color: "transparent"
    flags: Qt.FramelessWindowHint | Qt.WindowDoesNotAcceptFocus | Qt.WindowTransparentForInput
    screen: Qt.application.screens.find(s => s.name === "DSI-2") || Qt.application.screens[0]
    title: "Asgard OSD"

    property string what: "Volume"
    property int value: 0
    property bool shown: false

    Connections {
        target: backend
        function onOsd(w, v) {
            osd.what = w; osd.value = Math.max(0, Math.min(100, v))
            osd.visible = true; osd.shown = true
            hide.restart()
        }
    }
    Timer { id: hide; interval: 1400; onTriggered: osd.shown = false }

    Rectangle {
        id: pill
        width: 560; height: 108; radius: height / 2
        anchors.horizontalCenter: parent.horizontalCenter
        y: osd.shown ? 22 : -height
        opacity: osd.shown ? 1 : 0
        Behavior on y { NumberAnimation { duration: Theme.animations ? 180 : 0; easing.type: Easing.OutCubic } }
        Behavior on opacity {
            NumberAnimation { duration: Theme.animations ? 180 : 0 }
        }
        onOpacityChanged: if (opacity === 0 && !osd.shown) osd.visible = false
        color: Theme.pill; border.color: Theme.pillRim; border.width: 3

        Rectangle {  // icon bubble in the accent glow
            id: bubble
            x: 16; anchors.verticalCenter: parent.verticalCenter
            width: 76; height: 76; radius: 38
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0; color: Theme.selA }
                GradientStop { position: 1; color: Theme.selB }
            }
            Image {
                anchors.centerIn: parent; width: 44; height: 44; sourceSize: Qt.size(88, 88)
                source: "icons/osd/" + (osd.what === "Volume" ? (osd.value > 0 ? "volume" : "volume-mute") : "brightness") + ".svg"
            }
        }
        Rectangle {  // track
            id: track
            anchors.left: bubble.right; anchors.leftMargin: 26
            anchors.right: label.left; anchors.rightMargin: 22
            anchors.verticalCenter: parent.verticalCenter
            height: 18; radius: 9; color: "#33ffffff"
            Rectangle {
                width: Math.max(height, parent.width * osd.value / 100); height: parent.height; radius: 9
                visible: osd.value > 0
                Behavior on width { NumberAnimation { duration: Theme.animations ? 90 : 0 } }
                gradient: Gradient {
                    orientation: Gradient.Horizontal
                    GradientStop { position: 0; color: Theme.selA }
                    GradientStop { position: 1; color: Theme.selB }
                }
            }
        }
        Text {
            id: label
            anchors.right: parent.right; anchors.rightMargin: 34; anchors.verticalCenter: parent.verticalCenter
            width: 92; horizontalAlignment: Text.AlignRight
            text: osd.value + "%"
            font.family: Theme.font; font.pixelSize: 36; font.weight: Font.Black; color: Theme.text
        }
    }
}
