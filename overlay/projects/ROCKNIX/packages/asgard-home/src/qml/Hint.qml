import QtQuick

// "(A) Select" — glyph + label.
Row {
    property alias glyph: g.text
    property alias label: t.text
    property int size: 44
    spacing: 10
    Glyph { id: g; size: parent.size; anchors.verticalCenter: parent.verticalCenter }
    Text {
        id: t; anchors.verticalCenter: parent.verticalCenter
        font.family: Theme.font; font.pixelSize: parent.size * 0.86; font.weight: Font.Black; color: Theme.text
    }
}
