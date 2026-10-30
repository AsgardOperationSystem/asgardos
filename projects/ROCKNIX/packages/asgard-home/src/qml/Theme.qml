pragma Singleton
import QtQuick

// Look of the iiSU-style home: dark translucent pills with a light rim, lavender glass panels, white-rimmed tiles,
// a cyan-violet selection glow, one rounded heavy typeface. Sizes are in Thor pixels (1920x1080 / 1240x1080).
QtObject {
    // Nunito (OFL), static Bold/ExtraBold/Black cut from the variable font; one family, so font.weight picks.
    readonly property FontLoader bold: FontLoader { source: "fonts/Nunito-Bold.ttf" }
    readonly property FontLoader extraBold: FontLoader { source: "fonts/Nunito-ExtraBold.ttf" }
    readonly property FontLoader black: FontLoader { source: "fonts/Nunito-Black.ttf" }
    readonly property string font: black.name

    readonly property color text: "#ffffff"
    readonly property color textDim: "#c9c8e0"
    readonly property color pill: "#d6181a26"
    readonly property color pillRim: "#59ffffff"
    readonly property color panel: "#c43b3c5c"
    readonly property color panelRim: "#33ffffff"
    readonly property color tileRim: "#ebe9f7"
    // Accent (Settings > Appearance): the selection glow and highlights. asgard.accent in system.cfg.
    property string accent: "aurora"
    readonly property var accents: ({ aurora: ["#47d1ff", "#8f7dff"], sunset: ["#ffb35c", "#ff4f8b"],
                                      mint: ["#3ee6b0", "#3fb8ff"], gold: ["#ffd86b", "#f59e24"] })
    readonly property color selA: (accents[accent] || accents.aurora)[0]
    readonly property color selB: (accents[accent] || accents.aurora)[1]
    property bool animations: true             // Settings > Appearance > Animations (asgard.animations)
    readonly property color goldA: "#ffd86b"          // trophies: earned / mastered
    readonly property color goldB: "#f5a524"
    readonly property color tagBg: "#f4f4fb"
    readonly property color tagText: "#3a3b52"

    readonly property int anim: animations ? 180 : 0     // ms, selection moves
    readonly property int fade: animations ? 320 : 0     // ms, art crossfades

    // Pastel colour per system (stable hash), for system tiles and the little system badges.
    readonly property var pastels: ["#c9d4ff", "#ffd3e6", "#cdf3e4", "#fff0c2", "#e4d7ff", "#cdeeff", "#ffdccc", "#dff5c8"]
    readonly property var inks: ["#5866d8", "#d2558f", "#2f9e78", "#c48a14", "#7c5bd6", "#2c8fc4", "#d06a3c", "#5f9a2b"]
    function hash(s) { let h = 0; for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0; return h }
    function pastel(sys) { return pastels[hash(sys) % pastels.length] }
    function ink(sys) { return inks[hash(sys) % inks.length] }
}
