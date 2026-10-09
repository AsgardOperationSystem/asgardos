import QtQuick
import QtQuick.Effects

// Clips its children to a rounded rectangle (plain clip only clips to the bounding box).
Item {
    id: r
    property real radius: 0
    default property alias content: inner.data
    Item {
        id: inner
        anchors.fill: parent
        layer.enabled: true
        layer.effect: MultiEffect { maskEnabled: true; maskSource: mask; maskThresholdMin: 0.5; maskSpreadAtMin: 1.0 }
    }
    Rectangle { id: mask; anchors.fill: parent; radius: r.radius; visible: false; layer.enabled: true }
}
