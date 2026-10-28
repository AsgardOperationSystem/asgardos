import QtQuick
import QtQuick.Window

// Asgard Files (asgard-home --files, Tools > Files): the folder on the top screen; places, the clipboard, progress and
// the actions on the bottom one. `files` is the C++ side (files.cpp). Touch works everywhere.
//   d-pad up/down  move    A / right  open a folder    B / left  up a folder    X  mark (several)
//   Y  actions (d-pad + A on the bottom screen)    LB / RB  previous / next place    select  hidden files
// Actions work on the marked items, else on the selected one.
QtObject {
    id: app
    property int sel: 0
    property var marks: ({})                         // name -> true
    property bool menu: false                        // the pad is on the bottom screen's actions
    property int act: 0
    readonly property var cur: files.entries.length ? files.entries[Math.min(sel, files.entries.length - 1)] : null
    readonly property int marked: Object.keys(marks).length
    function targets() { return marked ? Object.keys(marks) : cur ? [cur.name] : [] }
    function count(n) { return n + (n === 1 ? " item" : " items") }

    function human(b) {
        const u = ["B", "KB", "MB", "GB", "TB"]; let i = 0
        while (b >= 1000 && i < 4) { b /= 1000; i++ }
        return (b < 10 && i ? b.toFixed(1) : Math.round(b)) + " " + u[i]
    }
    // The path from its place: "SD card  ›  ROMs  ›  gba"
    readonly property var place: files.places.filter(p => files.path === p.path || files.path.startsWith(p.path + "/"))
                                     .sort((a, b) => b.path.length - a.path.length)[0] || null
    readonly property string crumbs: {
        const rest = place ? files.path.slice(place.path.length) : files.path
        return [place ? place.name : "/"].concat(rest.split("/").filter(x => x)).join("   ›   ")
    }
    function placeIcon(n) { return ({ "SD card": "sd", "ROMs": "roms", "Thor": "thor" })[n] || "folder" }
    function goPlace(d) {
        const ps = files.places, i = ps.findIndex(p => place && p.path === place.path)
        files.open(ps[(i + d + ps.length) % ps.length].path)
    }

    function openCur() { if (cur && cur.dir) files.open(files.path.replace(/\/$/, "") + "/" + cur.name) }
    function mark(name) { const m = Object.assign({}, marks); if (m[name]) delete m[name]; else m[name] = true; marks = m }

    // The bottom screen's actions: [icon, label, enabled, run]
    readonly property var actions: [
        ["copy", "Copy", !!cur, () => { files.copy(targets(), false); marks = ({}) }],
        ["cut", "Move", !!cur, () => { files.copy(targets(), true); marks = ({}) }],
        ["paste", "Paste", files.clipCount > 0 && !files.busy, () => files.paste()],
        ["rename", "Rename", !!cur && marked <= 1, () => { const n = targets()[0]
            keyboard.ask("Rename " + n, n, false, v => { if (v && v.trim()) files.rename(n, v.trim()) }) }],
        ["newfolder", "New folder", true, () => keyboard.ask("New folder", "", false, v => { if (v && v.trim()) files.makeDir(v.trim()) })],
        ["delete", "Delete", !!cur && !files.busy, () => { const t = targets()
            dialog.open("Delete " + (t.length === 1 ? t[0] : count(t.length)), "It's gone for good: there's no trash.", "Delete",
                        () => { files.remove(t); marks = ({}) }) }],
        ["all", marked === files.entries.length && marked ? "Unmark all" : "Mark all", files.entries.length > 0,
         () => { const m = {}; if (marked !== files.entries.length) for (const e of files.entries) m[e.name] = true; marks = m }],
        ["eye", files.hidden ? "Hide hidden" : "Show hidden", true, () => files.toggleHidden()]]
    function runAct(i) { const a = actions[i]; if (a[2]) { menu = false; a[3]() } }

    Component.onCompleted: Theme.accent = files.setting("asgard.accent", "aurora")
    property Connections onFolder: Connections {
        target: files
        property string last: files.path
        function onChanged() {   // a new folder starts at the top; a refresh of the same one keeps the row
            if (files.path !== last) { app.sel = 0; app.marks = ({}); last = files.path }
            app.sel = Math.min(app.sel, Math.max(0, files.entries.length - 1))
        }
    }
    property Connections input: Connections {
        target: pad
        function onPressed(b) {
            if (keyboard.nav(b) || dialog.nav(b)) return
            const n = files.entries.length
            if (app.menu) {
                if (b === "left" || b === "right") app.act = app.act % 2 ? app.act - 1 : app.act + 1
                else if (b === "up") app.act = (app.act + app.actions.length - 2) % app.actions.length
                else if (b === "down") app.act = (app.act + 2) % app.actions.length
                else if (b === "a") app.runAct(app.act)
                else if (b === "b" || b === "y") app.menu = false
                return
            }
            if (b === "up") app.sel = Math.max(0, app.sel - 1)
            else if (b === "down") app.sel = Math.min(n - 1, app.sel + 1)
            else if (b === "a" || b === "right") app.openCur()
            else if (b === "b" || b === "left") files.up()
            else if (b === "x" && app.cur) { app.mark(app.cur.name); app.sel = Math.min(n - 1, app.sel + 1) }
            else if (b === "y") { app.menu = true }
            else if (b === "lb") app.goPlace(-1)
            else if (b === "rb") app.goPlace(1)
            else if (b === "select") files.toggleHidden()
        }
    }

    // ---- top screen: the folder ----
    property Window top: Window {
        title: "Asgard Files"
        width: 1920; height: 1080; color: "#0b0c14"; visible: !shotMode
        Backdrop { anchors.fill: parent; source: "../media/music/covers/Files.png"; dim: 0.6 }
        Item {
            width: parent.height > 0 ? Math.round(1080 * parent.width / parent.height) : 1920
            height: 1080; anchors.centerIn: parent; scale: parent.height / 1080

            // where we are, and the free space there
            Rectangle {
                id: head
                x: 60; y: 44; width: parent.width - 120; height: 104; radius: 52
                color: Theme.pill; border.color: Theme.pillRim; border.width: 3
                Image { x: 34; anchors.verticalCenter: parent.verticalCenter; width: 52; height: 52; sourceSize: Qt.size(104, 104)
                        source: "icons/files/" + app.placeIcon(app.place ? app.place.name : "") + ".svg" }
                Text { x: 108; anchors.verticalCenter: parent.verticalCenter; width: parent.width - x - spaceText.width - 70
                       elide: Text.ElideLeft; text: app.crumbs; color: Theme.text
                       font.family: Theme.font; font.pixelSize: 44; font.weight: Font.Black }
                Text { id: spaceText; anchors.right: parent.right; anchors.rightMargin: 40; anchors.verticalCenter: parent.verticalCenter
                       text: files.space; color: Theme.textDim; font.family: Theme.font; font.pixelSize: 36; font.weight: Font.Bold }
            }

            Rectangle {
                x: 60; y: 178; width: parent.width - 120; height: parent.height - y - 50; radius: 48
                color: Theme.panel; border.color: Theme.panelRim; border.width: 3; clip: true
                Text { anchors.centerIn: parent; visible: !files.entries.length; text: "Empty folder"; color: Theme.textDim
                       font.family: Theme.font; font.pixelSize: 52; font.weight: Font.Black }
                ListView {
                    id: list
                    anchors.fill: parent; anchors.margins: 18
                    model: files.entries
                    currentIndex: app.sel
                    highlightMoveDuration: Theme.anim; preferredHighlightBegin: height / 2 - 56; preferredHighlightEnd: height / 2 + 56
                    highlightRangeMode: ListView.ApplyRange
                    highlight: Rectangle { radius: 30; opacity: app.menu ? 0.45 : 1
                        gradient: Gradient { orientation: Gradient.Horizontal; GradientStop { position: 0; color: Theme.selA } GradientStop { position: 1; color: Theme.selB } } }
                    delegate: Item {
                        width: list.width; height: 112
                        readonly property bool on: !!app.marks[modelData.name]
                        Rectangle { anchors.fill: parent; anchors.margins: 4; radius: 28; color: "#26ffffff"; visible: parent.on && index !== app.sel }
                        Image { x: 30; anchors.verticalCenter: parent.verticalCenter; width: 58; height: 58; sourceSize: Qt.size(116, 116)
                                source: "icons/files/" + (modelData.dir ? "folder" : "file") + ".svg"; opacity: modelData.dir ? 1 : 0.8 }
                        Text { x: 120; anchors.verticalCenter: parent.verticalCenter; width: parent.width - x - info.width - 140
                               elide: Text.ElideMiddle; text: modelData.name; color: Theme.text
                               font.family: Theme.font; font.pixelSize: 42; font.weight: Font.Black }
                        Text { id: info; anchors.right: parent.right; anchors.rightMargin: 110; anchors.verticalCenter: parent.verticalCenter
                               text: modelData.dir ? "Folder" : app.human(modelData.size) + "   ·   " + Qt.formatDate(new Date(modelData.modified), "d MMM yyyy")
                               color: Theme.textDim; font.family: Theme.font; font.pixelSize: 34; font.weight: Font.Bold }
                        Rectangle { anchors.right: parent.right; anchors.rightMargin: 34; anchors.verticalCenter: parent.verticalCenter
                                    width: 52; height: 52; radius: 26; color: parent.on ? Theme.selB : "transparent"
                                    border.color: Theme.text; border.width: 3; opacity: parent.on || app.marked ? 1 : 0.35
                            Image { anchors.centerIn: parent; width: 34; height: 34; visible: parent.parent.on
                                    source: "icons/files/check.svg"; sourceSize: Qt.size(68, 68) }
                            TapHandler { onTapped: app.mark(modelData.name) } }
                        TapHandler {
                            onTapped: { if (index === app.sel) app.openCur(); else app.sel = index; app.menu = false }
                            onLongPressed: app.mark(modelData.name)
                        }
                    }
                }
            }
        }
    }

    // ---- bottom screen: places, the clipboard / progress, actions ----
    property Window bottom: Window {
        title: "Asgard Files (Bottom)"
        width: 1240; height: 1080; color: "#0b0c14"; visible: !shotMode
        Backdrop { anchors.fill: parent; source: "../media/music/covers/Files.png"; dim: 0.72 }
        Item {
            width: parent.height > 0 ? Math.round(1080 * parent.width / parent.height) : 1240
            height: 1080; anchors.centerIn: parent; scale: parent.height / 1080

            // places
            Row {
                x: 40; y: 40; spacing: 22
                Repeater {
                    model: files.places
                    Rectangle {
                        readonly property bool on: app.place && app.place.path === modelData.path
                        width: (1240 - 80 - 22 * (files.places.length - 1)) / files.places.length; height: 110; radius: 55
                        color: on ? "transparent" : Theme.pill; border.color: Theme.pillRim; border.width: on ? 0 : 3
                        gradient: on ? app.selGrad : null
                        Row { anchors.centerIn: parent; spacing: 18
                            Image { width: 50; height: 50; sourceSize: Qt.size(100, 100); source: "icons/files/" + app.placeIcon(modelData.name) + ".svg"
                                    anchors.verticalCenter: parent.verticalCenter }
                            Text { text: modelData.name; color: Theme.text; font.family: Theme.font; font.pixelSize: 40; font.weight: Font.Black
                                   anchors.verticalCenter: parent.verticalCenter } }
                        TapHandler { onTapped: files.open(modelData.path) }
                    }
                }
            }

            // the clipboard, an operation in progress, or the last error
            Rectangle {
                x: 40; y: 180; width: 1160; height: 150; radius: 44
                color: Theme.panel; border.color: Theme.panelRim; border.width: 3
                Text { x: 40; y: 26; width: parent.width - 80 - (stop.visible ? stop.width + 20 : 0); elide: Text.ElideRight
                       color: files.message && !files.busy ? "#ffb4b4" : Theme.text; font.family: Theme.font; font.pixelSize: 40; font.weight: Font.Black
                       text: files.busy ? files.busy + (files.progress >= 0 ? "  ·  " + Math.round(files.progress * 100) + "%" : "…")
                           : files.message ? files.message
                           : files.clipCount ? app.count(files.clipCount) + (files.clipCut ? " to move" : " to copy") + ": open a folder and paste"
                           : app.marked ? app.count(app.marked) + " marked" : "Y for actions  ·  X marks several" }
                Item {
                    x: 40; y: 94; width: parent.width - 80; height: 18; visible: !!files.busy
                    Rectangle { anchors.fill: parent; radius: 9; color: "#40ffffff" }
                    Rectangle { height: parent.height; radius: 9; gradient: Gradient { orientation: Gradient.Horizontal
                                    GradientStop { position: 0; color: Theme.selA } GradientStop { position: 1; color: Theme.selB } }
                                width: files.progress >= 0 ? parent.width * files.progress : parent.width * 0.3
                                x: files.progress >= 0 ? 0 : sweep.x
                                Item { id: sweep; x: 0; SequentialAnimation on x { running: files.busy !== "" && files.progress < 0; loops: Animation.Infinite
                                       NumberAnimation { from: 0; to: 1080 * 0.7; duration: 900 } NumberAnimation { from: 1080 * 0.7; to: 0; duration: 900 } } } }
                }
                Rectangle { id: stop; visible: !!files.busy; anchors.right: parent.right; anchors.rightMargin: 24; y: 18
                            width: 170; height: 64; radius: 32; color: Theme.pill; border.color: Theme.pillRim; border.width: 3
                    Text { anchors.centerIn: parent; text: "Stop"; color: Theme.text; font.family: Theme.font; font.pixelSize: 34; font.weight: Font.Black }
                    TapHandler { onTapped: files.cancel() } }
            }

            // actions, 2 x 4
            Grid {
                x: 40; y: 360; columns: 2; rowSpacing: 20; columnSpacing: 20
                Repeater {
                    model: app.actions
                    Rectangle {
                        readonly property bool on: app.menu && app.act === index
                        width: 570; height: 132; radius: 40
                        color: on ? "transparent" : Theme.pill; border.color: Theme.pillRim; border.width: on ? 0 : 3
                        gradient: on ? app.selGrad : null
                        opacity: modelData[2] ? 1 : 0.4
                        Row { x: 40; anchors.verticalCenter: parent.verticalCenter; spacing: 26
                            Image { width: 60; height: 60; sourceSize: Qt.size(120, 120); source: "icons/files/" + modelData[0] + ".svg"
                                    anchors.verticalCenter: parent.verticalCenter }
                            Text { text: modelData[1]; color: Theme.text; font.family: Theme.font; font.pixelSize: 42; font.weight: Font.Black
                                   anchors.verticalCenter: parent.verticalCenter } }
                        TapHandler { onTapped: app.runAct(index) }
                    }
                }
            }

            Row {
                anchors.horizontalCenter: parent.horizontalCenter; y: parent.height - 84; spacing: 34
                Hint { glyph: "A"; label: app.menu ? "Do" : "Open"; size: 38 }
                Hint { glyph: "B"; label: app.menu ? "Close" : "Up"; size: 38 }
                Hint { glyph: "X"; label: "Mark"; size: 38; visible: !app.menu }
                Hint { glyph: "Y"; label: "Actions"; size: 38; visible: !app.menu }
                Hint { glyph: "L"; label: "Places"; size: 38; visible: !app.menu }
            }

            Confirm { id: dialog; anchors.fill: parent }
            Keyboard { id: keyboard; anchors.fill: parent }
        }
    }
    property Gradient selGrad: Gradient { orientation: Gradient.Horizontal
        GradientStop { position: 0; color: Theme.selA } GradientStop { position: 1; color: Theme.selB } }
}
