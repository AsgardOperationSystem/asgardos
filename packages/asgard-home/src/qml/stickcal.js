.pragma library
// Stick and trigger calibration maths (Settings > Hardware > Calibration, StickCal.qml): rsinput's parameters from raw
// readings, taken with that control's parameters reset so the driver reports raw values. GPcal's maths (Kdog, MIT):
// 95 % of the shorter half-travel is the range, the deadzone is 150 % of how far the rest readings spread (at least 5 %
// of the range), the antideadzone 80 % of the deadzone. Host-tested by test_stickcal.py against rsinput.c's formulas.

var AXIS_DEFAULT = 0x580       // rsinput's defaults (Reset)
var TRIGGER_DEFAULT = 0x610
var TRIGGER_MEASURE = 0x755    // a trigger's max while measuring: above any rest reading (the driver reports max - raw)
var HOLD_MS = 600              // a position counts once it has held this long
var STEADY = 30                // ... within this many raw units
var PUSHED = 0.4 * AXIS_DEFAULT    // this far from rest is pushed
var AT_REST = 0.25 * AXIS_DEFAULT  // this close to centre is at rest
// A trigger's travel isn't known until it's measured (raw 0 at the bottom isn't a given), so its steps go by what it does:
// pressed is this far past its rest and held at the deepest point it reached, let go is back near its rest (that step
// only checks it was released: a trigger needn't settle exactly where it rested before).
var TRIGGER_PRESSED = 0.15 * TRIGGER_DEFAULT
var TRIGGER_BOTTOM = 0.1           // of the travel so far: within this of the deepest reading is still at the bottom
var TRIGGER_LET_GO = 0.25          // ... and within this of the rest reading is let go

var STICKS = { left: ["axis_leftx", "axis_lefty", 0, 1], right: ["axis_rightx", "axis_righty", 3, 4] }  // + ABS codes
var TRIGGERS = { left: ["trigger_left", 2], right: ["trigger_right", 5] }
var AXIS_KEYS = ["min", "center", "max", "deadzone", "antideadzone"]
var TRIGGER_KEYS = ["max", "deadzone", "antideadzone"]
// A stick: let go, then each way and back. A trigger: let go, press, let go.
var STICK_STEPS = ["rest", "right", "rest", "left", "rest", "down", "rest", "up", "rest"]
var TRIGGER_STEPS = ["rest", "press", "rest"]

function paramNames() {
    var out = []
    for (var s in STICKS)
        for (var a = 0; a < 2; a++)
            for (var k = 0; k < AXIS_KEYS.length; k++) out.push(STICKS[s][a] + "_" + AXIS_KEYS[k])
    for (var t in TRIGGERS)
        for (var j = 0; j < TRIGGER_KEYS.length; j++) out.push(TRIGGERS[t][0] + "_" + TRIGGER_KEYS[j])
    return out
}

// One stick axis from raw readings: rests (at rest after each push) and lo / hi (pushed fully each way).
function axisParams(rests, lo, hi) {
    var c = 0, spread = 0
    for (var i = 0; i < rests.length; i++) c += rests[i] / rests.length
    for (var j = 0; j < rests.length; j++) spread = Math.max(spread, Math.abs(rests[j] - c))
    var m = 0.95 * Math.min(hi - c, c - lo)
    var dz = Math.max(1.5 * spread, 0.05 * m)
    return { min: -Math.trunc(m), center: -Math.round(c), max: Math.trunc(m), deadzone: Math.trunc(dz),
             antideadzone: Math.trunc(0.8 * dz) }
}

// One trigger from its readings with max = TRIGGER_MEASURE, at rest and pressed fully. max becomes the raw rest value,
// so it reads 0 at rest and its whole travel above that.
function triggerParams(rest, full) {
    var r0 = TRIGGER_MEASURE - rest, r1 = TRIGGER_MEASURE - full
    var dz = 0.05 * (r0 - r1)
    return { max: Math.trunc(r0), deadzone: Math.trunc(dz), antideadzone: Math.trunc(0.8 * dz) }
}

// The parameters that make a control report raw values while it's measured.
function measuring(kind, side) {
    var p = {}
    if (kind === "stick") {
        for (var a = 0; a < 2; a++) {
            var n = STICKS[side][a]
            p[n + "_min"] = -AXIS_DEFAULT; p[n + "_center"] = 0; p[n + "_max"] = AXIS_DEFAULT
            p[n + "_deadzone"] = 0; p[n + "_antideadzone"] = 0
        }
    } else {
        var t = TRIGGERS[side][0]
        p[t + "_max"] = TRIGGER_MEASURE; p[t + "_deadzone"] = 0; p[t + "_antideadzone"] = 0
    }
    return p
}

function defaults() {
    var p = {}
    for (var s in STICKS) for (var a = 0; a < 2; a++) {
        var n = STICKS[s][a]
        p[n + "_min"] = -AXIS_DEFAULT; p[n + "_center"] = 0; p[n + "_max"] = AXIS_DEFAULT
        p[n + "_deadzone"] = 0; p[n + "_antideadzone"] = 0
    }
    for (var t in TRIGGERS) {
        var tn = TRIGGERS[t][0]
        p[tn + "_max"] = TRIGGER_DEFAULT; p[tn + "_deadzone"] = 0; p[tn + "_antideadzone"] = 0
    }
    return p
}

// What a measured control's readings give: {params} for the control, from the readings collected step by step.
function result(kind, side, got) {
    var p = {}, k
    if (kind === "stick") {
        var names = STICKS[side]
        var xs = got.rests.map(function (r) { return r[0] }), ys = got.rests.map(function (r) { return r[1] })
        var px = axisParams(xs, got.left, got.right), py = axisParams(ys, got.up, got.down)
        for (k in px) p[names[0] + "_" + k] = px[k]
        for (k in py) p[names[1] + "_" + k] = py[k]
    } else {
        var pt = triggerParams(got.rest, got.full)
        for (k in pt) p[TRIGGERS[side][0] + "_" + k] = pt[k]
    }
    return p
}

// One step of a measurement: is the control where this step wants it? `axes` are rsinput's raw [x, y, z, rx, ry, rz].
function inPlace(kind, side, step, axes, got) {
    if (kind === "stick") {
        var x = axes[STICKS[side][2]], y = axes[STICKS[side][3]]
        if (step === "rest") return Math.abs(x) < AT_REST && Math.abs(y) < AT_REST
        return { right: x, left: -x, down: y, up: -y }[step] > PUSHED
    }
    var v = axes[TRIGGERS[side][1]]
    if (got.rest === undefined) return step === "rest"
    var travel = Math.max(got.peak === undefined ? 0 : got.peak, got.full === undefined ? 0 : got.full) - got.rest
    if (step === "press")
        return v - got.rest > TRIGGER_PRESSED && v >= got.rest + travel - Math.max(2 * STEADY, TRIGGER_BOTTOM * travel)
    return v - got.rest < Math.max(2 * STEADY, TRIGGER_LET_GO * travel)
}

// A trigger's deepest reading so far, kept in the readings while it's measured (what "press" holds at, and what the
// gauge fills against).
function track(kind, side, axes, got) {
    if (kind !== "trigger" || got.rest === undefined) return got
    var v = axes[TRIGGERS[side][1]]
    if (got.peak !== undefined && v <= got.peak) return got
    var g = JSON.parse(JSON.stringify(got))
    g.peak = v
    return g
}

// A trigger's gauge while it's measured (0..1): raw against the measuring max until its rest is known, then its travel
// from rest against the deepest press so far, so pressing all the way fills it whatever the trigger's raw range.
function triggerGauge(axes, side, got) {
    var v = axes[TRIGGERS[side][1]]
    if (got.rest === undefined) return v / TRIGGER_MEASURE
    var travel = Math.max(got.peak === undefined ? 0 : got.peak, got.full === undefined ? 0 : got.full) - got.rest
    return (v - got.rest) / Math.max(travel, TRIGGER_PRESSED)
}

// The values a step watches, and what it records once they've held: returns the updated readings.
function watched(kind, side, axes) {
    return kind === "stick" ? [axes[STICKS[side][2]], axes[STICKS[side][3]]] : [axes[TRIGGERS[side][1]]]
}
function record(kind, step, values, got) {
    var g = JSON.parse(JSON.stringify(got))
    if (kind === "stick") {
        if (step === "rest") (g.rests = g.rests || []).push(values)
        else g[step] = step === "left" || step === "right" ? values[0] : values[1]
    } else if (step === "press") g.full = values[0]
    else if (g.rest === undefined) g.rest = values[0]
    return g
}

// Held steady: {ref, since} -> progress 0..1, and the state to keep. Moving more than STEADY, or leaving the place,
// starts it again.
function hold(state, values, ok, now) {
    var moved = !state.ref || values.some(function (v, i) { return Math.abs(v - state.ref[i]) > STEADY })
    if (!ok) return { state: { ref: null, since: now }, progress: 0 }
    if (moved) return { state: { ref: values, since: now }, progress: 0 }
    return { state: state, progress: Math.min(1, (now - state.since) / HOLD_MS) }
}

// A calibrated reading as a fraction of its range (what games see), for the test views.
function fraction(p, name, value) {
    var top = (p[name + "_max"] || 0) - (p[name + "_antideadzone"] || 0)
    return top > 0 ? Math.max(-1, Math.min(1, value / top)) : 0   // a parameter the driver doesn't have: centred
}

// GPcal's file format, which asgard-gpcal-apply.sh runs the rsinput lines of (CAL-2).
function savedText(p) {
    var lines = ["#!/usr/bin/env bash", "#", "# Stick calibration, from Asgard Home's Settings (GPcal's format)", "#"]
    var names = paramNames()
    for (var i = 0; i < names.length; i++) lines.push("echo " + p[names[i]] + " > /sys/module/rsinput/parameters/" + names[i])
    lines.push("echo 1 > /sys/module/rsinput/parameters/update_params")
    return lines.join("\n") + "\n"
}
