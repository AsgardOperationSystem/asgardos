#include "backend.h"

#include <QDateTime>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QJsonDocument>
#include <QJsonObject>
#include <QSet>
#include <QSysInfo>
#include <QXmlStreamReader>
#include <algorithm>

#include <fcntl.h>
#include <linux/input.h>
#include <unistd.h>

static const char *PLAYLOG = "/storage/.config/thor/playtime.jsonl";  // shared with Thor Panel (playlog.py)
static const QStringList IMAGE_EXT = {"png", "jpg", "jpeg", "webp"};

Backend::Backend(const QProcessEnvironment &gameEnv, QObject *parent)
    : QObject(parent), m_root(qEnvironmentVariable("ASGARD_ROOT")), m_gameEnv(gameEnv)
{
    scan();
    readPlaytime();
    readStatus();
    auto *t = new QTimer(this);
    connect(t, &QTimer::timeout, this, &Backend::readStatus);
    t->start(30000);
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
                                          x.name() == u"release")) {
            sys[x.name().toString()] = text(x);
        } else if (x.isStartElement() && x.name() == u"emulator") {
            const QString emu = x.attributes().value("name").toString();
            while (!(x.isEndElement() && x.name() == u"emulator") && !x.atEnd()) {
                x.readNext();
                if (x.isStartElement() && x.name() == u"core" && x.attributes().value("default") == u"true") {
                    sys["emulator"] = emu;
                    sys["core"] = text(x);
                }
            }
        } else if (x.isEndElement() && x.name() == u"system" && sys.contains("emulator")) {
            const QString name = sys["name"].toString(), dir = path(sys["path"].toString());
            QSet<QString> exts;
            for (const QString &e : sys["extension"].toString().split(' ', Qt::SkipEmptyParts))
                exts << e.toLower();
            const auto gl = readGamelist(path("/storage/ES-DE/gamelists/" + name + "/gamelist.xml"));
            const QString mediaDir = path("/storage/ES-DE/downloaded_media/" + name);
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
                const QString rel = QDir(dir).relativeFilePath(file);
                const QString stem = rel.left(rel.size() - fi.suffix().size() - 1);
                const QVariantMap meta = gl.value(QDir::cleanPath("./" + rel));
                QVariantMap g;
                g["path"] = file.mid(m_root.size());  // device path, without the dev fixture prefix
                g["sys"] = name;
                g["sysName"] = sys["fullname"];
                g["name"] = meta.value("name", fi.completeBaseName());
                g["desc"] = meta.value("desc");
                g["developer"] = meta.value("developer");
                g["year"] = meta.value("releasedate").toString().left(4);
                g["genre"] = meta.value("genre");
                g["cover"] = media(mediaDir + "/covers", stem);
                g["shot"] = media(mediaDir + "/screenshots", stem);
                g["marquee"] = media(mediaDir + "/marquees", stem);
                g["core"] = sys["core"];
                g["emulator"] = sys["emulator"];
                games << g;
                m_byPath[g["path"].toString()] = g;
            }
            if (games.isEmpty())
                continue;
            std::sort(games.begin(), games.end(), [](const QVariant &a, const QVariant &b) {
                return a.toMap()["name"].toString().compare(b.toMap()["name"].toString(), Qt::CaseInsensitive) < 0;
            });
            sys["count"] = games.size();
            sys["cover"] = games.first().toMap()["shot"];  // a picture for the system card until we have system art
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
    if (battery != m_battery || charging != m_charging) {
        m_battery = battery;
        m_charging = charging;
        emit statusChanged();
    }
}

void Backend::launch(const QVariantMap &game)
{
    if (m_game)
        return;
    const QString rom = game["path"].toString(), sys = game["sys"].toString();
    if (!QFile::exists("/usr/bin/runemu.sh")) {  // desktop
        qInfo("launch %s (%s)", qPrintable(rom), qPrintable(sys));
        return;
    }
    // playlog.py around ROCKNIX's runemu.sh (per-game options, governors, hotkeys), default core for the system.
    m_game = new QProcess(this);
    m_game->setProcessEnvironment(m_gameEnv);
    m_game->setProcessChannelMode(QProcess::ForwardedChannels);
    connect(m_game, &QProcess::finished, this, [this] {
        m_game->deleteLater();
        m_game = nullptr;
        readPlaytime();
        emit playingChanged();
    });
    m_game->start("/bin/bash", {"-c",
        // Our windows are hidden by now; the bottom panel goes dark unless the game opens a window there
        // (ROCKNIX's "Bottom"/"[w2]" sway rules power it back on).
        "swaymsg 'output DSI-1 power off' >/dev/null 2>&1; "
        "python3 /usr/share/asgard/playlog.py start \"$1\" \"$2\" 2>/dev/null; "
        "/usr/bin/runemu.sh \"$1\" -P\"$2\" --core=\"$3\" --emulator=\"$4\" --controllers=\"\"; rc=$?; "
        "python3 /usr/share/asgard/playlog.py stop 2>/dev/null; exit $rc",
        "run", rom, sys, game["core"].toString(), game["emulator"].toString()});
    emit playingChanged();
}

// --- Gamepad --------------------------------------------------------------------------------------------------------

static const char *PAD_NAME = "Sony Interactive Entertainment DualSense Wireless Controller";

Gamepad::Gamepad(QObject *parent) : QObject(parent)
{
    // /proc/bus/input/devices: find the event node of the exact pad name (not its Motion/Touchpad siblings).
    QFile f("/proc/bus/input/devices");
    if (!f.open(QIODevice::ReadOnly))
        return;
    QString name;
    for (const QString &line : QString::fromUtf8(f.readAll()).split('\n')) {
        if (line.startsWith("N: Name="))
            name = line.mid(9).chopped(1);
        else if (line.startsWith("H: Handlers=") && name == PAD_NAME)
            for (const QString &h : line.mid(12).split(' '))
                if (h.startsWith("event"))
                    m_fd = ::open(qPrintable("/dev/input/" + h), O_RDONLY | O_NONBLOCK | O_CLOEXEC);
    }
    if (m_fd < 0)
        return;
    m_notifier = new QSocketNotifier(m_fd, QSocketNotifier::Read, this);
    connect(m_notifier, &QSocketNotifier::activated, this, &Gamepad::read);
    m_repeat.setInterval(90);
    connect(&m_repeat, &QTimer::timeout, this, [this] {
        m_repeat.setInterval(90);
        emit pressed(m_held);
    });
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
        {BTN_EAST, "a"}, {BTN_SOUTH, "b"}, {BTN_NORTH, "x"}, {BTN_WEST, "y"}, {BTN_TL, "lb"}, {BTN_TR, "rb"},
        {BTN_TL2, "lt"}, {BTN_TR2, "rt"}, {BTN_SELECT, "select"}, {BTN_START, "start"}, {BTN_MODE, "guide"}};
    input_event ev;
    while (::read(m_fd, &ev, sizeof ev) == sizeof ev) {
        if (ev.type == EV_KEY && ev.value == 1 && buttons.contains(ev.code))
            emit pressed(buttons[ev.code]);
        else if (ev.type == EV_ABS && ev.code == ABS_HAT0X) {
            hold("left", ev.value < 0);
            hold("right", ev.value > 0);
        } else if (ev.type == EV_ABS && ev.code == ABS_HAT0Y) {
            hold("up", ev.value < 0);
            hold("down", ev.value > 0);
        }
    }
}
