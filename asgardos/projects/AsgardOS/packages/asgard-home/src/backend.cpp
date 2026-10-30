#include "backend.h"

#include <QDateTime>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QRegularExpression>
#include <QSet>
#include <QSysInfo>
#include <QXmlStreamReader>
#include <algorithm>
#include <functional>

#include <cerrno>
#include <cstring>
#include <fcntl.h>
#include <linux/input.h>
#include <linux/uinput.h>
#include <netinet/in.h>
#include <sys/ioctl.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <unistd.h>

static const char *PLAYLOG = "/storage/.config/thor/playtime.jsonl";  // shared with Thor Panel (playlog.py)
static const QStringList IMAGE_EXT = {"png", "jpg", "jpeg", "webp"};

Backend::Backend(const QProcessEnvironment &gameEnv, QObject *parent)
    : QObject(parent), m_root(qEnvironmentVariable("ASGARD_ROOT")), m_gameEnv(gameEnv)
{
    scan();
    readPlaytime();
    readStatus();
    topScreenOn();
    if (QFile::exists("/usr/bin/runemu.sh") && !qEnvironmentVariableIsSet("ASGARD_SHOT")) {
        // A keyboard of our own for emulator hotkeys (made now, so sway knows it before the first press).
        m_keys = ::open("/dev/uinput", O_WRONLY | O_NONBLOCK | O_CLOEXEC);
        if (m_keys >= 0) {
            ioctl(m_keys, UI_SET_EVBIT, EV_KEY);
            for (int k : {KEY_LEFTALT, KEY_LEFTCTRL, KEY_LEFTSHIFT, KEY_F4, KEY_F6, KEY_F7, KEY_F9, KEY_F10,
                          KEY_F1, KEY_S, KEY_L, KEY_P, KEY_M, KEY_U, KEY_V, KEY_ESC})
                ioctl(m_keys, UI_SET_KEYBIT, k);
            uinput_setup us{};
            us.id.bustype = BUS_VIRTUAL;
            strcpy(us.name, "asgard-home-keys");
            if (ioctl(m_keys, UI_DEV_SETUP, &us) < 0 || ioctl(m_keys, UI_DEV_CREATE) < 0) {
                ::close(m_keys);
                m_keys = -1;
            }
        }
        // Command FIFO. Opened read-write so it never reads EOF when a writer closes.
        mkfifo("/run/asgard-home.cmd", 0600);
        m_cmd = ::open("/run/asgard-home.cmd", O_RDWR | O_NONBLOCK | O_CLOEXEC);
        if (m_cmd >= 0) {
            auto *n = new QSocketNotifier(m_cmd, QSocketNotifier::Read, this);
            connect(n, &QSocketNotifier::activated, this, [this] {
                char buf[256];
                const ssize_t len = ::read(m_cmd, buf, sizeof buf);
                if (len > 0)
                    for (const QString &c : QString::fromUtf8(buf, len).split('\n', Qt::SkipEmptyParts))
                        command(c.trimmed());
            });
        }
    }
    // ponytail: polled, and often: QTimer's clock stops in sleep, so at 30 s the bar kept the pre-sleep battery
    // level for up to 30 s after a wake (48 % vs the panel's 81 %, 2026-10-10). Two sysfs reads every 5 s.
    auto *t = new QTimer(this);
    connect(t, &QTimer::timeout, this, &Backend::readStatus);
    t->start(5000);
}

QString Backend::hostname() const { return QSysInfo::machineHostName(); }

static QString text(QXmlStreamReader &x) { return x.readElementText(QXmlStreamReader::IncludeChildElements).trimmed(); }

// <game><path>./x.nds</path><name/><desc/><developer/><releasedate>20050101T000000</releasedate><genre/></game>
static QHash<QString, QVariantMap> readGamelist(const QString &file)
{
    QHash<QString, QVariantMap> out;
    QFile f(file);
    if (!f.open(QIODevice::ReadOnly))
        return out;
    QXmlStreamReader x(&f);
    QVariantMap g;
    while (!x.atEnd()) {
        x.readNext();
        if (x.isStartElement() && x.name() == u"game")
            g.clear();
        else if (x.isStartElement() && g.size() < 16 && x.name() != u"gameList")
            g[x.name().toString()] = text(x);
        else if (x.isEndElement() && x.name() == u"game")
            out[QDir::cleanPath(g.value("path").toString())] = g;
    }
    return out;
}

static QString media(const QString &dir, const QString &stem)
{
    for (const QString &ext : IMAGE_EXT)
        if (QFile::exists(dir + "/" + stem + "." + ext))
            return QUrl::fromLocalFile(dir + "/" + stem + "." + ext).toString();
    return {};
}

void Backend::rescan()
{
    m_systems.clear();
    m_games.clear();
    m_byPath.clear();
    scan();
    readPlaytime();
}

void Backend::scan()
{
    QFile f(path("/usr/config/emulationstation/es_systems.cfg"));
    if (!f.open(QIODevice::ReadOnly))
        return;
    QXmlStreamReader x(&f);
    QVariantMap sys;
    while (!x.atEnd()) {
        x.readNext();
        if (x.isStartElement() && x.name() == u"system") {
            sys.clear();
        } else if (x.isStartElement() && (x.name() == u"name" || x.name() == u"fullname" || x.name() == u"path" ||
                                          x.name() == u"extension" || x.name() == u"manufacturer" ||
                                          x.name() == u"release" || x.name() == u"theme")) {
            sys[x.name().toString()] = text(x);
        } else if (x.isStartElement() && x.name() == u"emulator") {
            const QString emu = x.attributes().value("name").toString();
            QStringList cores;
            while (!(x.isEndElement() && x.name() == u"emulator") && !x.atEnd()) {
                x.readNext();
                if (x.isStartElement() && x.name() == u"core") {
                    const bool def = x.attributes().value("default") == u"true";
                    const QString core = text(x);
                    cores << core;
                    if (def) {
                        sys["emulator"] = emu;
                        sys["core"] = core;
                    }
                }
            }
            QVariantList emus = sys["emulators"].toList();
            emus << QVariantMap{{"name", emu}, {"cores", cores}};
            sys["emulators"] = emus;
        } else if (x.isEndElement() && x.name() == u"system" && sys.contains("emulator")) {
            const QString name = sys["name"].toString(), dir = path(sys["path"].toString());
            // ROCKNIX's Music Player system holds Asgard Music and other apps (Firefox): shown as Tools, with the
            // theme's Tools art (its music logo reads "Music Player").
            if (name == "music") {
                sys["fullname"] = "Tools";
                sys["theme"] = "tools";
            }
            QSet<QString> exts;
            for (const QString &e : sys["extension"].toString().split(' ', Qt::SkipEmptyParts))
                exts << e.toLower();
            auto gl = readGamelist(path("/storage/ES-DE/gamelists/" + name + "/gamelist.xml"));
            const QString mediaDir = path("/storage/ES-DE/downloaded_media/" + name);
            // Entries Asgard ships (Tools > Firefox) bring their own art and metadata; the user's ES-DE files win.
            const QString builtin = path("/usr/share/asgard-home/media/" + name);
            for (const auto &[p, meta] : readGamelist(builtin + "/gamelist.xml").asKeyValueRange())
                if (!gl.contains(p))
                    gl[p] = meta;
            const auto mediaOf = [&](const QString &kind, const QString &stem) {
                const QString m = media(mediaDir + "/" + kind, stem);
                return m.isEmpty() ? media(builtin + "/" + kind, stem) : m;
            };
            QVariantList games;
            // ROMs in the system dir and one level of subfolders (multi-disc / per-game folders).
            QStringList files;
            for (const QFileInfo &fi : QDir(dir).entryInfoList(QDir::Files | QDir::Dirs | QDir::NoDotAndDotDot)) {
                if (fi.isDir())
                    for (const QFileInfo &sub : QDir(fi.filePath()).entryInfoList(QDir::Files))
                        files << sub.filePath();
                else
                    files << fi.filePath();
            }
            for (const QString &file : files) {
                const QFileInfo fi(file);
                if (!exts.contains("." + fi.suffix().toLower()))
                    continue;
                // Switch updates and DLC sit next to their game (Eden loads them from there): not games themselves.
                // Title IDs: base ends in 000, update in 800, DLC anything else.
                static const QRegularExpression switchExtra("\\[0100[0-9a-f]{9}(?!000\\])[0-9a-f]{3}\\]|\\[dlc",
                                                            QRegularExpression::CaseInsensitiveOption);
                if (name == "switch" && switchExtra.match(fi.fileName()).hasMatch())
                    continue;
                // 3DS DLC and update installers (.cia) get installed into Azahar's NAND/SD: not games themselves.
                static const QRegularExpression ctrExtra("\\b(DLC|Update)\\b", QRegularExpression::CaseInsensitiveOption);
                if (name == "3ds" && fi.suffix().compare("cia", Qt::CaseInsensitive) == 0 &&
                    ctrExtra.match(fi.fileName()).hasMatch())
                    continue;
                // The music system is one entry, Asgard Music Player (ROCKNIX's "Start Music Player.sh"): its
                // playlists are picked inside Asgard Music, which reads them from this same folder.
                if (name == "music" && fi.suffix().compare("m3u", Qt::CaseInsensitive) == 0)
                    continue;
                const QString rel = QDir(dir).relativeFilePath(file);
                const QString stem = rel.left(rel.size() - fi.suffix().size() - 1);
                const QVariantMap meta = gl.value(QDir::cleanPath("./" + rel));
                QVariantMap g;
                g["path"] = file.mid(m_root.size());  // device path, without the dev fixture prefix
                g["sys"] = name;
                g["stem"] = stem;  // media file name (asgard-scrape.py writes <mediaDir>/<kind>/<stem>.png)
                g["sysName"] = sys["fullname"];
                g["name"] = meta.value("name", fi.completeBaseName());
                g["desc"] = meta.value("desc");
                g["developer"] = meta.value("developer");
                g["year"] = meta.value("releasedate").toString().left(4);
                g["genre"] = meta.value("genre");
                g["cover"] = mediaOf("covers", stem);
                g["shot"] = mediaOf("screenshots", stem);
                g["marquee"] = mediaOf("marquees", stem);
                g["core"] = sys["core"];
                g["emulator"] = sys["emulator"];
                games << g;
                m_byPath[g["path"].toString()] = g;
            }
            // Systems without games are listed too (an empty grid when opened), so every emulator is visible.
            std::sort(games.begin(), games.end(), [](const QVariant &a, const QVariant &b) {
                return a.toMap()["name"].toString().compare(b.toMap()["name"].toString(), Qt::CaseInsensitive) < 0;
            });
            sys["count"] = games.size();
            // Backdrop: the first game that has a screenshot (the first one alphabetically often has none: 3DS).
            for (const QVariant &g : games)
                if (!g.toMap()["shot"].toString().isEmpty()) {
                    sys["cover"] = g.toMap()["shot"];
                    break;
                }
            // ROCKNIX's Steam system (the .desktop files in ~/.local/share/applications) holds Steam and other PC
            // apps (Gen1 Recomp...): shown as PC, with the theme's PC art. Steam itself stays an entry inside.
            if (name == "steam") {
                sys["fullname"] = "PC";
                sys["theme"] = "pc";
            }
            // System artwork + white logo from ROCKNIX's Art Book Next theme (es-theme-art-book-next), by <theme>.
            const QString art = path("/usr/share/themes/es-theme-art-book-next/_inc/systems/");
            const QString theme = sys.value("theme", name).toString();
            if (QFile::exists(art + "artwork-default/" + theme + ".png"))
                sys["art"] = QUrl::fromLocalFile(art + "artwork-default/" + theme + ".png").toString();
            if (QFile::exists(art + "logos/" + theme + ".svg"))
                sys["logo"] = QUrl::fromLocalFile(art + "logos/" + theme + ".svg").toString();
            m_games[name] = games;
            m_systems << sys;
        }
    }
    emit libraryChanged();
}

// playtime.jsonl: one {"rom", "sys", "start", "secs"} per session (playlog.py's format).
void Backend::readPlaytime()
{
    QFile f(path(PLAYLOG));
    QHash<QString, QPair<double, double>> stats;  // rom -> (total secs, last start)
    if (f.open(QIODevice::ReadOnly))
        while (!f.atEnd()) {
            const QJsonObject o = QJsonDocument::fromJson(f.readLine()).object();
            auto &s = stats[o["rom"].toString()];
            s.first += o["secs"].toDouble();
            s.second = std::max(s.second, o["start"].toDouble());
        }
    QList<QVariantMap> recent;
    for (auto it = stats.cbegin(); it != stats.cend(); ++it) {
        if (!m_byPath.contains(it.key()))
            continue;
        QVariantMap g = m_byPath[it.key()];
        g["playtime"] = it->first;
        g["lastPlayed"] = it->second;
        m_byPath[it.key()] = g;
        recent << g;
    }
    std::sort(recent.begin(), recent.end(), [](const QVariantMap &a, const QVariantMap &b) {
        return a["lastPlayed"].toDouble() > b["lastPlayed"].toDouble();
    });
    m_recent.clear();
    for (const QVariantMap &g : recent)
        m_recent << g;
    qInfo("library: %lld systems, %lld games, %lld recently played (of %lld in the play log)",
          qsizetype(m_systems.size()), qsizetype(m_byPath.size()), qsizetype(m_recent.size()), qsizetype(stats.size()));
    emit libraryChanged();
}

void Backend::readStatus()
{
    QFile cap("/sys/class/power_supply/battery/capacity"), st("/sys/class/power_supply/battery/status");
    const int battery = cap.open(QIODevice::ReadOnly) ? cap.readAll().trimmed().toInt() : -1;
    const bool charging = st.open(QIODevice::ReadOnly) && st.readAll().trimmed() == "Charging";
    // Charger in/out chime. The charger's own online flag: the battery reads "Not charging" at the charge limit.
    QFile usb("/sys/class/power_supply/qcom-battmgr-usb/online");
    const int plugged = usb.open(QIODevice::ReadOnly) ? usb.readAll().trimmed().toInt() : -1;
    if (m_plugged >= 0 && plugged >= 0 && plugged != m_plugged && getSetting("asgard.charger_sounds", "1") == "1")
        play(plugged ? "charger-in" : "charger-out");
    m_plugged = plugged;
    if (battery != m_battery || charging != m_charging) {
        m_battery = battery;
        m_charging = charging;
        emit statusChanged();
    }
    // The game's frame rate, for the pause menu: sampled while it runs in front, restarted after a pause.
    if (playing() && !m_gameMenu)
        sampleFps();
    else
        m_framesAt = 0;
}

// Frames per window from sway (sway-100.02's "frames": buffer commits, subsurfaces included); Home's own skipped.
static QHash<qint64, qint64> windowFrames()
{
    QProcess p;
    p.start("swaymsg", {"-t", "get_tree", "-r"});
    p.waitForFinished(1000);
    QHash<qint64, qint64> out;
    std::function<void(const QJsonObject &)> walk = [&](const QJsonObject &n) {
        if (n.contains("frames") && n["app_id"].toString() != "asgard-home")
            out[n["id"].toInteger()] = n["frames"].toInteger();
        for (const char *k : {"nodes", "floating_nodes"})
            for (const QJsonValue &v : n[k].toArray())
                walk(v.toObject());
    };
    walk(QJsonDocument::fromJson(p.readAllStandardOutput()).object());
    return out;
}

// m_fps = the busiest game window's frames per second since the previous sample (-1 until there are two). Under a
// second apart is too short to measure: the last rate stays.
void Backend::sampleFps()
{
    const qint64 now = QDateTime::currentMSecsSinceEpoch();
    if (m_framesAt && now - m_framesAt < 1000)
        return;
    const QHash<qint64, qint64> frames = windowFrames();
    m_fps = -1;
    if (m_framesAt) {
        qint64 best = 0;
        for (auto it = frames.cbegin(); it != frames.cend(); ++it)
            best = std::max(best, it.value() - m_frames.value(it.key(), it.value()));
        m_fps = int(best * 1000.0 / (now - m_framesAt) + 0.5);
    }
    m_frames = frames;
    m_framesAt = now;
}

// The stick LEDs follow the screens: "poweroff" darkens them without touching the saved led.color, and back on
// re-applies led.color (rgb / battery / off). The battery mode's service would relight them, so it stops too.
static void sticksLeds(bool on)
{
    QProcess::startDetached("/bin/sh", {"-c", on ? ". /etc/profile; ledcontrol \"$(get_setting led.color)\""
                                                 : "systemctl stop batteryledstatus.service; ledcontrol poweroff"});
}

// The top panel can be left off when the frontend (re)starts or comes back after a game/tool while the screens
// were off: ROCKNIX's "Bottom" sway rule powers the bottom panel back on when our bottom window maps, nothing
// powered the top one, and the top screen stayed dark. The frontend owns both panels while it is shown.
void Backend::topScreenOn()
{
    if (m_screensOff)
        sticksLeds(true);
    m_screensOff = false;
    QProcess::startDetached("swaymsg", {"output DSI-2 power on"});
    emit screensOffChanged();
}

// Both OLED panels off (pixels dark, the frontend keeps running and reading the pad) or back on, stick LEDs too.
void Backend::setScreensOff(bool off)
{
    if (off == m_screensOff)
        return;
    m_screensOff = off;
    const QString power = off ? "off" : "on";
    QProcess::startDetached("swaymsg", {QString("output DSI-2 power %1, output DSI-1 power %1").arg(power)});
    sticksLeds(!off);
    emit screensOffChanged();
}

// A journal snapshot at each game's launch and exit (in the background: it never delays the game), so a freeze
// leaves the boot's log up to then (asgard-journal-snap.sh, filed by asgard-lastboot.sh).
#define SNAP_JOURNAL "(/usr/share/asgard/asgard-journal-snap.sh >/dev/null 2>&1 &); "

void Backend::launch(const QVariantMap &game)
{
    if (m_game)
        return;
    m_launched = game;
    QFile::remove("/tmp/asgard-save-log");   // Quit and save log's marker, for this launch only
    const QString rom = game["path"].toString(), sys = game["sys"].toString();
    // The emulator/core chosen for this game, else for its system, else ROCKNIX's default (what ROCKNIX ES did).
    const QString file = QFileInfo(rom).fileName();
    const QString emulator = setting(sys, file, "emulator", game["emulator"].toString());
    const QString core = setting(sys, file, "core", game["core"].toString());
    if (!QFile::exists("/usr/bin/runemu.sh")) {  // desktop
        qInfo("launch %s (%s) with %s/%s", qPrintable(rom), qPrintable(sys), qPrintable(emulator), qPrintable(core));
        return;
    }
    // A .desktop entry that isn't a Steam link (a PC app in the PC system): its own command, not Steam.
    if (rom.endsWith(".desktop")) {
        QFile desk(rom);
        QString exec, kill;   // X-Asgard-Kill: the process Home's Quit stops (default: the command's own name)
        if (desk.open(QIODevice::ReadOnly))
            for (const QString &line : QString::fromUtf8(desk.readAll()).split('\n')) {
                if (line.startsWith("Exec=") && exec.isEmpty())
                    exec = line.mid(5).trimmed();
                if (line.startsWith("X-Asgard-Kill="))
                    kill = line.mid(14).trimmed();
            }
        if (!exec.isEmpty() && !exec.startsWith("steam")) {
            if (kill.isEmpty())
                kill = QFileInfo(exec.section(' ', 0, 0)).fileName();
            // ROCKNIX's kill-hotkey target (runemu.sh writes it for emulators): Home's in-game menu reads it.
            // Its output goes to exec.log, as runemu.sh's launches do, and a failed run (or Quit and save log) keeps
            // it in /storage like theirs: 137/143 are Home's quit. The game's per-game/per-system profile (cores, caps,
            // fan, EQ, sleep mode) around it, as runemu.sh does for emulators: else the menu's profile stays on.
            run(". /etc/profile; set_kill set \"$3\"; python3 /usr/share/asgard/playlog.py start \"$1\" \"$2\" 2>/dev/null; " SNAP_JOURNAL
                "/usr/share/asgard/asgard-perf-profile.sh apply \"$2\" \"${1##*/}\" >/dev/null 2>&1; "
                "echo \"Run log - $(date): $1\" >/var/log/exec.log; { " + exec + "; } >>/var/log/exec.log 2>&1; rc=$?; "
                "/usr/share/asgard/asgard-perf-profile.sh restore >/dev/null 2>&1; "
                "set_kill stop; python3 /usr/share/asgard/playlog.py stop 2>/dev/null; " SNAP_JOURNAL "case $rc in 0|137|143) [ -e /tmp/asgard-save-log ] || exit $rc ;; esac; "
                "/usr/share/asgard/asgard-crashlog.sh \"$1\" \"$2\" $rc; exit $rc",
                {rom, sys, kill},
                m_gameEnv);
            return;
        }
    }
    // playlog.py around ROCKNIX's runemu.sh (per-game options, governors, hotkeys).
    run("python3 /usr/share/asgard/playlog.py start \"$1\" \"$2\" \"$4\" \"$3\" 2>/dev/null; " SNAP_JOURNAL
        "/usr/bin/runemu.sh \"$1\" -P\"$2\" --core=\"$3\" --emulator=\"$4\" --controllers=\"\"; rc=$?; "
        "python3 /usr/share/asgard/playlog.py stop 2>/dev/null; " SNAP_JOURNAL "exit $rc",
        {rom, sys, core, emulator}, m_gameEnv);
}

void Backend::openSettings(const QVariantMap &game, const QString &page)
{
    if (m_game)
        return;
    // Thor Settings' Game Options opens on the highlighted game.
    QFile sel("/tmp/thor-selected-game");
    if (!game.isEmpty() && sel.open(QIODevice::WriteOnly))
        sel.write((game["sys"].toString() + "\t" + game["path"].toString() + "\n").toUtf8());
    if (!QFile::exists("/usr/share/asgard/thor_settings.py")) {  // desktop
        qInfo("settings page %s", qPrintable(page));
        return;
    }
    QProcessEnvironment env = m_gameEnv;
    env.insert("SDL_GAMECONTROLLERCONFIG", "");  // sdlui expects the pad's positional mapping
    run("exec python3 /usr/share/asgard/thor_settings.py --page \"$1\"", {page.isEmpty() ? "main" : page}, env);
}

void Backend::runTool(const QString &script, const QStringList &args)
{
    if (m_game)
        return;
    m_launched.clear();
    if (!QFile::exists(script)) {  // desktop
        qInfo("tool %s", qPrintable(script));
        return;
    }
    run("exec \"$@\"", QStringList{script} + args, m_gameEnv);
}

// Run a game or tool in place of the frontend: our windows hide (playing), the pad is ignored until it exits.
void Backend::run(const QString &script, const QStringList &args, const QProcessEnvironment &env)
{
    m_game = new QProcess(this);
    m_game->setProcessEnvironment(env);
    m_game->setProcessChannelMode(QProcess::ForwardedChannels);
    connect(m_game, &QProcess::finished, this, [this] {
        m_game->deleteLater();
        m_game = nullptr;
        m_background = false;
        QFile::remove("/run/asgard-bg.json");   // asgard-background.py's state: no game in the background now
        setGameMenu(false);
        // ROCKNIX's Steam/Heroic launchers set seat1 as a fallback seat and only undo it on a clean exit. Left on,
        // every touch reaches us on seat0 and seat1, and the phantom second press steals taps (the power button).
        QProcess::startDetached("swaymsg", {"seat seat1 fallback false"});
        readPlaytime();
        topScreenOn();
        emit playingChanged();
    });
    m_game->start("/bin/bash", QStringList{"-c",
        // Our windows are hidden by now, but sway's focus may still be on the bottom screen (our bottom window
        // maps last), and a new window opens on the focused output: focus the top screen, or it lands on the
        // bottom panel. The bottom panel goes dark a few seconds later unless the program opened a window there
        // (not at once: a dual-screen game would power it straight back on, two modesets that can hang the top panel).
        "swaymsg 'focus output DSI-2' >/dev/null 2>&1; (/usr/share/asgard/thor-bottom-idle-off.sh 3 >/dev/null 2>&1 &); " + script,
        "run"} + args);
    emit playingChanged();
}

// --- in-game menu ----------------------------------------------------------------------------------------------------

void Backend::setGameMenu(bool on)
{
    if (on == m_gameMenu)
        return;
    m_gameMenu = on;
    // A tool's touch keyboard on the bottom screen (Firefox, start_firefox.sh) is a layer above the menu: hide it
    // while the menu is open (wvkbd: SIGUSR1 hides, SIGUSR2 shows).
    QProcess::startDetached("sh", {"-c", QString("kill -%1 $(cat /run/asgard-osk.pid) 2>/dev/null").arg(on ? "USR1" : "USR2")});
    emit gameMenuChanged();
}

void Backend::command(const QString &cmd)
{
    if (cmd.startsWith("osd ")) {          // "osd Volume 60" from asgard-osd (input_sense)
        const QStringList p = cmd.split(' ', Qt::SkipEmptyParts);
        if (p.size() == 3)
            emit osd(p[1], p[2].toInt());
        return;
    }
    qInfo("command: %s", qPrintable(cmd));
    if (cmd == "rescan") {   // 090-asgard-tuning, after it adds Tools entries: Home may have scanned before them
        rescan();
        return;
    }
    if (cmd == "menu" && playing()) {
        const bool open = !m_gameMenu;
        if (!open)
            setGameMenu(false);  // Home again: close, then unpause below (keys go to the game)
        else
            sampleFps();         // the rate up to now, while the game still runs
        togglePause();
        if (open)
            setGameMenu(true);
    }
    // Around a sleep (sleep.d/asgard-game-pause): the game paused with its own pause, so on wake it carries on
    // from there instead of replaying the whole sleep (emulators reset their timing on unpause; a clock that kept
    // counting through the sleep otherwise has them race through every missed frame, frozen for minutes). Not a
    // game already paused (the in-game menu) or frozen in the background, and only ours to unpause.
    if (cmd == "sleep" && playing() && !m_gameMenu && !m_sleepPaused)
        m_sleepPaused = togglePause();
    if (cmd == "wake" && m_sleepPaused) {
        m_sleepPaused = false;
        if (playing())
            togglePause();
    }
}

bool Backend::togglePause()
{
    const QStringList names = runningGame();
    if (names.contains("azahar") || names.contains("eden")) {
        gameKeys("F4");      // pause / unpause (Azahar and Eden keep running when they lose focus)
        return true;
    }
    if (names.contains("retroarch")) {
        retroarch("PAUSE_TOGGLE");
        return true;
    }
    return false;
}

QStringList Backend::runningGame() const
{
    // ROCKNIX's kill-hotkey target, written by runemu.sh for every emulator it starts.
    QFile f("/tmp/.process-kill-data");
    QStringList names;
    if (f.open(QIODevice::ReadOnly))
        for (const QString &w : QString::fromUtf8(f.readAll()).split(QRegularExpression("\\s+"), Qt::SkipEmptyParts))
            if (!w.startsWith('-') && w != "emulationstation")
                names << w;
    return names;
}

void Backend::gameKeys(const QString &combo)
{
    const QStringList names = runningGame();
    if (m_keys < 0 || names.isEmpty())
        return;
    // Keys go to the focused window: hand focus back to the game first (any of its windows but a GamePad one: Wind
    // Waker HD's settings open in its TV window; Azahar's shortcuts are application-wide).
    QProcess::execute("/bin/sh", {"-c", "swaymsg \"[pid=$(pidof -s " + names.first() + ") title=\\\"^(?!GamePad)\\\"] focus\" >/dev/null 2>&1"});
    static const QHash<QString, int> codes = {{"Alt", KEY_LEFTALT}, {"Ctrl", KEY_LEFTCTRL}, {"Shift", KEY_LEFTSHIFT},
        {"F1", KEY_F1}, {"F4", KEY_F4}, {"F6", KEY_F6}, {"F7", KEY_F7}, {"F9", KEY_F9}, {"F10", KEY_F10}, {"S", KEY_S}, {"L", KEY_L},
        {"P", KEY_P}, {"M", KEY_M}, {"U", KEY_U}, {"V", KEY_V}, {"Esc", KEY_ESC}};
    QList<int> keys;
    for (const QString &k : combo.split('+'))
        keys << codes.value(k, 0);
    if (keys.contains(0))
        return;
    auto emitKey = [this](int code, int value) {
        input_event ev[2] = {};
        ev[0].type = EV_KEY; ev[0].code = code; ev[0].value = value;
        ev[1].type = EV_SYN; ev[1].code = SYN_REPORT;
        (void)!::write(m_keys, ev, sizeof ev);
    };
    for (int k : keys) emitKey(k, 1);
    usleep(30000);
    for (auto it = keys.rbegin(); it != keys.rend(); ++it) emitKey(*it, 0);
}

// "Back to Home" from the in-game menu: the game's windows go to sway's scratchpad and its processes freeze
// (asgard-background.py), and our windows come back (playing() is false) until resumeGame() or the game is quit.
void Backend::toBackground()
{
    const QStringList names = runningGame();
    if (!m_game || m_background || m_launched.isEmpty() || names.isEmpty())
        return;
    setGameMenu(false);
    QProcess::execute("python3", QStringList{"/usr/share/asgard/asgard-background.py", "hide"} + names);
    m_background = true;
    topScreenOn();
    emit playingChanged();
}

void Backend::resumeGame()
{
    if (!m_background)
        return;
    m_background = false;
    emit playingChanged();   // our windows hide
    QProcess::startDetached("python3", QStringList{"/usr/share/asgard/asgard-background.py", "show"} + runningGame());
}

// RetroArch's network command port (runemu.sh enables it on dual-screen devices). Fire and forget: PAUSE_TOGGLE,
// MENU_TOGGLE, SAVE_STATE, LOAD_STATE, SCREENSHOT, RESET.
void Backend::retroarch(const QString &cmd)
{
    const int s = ::socket(AF_INET, SOCK_DGRAM, 0);
    if (s < 0)
        return;
    sockaddr_in a = {};
    a.sin_family = AF_INET;
    a.sin_port = htons(55355);
    a.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
    const QByteArray b = cmd.toUtf8();
    ::sendto(s, b.constData(), b.size(), 0, reinterpret_cast<sockaddr *>(&a), sizeof a);
    ::close(s);
}

// Press buttons on InputPlumber's virtual pad. SendButtonChord skips the profile, so Guide reaches Steam as Home even
// while steam-pad-profile.py maps the physical Home to F20.
void Backend::padChord(const QStringList &buttons)
{
    QProcess::startDetached("busctl", QStringList{"call", "org.shadowblip.InputPlumber",
        "/org/shadowblip/InputPlumber/CompositeDevice0", "org.shadowblip.Input.CompositeDevice", "SendButtonChord",
        "as", QString::number(buttons.size())} + buttons);
}

void Backend::quitGame(bool saveLog)
{
    const QStringList names = runningGame();
    setGameMenu(false);
    if (names.isEmpty())
        return;
    // The signal ROCKNIX's quit hotkey uses for this emulator (runemu.sh writes it, e.g. "-9 azahar": Azahar asks to
    // confirm on SIGTERM, so a polite quit sat there until the fallback). Otherwise ask nicely, then insist.
    QFile f("/tmp/.process-kill-data");
    QString sig = "-TERM";
    if (f.open(QIODevice::ReadOnly))
        for (const QString &w : QString::fromUtf8(f.readAll()).split(QRegularExpression("\\s+"), Qt::SkipEmptyParts))
            if (w.startsWith('-'))
                sig = w;
    const QString n = names.join(' ');
    QString log;
    if (saveLog) {
        // Quit and save log (a hung game): what each thread waits on (a GPU hang sits in a driver call) and the
        // kernel's last messages go into exec.log, and the marker has the launcher keep this launch's log
        // (asgard-crashlog.sh) however it ends. SIGABRT leaves a core dump, whose backtrace shows where it hung;
        // writing it takes a while, and a -KILL would cut it short, so wait up to 30 s for that.
        sig = "-ABRT";
        log = "touch /tmp/asgard-save-log; { echo; echo \"=== Quit and save log: $(date) ===\"; for p in $(pidof " + n + "); do "
              "for t in /proc/$p/task/*; do echo \"$t $(cat $t/comm) wchan=$(cat $t/wchan)\"; cat $t/stack; done; done; "
              "echo '=== dmesg ==='; dmesg | tail -60; } >>/var/log/exec.log 2>&1; ";
    }
    // A game in the background is frozen (SIGSTOP): it would only act on the quit signal once continued.
    shell(log + (m_background ? "killall -CONT " + n + "; " : QString()) + "killall " + sig + " " + n + "; for i in $(seq "
          + (saveLog ? "150" : "20") + "); do pidof " + n + " >/dev/null || exit 0; sleep .2; done; killall -KILL " + n);
}

// --- settings (system.cfg, ROCKNIX's semantics: one key=value per line, the last one wins) -----------------------

QString Backend::getSetting(const QString &key, const QString &fallback) const
{
    QFile f(path("/storage/.config/system/configs/system.cfg"));
    QString value;
    if (f.open(QIODevice::ReadOnly))
        for (const QByteArray &line : f.readAll().split('\n'))
            if (line.startsWith(key.toUtf8() + "="))
                value = QString::fromUtf8(line.mid(key.toUtf8().size() + 1));
    return value.isEmpty() ? fallback : value;
}

// Like ROCKNIX's set_setting: drop the key's lines, append key=value ("" or "default" just removes it).
void Backend::setSetting(const QString &key, const QString &value)
{
    QFile f(path("/storage/.config/system/configs/system.cfg"));
    QByteArrayList keep;
    if (f.open(QIODevice::ReadOnly)) {
        for (const QByteArray &line : f.readAll().split('\n'))
            if (!line.isEmpty() && !line.startsWith(key.toUtf8() + "="))
                keep << line;
        f.close();
    }
    if (!value.isEmpty() && value != "default")
        keep << (key + "=" + value).toUtf8();
    QFile tmp(f.fileName() + ".asgard-tmp");
    if (tmp.open(QIODevice::WriteOnly)) {
        tmp.write(keep.join('\n') + '\n');
        tmp.close();
        QFile::remove(f.fileName());
        tmp.rename(f.fileName());
    }
    emit settingsChanged();
}

QVariantMap Backend::osInfo() const
{
    QVariantMap info;
    QFile f("/etc/os-release");
    if (f.open(QIODevice::ReadOnly))
        for (const QByteArray &line : f.readAll().split('\n')) {
            const int eq = line.indexOf('=');
            if (eq > 0)
                info[QString::fromUtf8(line.left(eq))] = QString::fromUtf8(line.mid(eq + 1)).remove('"');
        }
    return info;
}

QVariantList Backend::emulators(const QString &system) const
{
    for (const QVariant &s : m_systems)
        if (s.toMap()["name"] == system)
            return s.toMap()["emulators"].toList();
    return {};
}

// Settings actions (volume, brightness, services...): a shell command in the frontend's environment.
void Backend::shell(const QString &command)
{
    if (!QFile::exists("/usr/bin/runemu.sh")) {  // desktop
        qInfo("shell: %s", qPrintable(command));
        return;
    }
    QProcess::startDetached("/bin/sh", {"-c", command});
}

void Backend::sound(const QString &name)
{
    // ponytail: reads system.cfg per sound; cache the two keys if that ever shows up in a profile
    if (getSetting("asgard.sounds", "1") == "1")
        play(name);
}

void Backend::play(const QString &name)
{
    if (qEnvironmentVariableIsSet("ASGARD_SHOT"))
        return;
    // A detached pw-play per sound: QSoundEffect's audio thread once spun at 100 % at startup while holding a lock
    // the UI thread waited on, freezing Home (2026-10-12). A stuck player now only costs its own process.
    QProcess::startDetached("pw-play", {"--volume=" + QString::number(getSetting("asgard.sounds_volume", "50").toInt() / 100.0),
        qEnvironmentVariable("ASGARD_HOME_QML", "/usr/share/asgard-home/qml") + "/sounds/" + name + ".wav"});
}

void Backend::exec(const QString &command, const QJSValue &done)
{
    auto *p = new QProcess(this);
    p->setProcessChannelMode(QProcess::MergedChannels);
    connect(p, &QProcess::finished, this, [p, done] {
        QJSValue cb = done;
        if (cb.isCallable())
            cb.call({QString::fromUtf8(p->readAll())});
        p->deleteLater();
    });
    if (!QFile::exists("/usr/bin/runemu.sh")) {  // desktop: log it, answer with nothing
        qInfo("exec: %s", qPrintable(command));
        p->start("/bin/true");
        return;
    }
    p->start("/bin/sh", {"-c", command});
}

// ROCKNIX's get_setting lookup: <sys>["<file>"].<key>, then <sys>.<key>, then global.<key>, else fallback.
QString Backend::setting(const QString &sys, const QString &file, const QString &key, const QString &fallback) const
{
    QFile f(path("/storage/.config/system/configs/system.cfg"));
    QHash<QString, QString> cfg;
    if (f.open(QIODevice::ReadOnly))
        for (const QByteArray &line : f.readAll().split('\n')) {
            const int eq = line.indexOf('=');
            if (eq > 0)
                cfg.insert(QString::fromUtf8(line.left(eq)), QString::fromUtf8(line.mid(eq + 1)));
        }
    for (const QString &k : {sys + "[\"" + file + "\"]." + key, sys + "." + key, "global." + key})
        if (!cfg.value(k).isEmpty())
            return cfg.value(k);
    return fallback;
}

QVariantMap Backend::playStats(const QString &path) const
{
    const QVariantMap g = m_byPath.value(path);
    return {{"playtime", g.value("playtime", 0)}, {"lastPlayed", g.value("lastPlayed", 0)}};
}

// --- Gamepad --------------------------------------------------------------------------------------------------------

static const char *PAD_NAME = "Sony Interactive Entertainment DualSense Wireless Controller";

Gamepad::Gamepad(bool disabled, bool grab, QObject *parent) : QObject(parent), m_grab(grab)
{
    if (disabled)
        return;
    m_repeat.setInterval(90);
    connect(&m_repeat, &QTimer::timeout, this, [this] {
        m_repeat.setInterval(90);
        emit pressed(m_held);
    });
    // InputPlumber creates the virtual pad a few seconds into boot and re-creates it whenever it restarts
    // (stick calibration does), so (re)open it until it's there.
    m_retry.setInterval(500);
    connect(&m_retry, &QTimer::timeout, this, &Gamepad::open);
    open();
}

void Gamepad::open()
{
    // /proc/bus/input/devices: find the event node of the exact pad name (not its Motion/Touchpad siblings).
    QFile f("/proc/bus/input/devices");
    QString name;
    if (f.open(QIODevice::ReadOnly))
        for (const QString &line : QString::fromUtf8(f.readAll()).split('\n')) {
            if (line.startsWith("N: Name="))
                name = line.mid(9).chopped(1);
            else if (line.startsWith("H: Handlers=") && name == PAD_NAME && m_fd < 0)
                for (const QString &h : line.mid(12).split(' '))
                    if (h.startsWith("event"))
                        m_fd = ::open(qPrintable("/dev/input/" + h), O_RDONLY | O_NONBLOCK | O_CLOEXEC);
        }
    if (m_fd < 0) {
        m_retry.start();
        return;
    }
    m_retry.stop();
    if (m_grab)
        ioctl(m_fd, EVIOCGRAB, 1);   // released when the fd closes (exit, or the pad going away)
    qInfo("gamepad: opened %s", qPrintable(QFileInfo(QString("/proc/self/fd/%1").arg(m_fd)).symLinkTarget()));
    m_notifier = new QSocketNotifier(m_fd, QSocketNotifier::Read, this);
    connect(m_notifier, &QSocketNotifier::activated, this, &Gamepad::read);
}

void Gamepad::lost()
{
    m_notifier->setEnabled(false);
    m_notifier->deleteLater();  // we're inside its activated() signal
    m_notifier = nullptr;
    ::close(m_fd);
    m_fd = -1;
    m_repeat.stop();
    m_held.clear();
    m_retry.start();
}

void Gamepad::hold(const QString &dir, bool down)
{
    if (down) {
        m_held = dir;
        emit pressed(dir);
        m_repeat.start(380);  // first repeat after 380 ms, then every 90 ms
    } else if (m_held == dir) {
        m_repeat.stop();
        m_held.clear();
    }
}

void Gamepad::read()
{
    static const QHash<int, QString> buttons = {
        {BTN_EAST, "a"}, {BTN_SOUTH, "b"}, {BTN_NORTH, "x"}, {BTN_WEST, "y"},
        {BTN_TL2, "lt"}, {BTN_TR2, "rt"}, {BTN_SELECT, "select"}, {BTN_START, "start"}, {BTN_MODE, "guide"}};
    input_event ev;
    ssize_t n;
    while ((n = ::read(m_fd, &ev, sizeof ev)) == sizeof ev) {
        if (ev.type == EV_KEY && (ev.code == BTN_TL || ev.code == BTN_TR)) {
            // Shoulders act on release, so LB+RB together is one "lr" (swap screens) rather than two tab switches.
            bool &held = ev.code == BTN_TL ? m_lb : m_rb;
            if (ev.value == 1) {
                held = true;
                m_combo = m_combo || (m_lb && m_rb);
            } else if (ev.value == 0 && held) {
                held = false;
                if (!m_combo)
                    emit pressed(ev.code == BTN_TL ? "lb" : "rb");
                else if (!m_lb && !m_rb) {
                    m_combo = false;
                    emit pressed("lr");
                }
            }
        } else if (ev.type == EV_KEY && ev.value == 1 && buttons.contains(ev.code))
            emit pressed(buttons[ev.code]);
        else if (ev.type == EV_ABS && ev.code == ABS_HAT0X) {
            hold("left", ev.value < 0);
            hold("right", ev.value > 0);
        } else if (ev.type == EV_ABS && ev.code == ABS_HAT0Y) {
            hold("up", ev.value < 0);
            hold("down", ev.value > 0);
        }
    }
    if (n < 0 && errno != EAGAIN)  // the pad was removed (InputPlumber restarted): reopen the new one
        lost();
}
