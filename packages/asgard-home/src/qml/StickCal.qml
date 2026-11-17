import QtQuick
import "stickcal.js" as SC

// Stick and trigger calibration (Settings > Hardware > Calibration, CAL-4), over Settings like Confirm.
// open("stick"|"trigger", "left"|"right") measures one control step by step (let go, push each way and hold, ...), applies
// the result live and tests it: A keeps it (and saves it, CAL-2), Y measures again, B puts back what was there.
// open("all") only shows every control live. InputPlumber is stopped meanwhile (it hides and grabs the raw pad) and Home
// reads rsinput's own pad (pad.setRaw): its buttons still drive this, and Home leaves at any point, putting back
// the calibration that was in place. The maths is stickcal.js.
Item {
    id: cal
    property string mode: ""                 // "" closed, "measure", "test", "all"
    property string kind: "stick"            // "stick" or "trigger"
    property string side: "left"
    property var before: ({})                // rsinput's parameters when it opened: what B and Home put back
    property var params: ({})                // what's live now (the measured control's result in "test")
    property int step: 0
    property var got: ({})                   // the readings so far
    property var holdState: ({ ref: null, since: 0 })
    property real progress: 0
    readonly property var axes: pad.axes && pad.axes.length === 6 ? pad.axes : [0, 0, 0, 0, 0, 0]
    readonly property var steps: kind === "stick" ? SC.STICK_STEPS : SC.TRIGGER_STEPS
    readonly property string stepName: steps[Math.min(step, steps.length - 1)]
    readonly property color ink: "#2a2b3d"
    readonly property color inkDim: "#6f7186"
    readonly property color card: "#fbfbfd"
    readonly property color line: "#e4e5ec"
    visible: mode !== ""

    signal closed()

    function title() {
        return mode === "all" ? "Test controls" : (side === "left" ? "Left " : "Right ") + kind
    }
    function open(what, which) {
        before = backend.rsinput()
        params = before
        backend.stickcal(true)
        pad.setRaw(true)
        if (what === "all") { mode = "all"; return }
        kind = what; side = which
        measure()
    }
    function measure() {
        params = Object.assign({}, before, SC.measuring(kind, side))
        backend.setRsinput(params)
        step = 0; got = {}; holdState = { ref: null, since: 0 }; progress = 0
        mode = "measure"
    }
    function finish(keep) {
        if (keep && mode === "test")
            backend.saveRsinput(SC.savedText(params))
        else
            backend.setRsinput(before)
        pad.setRaw(false)
        backend.stickcal(false)   // InputPlumber back: it re-reads the pad's ranges and re-applies the saved calibration
        mode = ""
        closed()
    }
    function tick() {
        got = SC.track(kind, side, axes, got)
        const vals = SC.watched(kind, side, axes)
        const h = SC.hold(holdState, vals, SC.inPlace(kind, side, stepName, axes, got), Date.now())
        holdState = h.state
        progress = h.progress
        if (progress < 1) return
        got = SC.record(kind, stepName, vals, got)
        holdState = { ref: null, since: 0 }; progress = 0
        backend.sound("select")
        if (step + 1 < steps.length) { step++; return }
        params = Object.assign({}, before, SC.result(kind, side, got))
        backend.setRsinput(params)
        mode = "test"
    }
    // Every button is ours while open. Home (guide) leaves from anywhere, nothing kept.
    function nav(b) {
        if (!mode) return false
        if (b === "guide") finish(false)
        else if (mode === "measure" && b === "b") finish(false)
        else if (mode === "test" && b === "a") finish(true)
        else if (mode === "test" && b === "y") measure()
        else if (mode === "test" && b === "b") finish(false)
        else if (mode === "all" && (b === "a" || b === "b")) finish(false)
        return true
    }

    Timer { interval: 33; repeat: true; running: cal.mode === "measure"; onTriggered: cal.tick() }

    // --- look --------------------------------------------------------------------------------------------------------
    Rectangle { anchors.fill: parent; color: "#99000000"; MouseArea { anchors.fill: parent } }
    Rectangle {
        id: sheet
        x: 36; y: 36; width: parent.width - 72; height: parent.height - 72; radius: 44
        color: "#ebedf2"; border.color: "#ffffff"; border.width: 2

        // left: what to do
        Column {
            id: words
            x: 56; y: 52; width: sheet.width * 0.42 - 56; spacing: 22
            Row {
                spacing: 18
                Image { width: 52; height: 52; source: "icons/settings/gamepad.svg"; sourceSize: Qt.size(104, 104)
                        anchors.verticalCenter: parent.verticalCenter }
                Text { text: cal.title(); font.family: Theme.font; font.pixelSize: 44; font.weight: Font.Black; color: cal.ink
                       anchors.verticalCenter: parent.verticalCenter }
            }
            Row {                                   // one dot a step: done, now, to come
                visible: cal.mode === "measure"
                spacing: 12
                Repeater {
                    model: cal.steps.length
                    Rectangle {
                        width: index === cal.step ? 44 : 16; height: 16; radius: 8
                        color: index < cal.step ? Theme.selB : index === cal.step ? Theme.selA : "#c9cbd6"
                        Behavior on width { NumberAnimation { duration: Theme.anim } }
                    }
                }
            }
            Item { width: 1; height: 18 }
            Text {
                width: parent.width; wrapMode: Text.WordWrap
                text: cal.mode === "test" ? "Try it out"
                    : cal.mode === "all" ? "Everything, as games see it"
                    : cal.stepName === "rest" ? (cal.kind === "stick" ? "Let go of the stick" : "Let go of the trigger")
                    : cal.stepName === "press" ? "Press the trigger all the way"
                    : "Push the stick all the way " + cal.stepName
                font.family: Theme.font; font.pixelSize: 52; font.weight: Font.Black; color: cal.ink
            }
            Text {
                width: parent.width; wrapMode: Text.WordWrap
                text: cal.mode === "test" ? (cal.kind === "stick"
                        ? "The dot should reach every edge, and sit in the middle when you let go."
                        : "The bar should be empty at rest and full when pressed.")
                    : cal.mode === "all" ? "Sticks and triggers with the calibration that's saved."
                    : cal.stepName === "rest" ? "Leave it alone until the bar fills."
                    : "Hold it there until the bar fills, then let go."
                font.family: Theme.font; font.pixelSize: 30; font.weight: Font.Bold; color: cal.inkDim
            }
            Rectangle {                              // the hold
                visible: cal.mode === "measure"
                width: parent.width; height: 22; radius: 11; color: "#d6d8e0"
                Rectangle {
                    height: parent.height; radius: parent.radius; width: Math.max(parent.height, parent.width * cal.progress)
                    visible: cal.progress > 0
                    gradient: Gradient { orientation: Gradient.Horizontal
                        GradientStop { position: 0; color: Theme.selA } GradientStop { position: 1; color: Theme.selB } }
                }
            }
        }

        // the buttons
        Row {
            x: 56; anchors.bottom: parent.bottom; anchors.bottomMargin: 46; spacing: 34
            Repeater {
                model: cal.mode === "test" ? [["A", "Keep"], ["Y", "Measure again"], ["B", "Undo"], ["home", "Exit"]]
                     : cal.mode === "all" ? [["B", "Back"], ["home", "Exit"]]
                     : [["B", "Cancel"], ["home", "Exit"]]
                Row {
                    spacing: 12
                    Rectangle {
                        width: 46; height: 46; radius: 23; color: "transparent"; border.color: cal.ink; border.width: 3
                        anchors.verticalCenter: parent.verticalCenter
                        Text { anchors.centerIn: parent; anchors.verticalCenterOffset: -1; text: modelData[0]
                               visible: modelData[0] !== "home"
                               font.family: Theme.font; font.pixelSize: 28; font.weight: Font.Black; color: cal.ink }
                        Image { anchors.centerIn: parent; width: 26; height: 26; visible: modelData[0] === "home"
                                source: "icons/settings/home.svg"; sourceSize: Qt.size(52, 52) }
                    }
                    Text { text: modelData[1]; anchors.verticalCenter: parent.verticalCenter
                           font.family: Theme.font; font.pixelSize: 32; font.weight: Font.Black; color: cal.ink }
                }
            }
        }

        // right: the controls
        Rectangle {
            id: stage
            x: sheet.width * 0.44; y: 40; width: sheet.width - x - 40; height: sheet.height - 80; radius: 36
            color: cal.card

            // one control in "measure" / "test"
            Item {
                anchors.fill: parent
                visible: cal.mode === "measure" || cal.mode === "test"
                Gate {
                    visible: cal.kind === "stick"
                    anchors.centerIn: parent; size: Math.min(parent.width, parent.height) * 0.78
                    pos: cal.stickPos(cal.side)
                    target: cal.mode === "measure" ? cal.stepName : ""
                    marks: cal.mode === "measure" ? cal.stickMarks() : []
                }
                Gauge {
                    visible: cal.kind === "trigger"
                    anchors.centerIn: parent; height: parent.height * 0.72; width: 150
                    value: cal.triggerFrac(cal.side)
                    target: cal.mode === "measure" && cal.stepName === "press"
                }
            }
            // everything in "all"
            Row {
                visible: cal.mode === "all"
                anchors.centerIn: parent; spacing: 60
                Repeater {
                    model: ["left", "right"]
                    Row {
                        spacing: 34
                        layoutDirection: modelData === "left" ? Qt.LeftToRight : Qt.RightToLeft
                        Gauge { height: stage.height * 0.5; width: 70; value: cal.triggerFrac(modelData)
                                anchors.verticalCenter: parent.verticalCenter }
                        Column {
                            spacing: 24
                            Gate { size: Math.min(stage.width * 0.3, stage.height * 0.62); pos: cal.stickPos(modelData) }
                            Text { anchors.horizontalCenter: parent.horizontalCenter; text: modelData === "left" ? "Left" : "Right"
                                   font.family: Theme.font; font.pixelSize: 30; font.weight: Font.Black; color: cal.inkDim }
                        }
                    }
                }
            }
        }
    }

    // Where a stick's dot goes (-1..1): raw against rsinput's default range while measuring, else as games see it.
    function stickPos(which) {
        const s = SC.STICKS[which], x = axes[s[2]], y = axes[s[3]]
        if (mode === "measure") return [x / SC.AXIS_DEFAULT, y / SC.AXIS_DEFAULT]
        return [SC.fraction(params, s[0], x), SC.fraction(params, s[1], y)]
    }
    function stickMarks() {   // what's been recorded so far, as small dots
        const out = (got.rests || []).map(r => [r[0] / SC.AXIS_DEFAULT, r[1] / SC.AXIS_DEFAULT])
        for (const d of ["left", "right"]) if (got[d] !== undefined) out.push([got[d] / SC.AXIS_DEFAULT, 0])
        for (const d of ["up", "down"]) if (got[d] !== undefined) out.push([0, got[d] / SC.AXIS_DEFAULT])
        return out
    }
    function triggerFrac(which) {
        const t = SC.TRIGGERS[which], v = axes[t[1]]
        return mode === "measure" ? SC.triggerGauge(axes, which, got) : Math.max(0, SC.fraction(params, t[0], v))
    }

    // A stick's gate: a round well, its crosshair, the direction to push, and the dot.
    component Gate: Item {
        property real size: 400
        property var pos: [0, 0]
        property string target: ""
        property var marks: []
        width: size; height: size
        Rectangle { anchors.fill: parent; radius: width / 2; color: "#eef0f6"; border.color: cal.line; border.width: 4 }
        Rectangle { anchors.centerIn: parent; width: parent.width * 0.5; height: width; radius: width / 2
                    color: "transparent"; border.color: cal.line; border.width: 3 }
        Rectangle { anchors.centerIn: parent; width: parent.width - 40; height: 3; color: cal.line }
        Rectangle { anchors.centerIn: parent; height: parent.height - 40; width: 3; color: cal.line }
        Rectangle {                                  // where to push: a glow on that edge
            readonly property var at: ({ right: [1, 0], left: [-1, 0], down: [0, 1], up: [0, -1] })[parent.target]
            visible: !!at
            width: parent.size * 0.2; height: width; radius: width / 2; opacity: 0.35
            color: Theme.selA
            x: at ? (parent.width - width) / 2 + at[0] * (parent.width - width) / 2 : 0
            y: at ? (parent.height - height) / 2 + at[1] * (parent.height - height) / 2 : 0
            SequentialAnimation on opacity {
                running: Theme.animations && parent.visible; loops: Animation.Infinite
                NumberAnimation { to: 0.7; duration: 600 } NumberAnimation { to: 0.25; duration: 600 }
            }
        }
        Repeater {
            model: parent.marks
            Rectangle {
                width: 14; height: 14; radius: 7; color: cal.inkDim
                x: parent.width / 2 + Math.max(-1, Math.min(1, modelData[0])) * (parent.width / 2 - 20) - 7
                y: parent.height / 2 + Math.max(-1, Math.min(1, modelData[1])) * (parent.height / 2 - 20) - 7
            }
        }
        Rectangle {                                  // the stick
            width: parent.size * 0.13; height: width; radius: width / 2
            border.color: "white"; border.width: 4
            gradient: Gradient { GradientStop { position: 0; color: Theme.selA } GradientStop { position: 1; color: Theme.selB } }
            x: parent.width / 2 + Math.max(-1, Math.min(1, parent.pos[0])) * (parent.width / 2 - width / 2) - width / 2
            y: parent.height / 2 + Math.max(-1, Math.min(1, parent.pos[1])) * (parent.height / 2 - height / 2) - height / 2
        }
    }

    // A trigger: a tall pill that fills from the bottom.
    component Gauge: Rectangle {
        property real value: 0
        property bool target: false
        radius: width / 2; color: "#eef0f6"; border.color: target ? Theme.selA : cal.line; border.width: 4
        Rectangle {
            anchors.bottom: parent.bottom; anchors.horizontalCenter: parent.horizontalCenter; anchors.bottomMargin: 8
            width: parent.width - 16; radius: width / 2
            height: Math.max(width, (parent.height - 16) * Math.max(0, Math.min(1, parent.value)))
            visible: parent.value > 0.005
            gradient: Gradient { GradientStop { position: 0; color: Theme.selA } GradientStop { position: 1; color: Theme.selB } }
        }
    }
}
