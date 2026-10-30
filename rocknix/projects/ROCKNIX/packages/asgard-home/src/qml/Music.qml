import QtQuick
import QtQuick.Window
import QtQuick.Effects

// Asgard Music (asgard-home --music, the Music Player system's emulator): now playing on the top screen, the queue and
// touch controls on the bottom one; without a playlist, a playlist picker on both. `music` is the C++ player (mpv).
//   d-pad up/down  move in the list     A  play the selected song (picker: open the playlist)
//   X  play / pause    LB / RB  previous / next    left / right  -10 s / +10 s    Y  shuffle    select  repeat
//   B  the playlist picker (B again: back to the player)
QtObject {
    id: app
    property int sel: Math.max(0, music.current)     // the queue's selected row
    property int pick: 0                             // the picker's selected playlist
    property bool picking: music.name === ""
    readonly property var cur: music.current >= 0 && music.current < music.tracks.length ? music.tracks[music.current] : null
    // The song's art, else its playlist's cover (the picker: the selected playlist's)
    readonly property var art: app.picking ? (pickedList && pickedList.cover) || ""
                                           : cur && cur.cover ? cur.cover : (nowList && nowList.cover) || ""
    readonly property var pickedList: music.playlists.length ? music.playlists[Math.min(pick, music.playlists.length - 1)] : null
    readonly property var nowList: music.playlists.find(p => p.name === music.name) || null
    function clock(s) { s = Math.max(0, Math.floor(s || 0)); return Math.floor(s / 60) + ":" + ("0" + s % 60).slice(-2) }
    function upNext() {
        if (!cur || music.tracks.length < 2 || music.shuffle) return ""
        const n = music.tracks[(music.current + 1) % music.tracks.length]
        return n.artist ? n.title + "  ·  " + n.artist : n.title
    }

    Component.onCompleted: Theme.accent = music.setting("asgard.accent", "aurora")
    property Connections onCurrent: Connections { target: music; function onCurrentChanged() { app.sel = music.current } }
    property Connections input: Connections {
        target: pad
        function onPressed(b) {
            if (app.picking) {
                const n = music.playlists.length
                if (b === "up" || b === "left") app.pick = (app.pick + n - 1) % Math.max(1, n)
                else if (b === "down" || b === "right") app.pick = (app.pick + 1) % Math.max(1, n)
                else if (b === "a" && app.pickedList) { music.load(app.pickedList.path); app.picking = false }
                else if (b === "b" && music.tracks.length) app.picking = false
                return
            }
            if (b === "up") app.sel = Math.max(0, app.sel - 1)
            else if (b === "down") app.sel = Math.min(music.tracks.length - 1, app.sel + 1)
            else if (b === "a") music.play(app.sel)
            else if (b === "x") music.toggle()
            else if (b === "lb") music.prev()
            else if (b === "rb") music.next()
            else if (b === "left") music.seek(-10)
            else if (b === "right") music.seek(10)
            else if (b === "y") music.toggleShuffle()
            else if (b === "select") music.cycleRepeat()
            else if (b === "b" || b === "start") { app.pick = Math.max(0, music.playlists.findIndex(p => p.name === music.name)); app.picking = true }
        }
    }

    // Rounded art with a soft shadow; the note icon when there's none.
    component Cover: Item {
        property string source
        property int radius: 36
        Rectangle { anchors.fill: parent; anchors.margins: -2; radius: parent.radius + 2; color: "#000000"; opacity: 0.35; y: 14 }
        Rectangle { id: ph; anchors.fill: parent; radius: parent.radius; color: Theme.pill; border.color: Theme.pillRim; border.width: 3
            Image { anchors.centerIn: parent; width: parent.width * 0.36; height: width; source: "icons/music/note.svg"; sourceSize: Qt.size(256, 256); opacity: 0.6 } }
        Image { id: img; anchors.fill: parent; source: parent.source; fillMode: Image.PreserveAspectCrop; asynchronous: true
                sourceSize: Qt.size(720, 720); visible: false; smooth: true }
        Rectangle { id: mask; anchors.fill: parent; radius: parent.radius; visible: false; layer.enabled: true }
        MultiEffect { anchors.fill: parent; source: img; maskEnabled: true; maskSource: mask; visible: img.status === Image.Ready }
    }
    component IconButton: Rectangle {
        property string icon
        property bool on: true
        signal clicked()
        width: 150; height: 150; radius: width / 2
        color: "transparent"
        Image { anchors.centerIn: parent; width: parent.width * 0.5; height: width; source: "icons/music/" + parent.icon + ".svg"
                sourceSize: Qt.size(160, 160); opacity: parent.on ? 1 : 0.4 }
        TapHandler { onTapped: parent.clicked() }
    }
    component ProgressBar: Item {
        id: pb
        property bool seekable: false
        height: 18
        Rectangle { anchors.fill: parent; radius: height / 2; color: "#40ffffff" }
        Rectangle {
            width: music.duration > 0 ? parent.width * Math.min(1, music.position / music.duration) : 0
            height: parent.height; radius: height / 2
            gradient: Gradient { orientation: Gradient.Horizontal; GradientStop { position: 0; color: Theme.selA } GradientStop { position: 1; color: Theme.selB } }
        }
        TapHandler { enabled: pb.seekable; onTapped: (ev) => { if (music.duration > 0) music.seekTo(music.duration * ev.position.x / pb.width) } }
    }

    // ---- top screen: now playing (or the picked playlist) ----
    property Window top: Window {
        title: "Asgard Music"
        width: 1920; height: 1080; color: "#0b0c14"; visible: !shotMode
        Backdrop { anchors.fill: parent; source: app.art; dim: 0.55 }
        Item {
            width: parent.height > 0 ? Math.round(1080 * parent.width / parent.height) : 1920
            height: 1080; anchors.centerIn: parent; scale: parent.height / 1080

            Cover { id: bigCover; x: 140; y: 190; width: 700; height: 700; source: app.art }
            Column {
                x: 940; width: parent.width - x - 140; anchors.verticalCenter: bigCover.verticalCenter; spacing: 22
                Text { width: parent.width; elide: Text.ElideRight; color: Theme.textDim; font.family: Theme.font; font.pixelSize: 40; font.weight: Font.Black
                       text: app.picking ? "PLAYLISTS" : (music.name + "  ·  " + (music.current + 1) + " / " + music.tracks.length).toUpperCase() }
                Text { width: parent.width; wrapMode: Text.WordWrap; maximumLineCount: 2; elide: Text.ElideRight; color: Theme.text
                       font.family: Theme.font; font.pixelSize: 92; font.weight: Font.Black; lineHeight: 0.95
                       text: app.picking ? (app.pickedList ? app.pickedList.name : "No playlists") : (app.cur ? app.cur.title : "") }
                Text { width: parent.width; elide: Text.ElideRight; color: Theme.textDim; font.family: Theme.font; font.pixelSize: 52; font.weight: Font.Bold
                       text: app.picking ? (app.pickedList ? app.pickedList.songs + " songs" : "Add .m3u playlists to Tools")
                                         : (app.cur && app.cur.artist ? app.cur.artist : "") }
                Item { width: 1; height: 40 }
                ProgressBar { width: parent.width; visible: !app.picking }
                Item {
                    width: parent.width; height: 56; visible: !app.picking
                    Text { text: app.clock(music.position); color: Theme.textDim; font.family: Theme.font; font.pixelSize: 40; font.weight: Font.Black }
                    Row {
                        anchors.horizontalCenter: parent.horizontalCenter; spacing: 26
                        Image { width: 50; height: 50; source: "icons/music/" + (music.playing ? "play" : "pause") + ".svg"; sourceSize: Qt.size(100, 100) }
                        Image { width: 50; height: 50; source: "icons/music/shuffle.svg"; sourceSize: Qt.size(100, 100); opacity: music.shuffle ? 1 : 0.3 }
                        Image { width: 50; height: 50; source: "icons/music/" + (music.repeat === "one" ? "repeat-one" : "repeat") + ".svg"
                                sourceSize: Qt.size(100, 100); opacity: music.repeat === "off" ? 0.3 : 1 }
                    }
                    Text { anchors.right: parent.right; text: app.clock(music.duration); color: Theme.textDim; font.family: Theme.font; font.pixelSize: 40; font.weight: Font.Black }
                }
                Text { width: parent.width; elide: Text.ElideRight; visible: !app.picking && text !== "Up next:  "; color: Theme.textDim; opacity: 0.85
                       font.family: Theme.font; font.pixelSize: 38; font.weight: Font.Bold; text: "Up next:  " + app.upNext() }
            }
        }
    }

    // ---- bottom screen: the queue and controls (or the playlist picker) ----
    property Window bottom: Window {
        title: "Asgard Music (Bottom)"
        width: 1240; height: 1080; color: "#0b0c14"; visible: !shotMode
        Backdrop { anchors.fill: parent; source: app.art; dim: 0.72 }
        Item {
            width: parent.height > 0 ? Math.round(1080 * parent.width / parent.height) : 1240
            height: 1080; anchors.centerIn: parent; scale: parent.height / 1080

            // The queue
            Rectangle {
                id: panel; visible: !app.picking
                x: 30; y: 30; width: parent.width - 60; height: 720; radius: 48
                color: Theme.panel; border.color: Theme.panelRim; border.width: 3; clip: true
                ListView {
                    id: queue
                    anchors.fill: parent; anchors.margins: 18
                    model: music.tracks
                    currentIndex: app.sel
                    highlightMoveDuration: Theme.anim; preferredHighlightBegin: height / 2 - 60; preferredHighlightEnd: height / 2 + 60
                    highlightRangeMode: ListView.ApplyRange
                    highlight: Rectangle { radius: 30
                        gradient: Gradient { orientation: Gradient.Horizontal; GradientStop { position: 0; color: Theme.selA } GradientStop { position: 1; color: Theme.selB } } }
                    delegate: Item {
                        width: queue.width; height: 120
                        Row {
                            x: 24; anchors.verticalCenter: parent.verticalCenter; spacing: 22
                            Item { width: 84; height: 84
                                Image { anchors.fill: parent; source: modelData.cover || "icons/music/note.svg"; sourceSize: Qt.size(168, 168)
                                        fillMode: Image.PreserveAspectCrop; asynchronous: true; opacity: modelData.cover ? 1 : 0.5 }
                                Image { anchors.centerIn: parent; width: 44; height: 44; visible: index === music.current
                                        source: "icons/music/" + (music.playing ? "play" : "pause") + ".svg"; sourceSize: Qt.size(88, 88) } }
                            Column {
                                width: queue.width - 84 - 22 - 48 - 120; anchors.verticalCenter: parent.verticalCenter
                                Text { width: parent.width; elide: Text.ElideRight; text: modelData.title; color: Theme.text
                                       font.family: Theme.font; font.pixelSize: 40; font.weight: Font.Black }
                                Text { width: parent.width; elide: Text.ElideRight; text: modelData.artist; color: Theme.textDim; visible: text !== ""
                                       font.family: Theme.font; font.pixelSize: 32; font.weight: Font.Bold }
                            }
                        }
                        Text { anchors.right: parent.right; anchors.rightMargin: 28; anchors.verticalCenter: parent.verticalCenter
                               text: modelData.length > 0 ? app.clock(modelData.length) : ""; color: Theme.textDim
                               font.family: Theme.font; font.pixelSize: 34; font.weight: Font.Black }
                        TapHandler { onTapped: { app.sel = index; music.play(index) } }
                    }
                }
            }
            // Seek bar and controls
            Item {
                visible: !app.picking
                x: 60; y: 780; width: parent.width - 120; height: 280
                ProgressBar { y: 6; width: parent.width; seekable: true }
                Row {
                    anchors.horizontalCenter: parent.horizontalCenter; y: 40; spacing: 34
                    IconButton { icon: "shuffle"; on: music.shuffle; width: 120; height: 120; anchors.verticalCenter: parent.verticalCenter; onClicked: music.toggleShuffle() }
                    IconButton { icon: "prev"; onClicked: music.prev() }
                    Rectangle {
                        width: 170; height: 170; radius: 85; anchors.verticalCenter: parent.verticalCenter
                        gradient: Gradient { GradientStop { position: 0; color: Theme.selA } GradientStop { position: 1; color: Theme.selB } }
                        Image { anchors.centerIn: parent; anchors.horizontalCenterOffset: music.playing ? 0 : 6; width: 84; height: 84
                                source: "icons/music/" + (music.playing ? "pause" : "play") + ".svg"; sourceSize: Qt.size(168, 168) }
                        TapHandler { onTapped: music.toggle() }
                    }
                    IconButton { icon: "next"; onClicked: music.next() }
                    IconButton { icon: music.repeat === "one" ? "repeat-one" : "repeat"; on: music.repeat !== "off"; width: 120; height: 120
                                 anchors.verticalCenter: parent.verticalCenter; onClicked: music.cycleRepeat() }
                }
                Row {
                    anchors.horizontalCenter: parent.horizontalCenter; y: 225; spacing: 30
                    Hint { glyph: "X"; label: "Play/Pause"; size: 34 }
                    Hint { glyph: "R"; label: "Next"; size: 34 }
                    Hint { glyph: "Y"; label: "Shuffle"; size: 34 }
                    Hint { glyph: "B"; label: "Playlists"; size: 34 }
                }
            }

            // The playlist picker
            GridView {
                id: picker; visible: app.picking
                x: 40; y: 40; width: parent.width - 80; height: parent.height - 160
                cellWidth: width / 3; cellHeight: cellWidth + 70; currentIndex: app.pick
                model: music.playlists
                delegate: Item {
                    width: picker.cellWidth; height: picker.cellHeight
                    Rectangle { anchors.fill: tile; anchors.margins: -10; radius: 46; visible: index === app.pick
                        gradient: Gradient { GradientStop { position: 0; color: Theme.selA } GradientStop { position: 1; color: Theme.selB } } }
                    Cover { id: tile; x: 26; y: 20; width: parent.width - 52; height: width; radius: 36; source: modelData.cover }
                    Text { anchors.top: tile.bottom; anchors.topMargin: 14; width: parent.width; horizontalAlignment: Text.AlignHCenter; elide: Text.ElideRight
                           text: modelData.name; color: Theme.text; font.family: Theme.font; font.pixelSize: 38; font.weight: Font.Black }
                    TapHandler { onTapped: { app.pick = index; music.load(modelData.path); app.picking = false } }
                }
            }
            Row {
                visible: app.picking; anchors.horizontalCenter: parent.horizontalCenter; y: parent.height - 90; spacing: 40
                Hint { glyph: "A"; label: "Play"; size: 40 }
                Hint { glyph: "B"; label: "Back"; size: 40; visible: music.tracks.length > 0 }
            }
        }
    }
}
