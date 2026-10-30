import QtQuick
import QtQuick.Effects

// Full-screen blurred, dimmed art behind everything; crossfades when the art changes.
Item {
    id: bd
    property string source
    property real dim: 0.5
    property bool flip: false
    clip: true
    onSourceChanged: { flip = !flip; (flip ? a : b).source = source }

    Image { id: a; anchors.fill: parent; fillMode: Image.PreserveAspectCrop; asynchronous: true; visible: false
            sourceSize: Qt.size(480, 270) }
    Image { id: b; anchors.fill: parent; fillMode: Image.PreserveAspectCrop; asynchronous: true; visible: false
            sourceSize: Qt.size(480, 270) }
    MultiEffect { source: a; anchors.fill: parent; blurEnabled: true; blur: 1; blurMax: 48; saturation: 0.15
                  opacity: bd.flip ? 1 : 0; Behavior on opacity { NumberAnimation { duration: Theme.fade } } }
    MultiEffect { source: b; anchors.fill: parent; blurEnabled: true; blur: 1; blurMax: 48; saturation: 0.15
                  opacity: bd.flip ? 0 : 1; Behavior on opacity { NumberAnimation { duration: Theme.fade } } }
    Rectangle { anchors.fill: parent; color: "#0b0c18"; opacity: bd.dim }
}
