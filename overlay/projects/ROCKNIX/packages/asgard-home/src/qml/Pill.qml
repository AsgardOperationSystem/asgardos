import QtQuick

// Dark translucent capsule with a light rim (status bars, hints, the dock).
Rectangle {
    radius: height / 2
    color: Theme.pill
    border.color: Theme.pillRim
    border.width: 3
}
