import QtQuick
import QtQuick.Effects

// Bottom-screen tab bar: five glossy icons in a pill, LB/RB tags on the rim, the current tab lifted and lit.
Item {
    id: dock
    property int current: 0
    signal tabTapped(int index)   // bottom touchscreen
    readonly property var icons: ["home", "games", "trophy", "profile", "apps"]
    width: 900; height: 150

    Pill { anchors.fill: parent }
    Row {
        id: row
        anchors.centerIn: parent; spacing: 64
        Repeater {
            model: dock.icons
            Item {
                width: 112; height: 112
                readonly property bool on: index === dock.current
                MouseArea { anchors.fill: parent; anchors.margins: -24; onClicked: dock.tabTapped(index) }
                Rectangle {  // soft disc behind the current tab
                    anchors.centerIn: parent; width: 124; height: 124; radius: 62
                    color: "#2effffff"; opacity: parent.on ? 1 : 0
                    Behavior on opacity { NumberAnimation { duration: Theme.anim } }
                }
                Image {
                    id: icon
                    anchors.centerIn: parent; width: 92; height: 92
                    source: "icons/" + modelData + ".svg"; sourceSize: Qt.size(184, 184); smooth: true
                    scale: parent.on ? 1.12 : 0.92
                    opacity: parent.on ? 1 : 0.8
                    Behavior on scale { NumberAnimation { duration: Theme.anim; easing.type: Easing.OutBack; easing.overshoot: 2.5 } }
                }
            }
        }
    }
    Tag { text: "LB"; x: 26; y: -18 }
    Tag { text: "RB"; anchors.right: parent.right; anchors.rightMargin: 26; y: -18 }
}
