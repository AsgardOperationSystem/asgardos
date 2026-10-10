import QtQuick

// "(A) Select" — glyph + label.
Row {
    property alias glyph: g.text
    property alias label: t.text
    property alias icon: g.icon
    signal tapped()                 // top touchscreen
    property int size: 44
    spacing: 10
    Glyph { id: g; size: parent.size; anchors.verticalCenter: parent.verticalCenter }
    Text {
        id: t; anchors.verticalCenter: parent.verticalCenter
        font.family: Theme.font; font.pixelSize: parent.size * 0.86; font.weight: Font.Black; color: Theme.text
    }
    TapHandler { onTapped: parent.tapped() }   // a handler, not an item: a MouseArea child made the Row re-layout forever
}
