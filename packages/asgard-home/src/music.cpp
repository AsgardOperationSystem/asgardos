#include "music.h"

#include <QCoreApplication>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QJsonDocument>
#include <QJsonObject>
#include <QRandomGenerator>
#include <QTextStream>
#include <QUrl>

#include <algorithm>
#include <csignal>
#include <numeric>
#include <sys/prctl.h>

static const char *PLAYLISTS = "/storage/.config/gmu/playlists";            // the Music Player system's ROM folder
static const char *ART = "/storage/ES-DE/downloaded_media/music/covers/";   // playlist covers (navidrome-sync)

Music::Music(QObject *parent) : QObject(parent), m_root(qEnvironmentVariable("ASGARD_ROOT"))
{
    m_sockPath = QDir::tempPath() + QString("/asgard-music-%1.sock").arg(QCoreApplication::applicationPid());
    m_mpv.setProgram("mpv");
    m_mpv.setArguments({"--idle=yes", "--no-video", "--no-terminal", "--audio-display=no", "--gapless-audio=yes",
                        "--input-ipc-server=" + m_sockPath,
                        "--ao=" + qEnvironmentVariable("ASGARD_MUSIC_AO", "pipewire,pulse,alsa")});
    m_mpv.setChildProcessModifier([] { prctl(PR_SET_PDEATHSIG, SIGTERM); });   // dies with us, even on SIGKILL
    m_mpv.setProcessChannelMode(QProcess::ForwardedErrorChannel);
    m_mpv.start();
    connect(&m_sock, &QLocalSocket::readyRead, this, &Music::readMpv);
    connect(&m_sock, &QLocalSocket::connected, this, [this] {
        m_connect.stop();
        for (const char *p : {"time-pos", "duration", "pause"})
            send({"observe_property", 1, p});
        for (const QByteArray &c : std::as_const(m_pending))
            m_sock.write(c);
        m_pending.clear();
    });
    m_connect.setInterval(100);
    connect(&m_connect, &QTimer::timeout, this, &Music::connectMpv);
    m_connect.start();
}

Music::~Music()
{
    m_mpv.terminate();
    m_mpv.waitForFinished(1000);
    QFile::remove(m_sockPath);
}

void Music::connectMpv()
{
    if (m_sock.state() == QLocalSocket::UnconnectedState && QFile::exists(m_sockPath))
        m_sock.connectToServer(m_sockPath);
}

void Music::send(const QJsonArray &command)
{
    const QByteArray line = QJsonDocument(QJsonObject{{"command", command}}).toJson(QJsonDocument::Compact) + "\n";
    if (m_sock.state() == QLocalSocket::ConnectedState)
        m_sock.write(line);
    else
        m_pending << line;
}

void Music::readMpv()
{
    m_buf += m_sock.readAll();
    int nl;
    while ((nl = m_buf.indexOf('\n')) >= 0) {
        const QJsonObject o = QJsonDocument::fromJson(m_buf.left(nl)).object();
        m_buf.remove(0, nl + 1);
        const QString event = o["event"].toString();
        if (event == "property-change") {
            const QString n = o["name"].toString();
            if (n == "time-pos") { m_position = o["data"].toDouble(); emit positionChanged(); }
            else if (n == "duration") { m_duration = o["data"].toDouble(); emit positionChanged(); }
            else if (n == "pause") { m_playing = !o["data"].toBool(); emit stateChanged(); }
        } else if (event == "end-file") {
            const QString reason = o["reason"].toString();   // "stop" is our own replace: not the end of a song
            if (reason == "eof" || reason == "error")
                advance(false);
        }
    }
}

QString Music::setting(const QString &key, const QString &fallback) const
{
    QFile f(path("/storage/.config/system/configs/system.cfg"));
    QString value = fallback;
    if (f.open(QIODevice::ReadOnly | QIODevice::Text)) {
        QTextStream in(&f);
        while (!in.atEnd()) {   // the last one wins, as in ROCKNIX's get_setting
            const QString line = in.readLine();
            if (line.startsWith(key + "=") && line.size() > key.size() + 1)
                value = line.mid(key.size() + 1);
        }
    }
    return value;
}

// A song's art: <song>.jpg/.png beside it (navidrome-sync saves the album art so), else the folder's cover.
QString Music::coverFor(const QString &file) const
{
    const QFileInfo fi(path(file));
    for (const QString &c : {fi.path() + "/" + fi.completeBaseName() + ".jpg", fi.path() + "/" + fi.completeBaseName() + ".png",
                             fi.path() + "/cover.jpg", fi.path() + "/cover.png", fi.path() + "/folder.jpg"})
        if (QFile::exists(c))
            return QUrl::fromLocalFile(c).toString();
    return QString();
}

QVariantList Music::playlists() const
{
    QVariantList out;
    for (const QFileInfo &fi : QDir(path(PLAYLISTS)).entryInfoList({"*.m3u"}, QDir::Files, QDir::Name)) {
        QFile f(fi.filePath());
        int songs = 0;
        if (f.open(QIODevice::ReadOnly | QIODevice::Text))
            for (const QByteArray &l : f.readAll().split('\n'))
                songs += !l.trimmed().isEmpty() && !l.startsWith('#');
        if (!songs)
            continue;   // gmu's empty playlist.m3u
        QString cover;
        for (const char *ext : {".jpg", ".png"})
            if (QFile::exists(path(ART) + fi.completeBaseName() + ext))
                cover = QUrl::fromLocalFile(path(ART) + fi.completeBaseName() + ext).toString();
        out << QVariantMap{{"name", fi.completeBaseName()}, {"path", fi.filePath().mid(m_root.size())},
                           {"cover", cover}, {"songs", songs}};
    }
    return out;
}

void Music::load(const QString &m3u)
{
    QFile f(path(m3u));
    if (!f.open(QIODevice::ReadOnly | QIODevice::Text))
        return;
    m_tracks.clear();
    QString title, artist;
    int length = -1;
    QTextStream in(&f);
    while (!in.atEnd()) {
        const QString l = in.readLine().trimmed();
        if (l.startsWith("#EXTINF:")) {   // #EXTINF:<seconds>,<artist> - <title>
            const int comma = l.indexOf(',');
            length = l.mid(8, comma - 8).toInt();
            const QString info = l.mid(comma + 1);
            const int dash = info.indexOf(" - ");
            artist = dash >= 0 ? info.left(dash) : QString();
            title = dash >= 0 ? info.mid(dash + 3) : info;
        } else if (!l.isEmpty() && !l.startsWith('#')) {
            const QString file = l.startsWith('/') ? l : QFileInfo(m3u).path() + "/" + l;
            if (title.isEmpty())
                title = QFileInfo(file).completeBaseName();
            m_tracks << QVariantMap{{"title", title}, {"artist", artist}, {"file", file},
                                    {"cover", coverFor(file)}, {"length", length}};
            title.clear(); artist.clear(); length = -1;
        }
    }
    m_name = QFileInfo(m3u).completeBaseName();
    m_order.resize(m_tracks.size());
    std::iota(m_order.begin(), m_order.end(), 0);
    if (m_shuffle)
        shuffleOrder();
    emit playlistChanged();
    if (!m_tracks.isEmpty())
        play(m_shuffle ? m_order[0] : 0);
}

void Music::play(int index)
{
    if (index < 0 || index >= m_tracks.size())
        return;
    m_current = index;
    m_position = 0;
    m_duration = m_tracks[index].toMap()["length"].toDouble();
    emit currentChanged();
    emit positionChanged();
    send({"loadfile", path(m_tracks[index].toMap()["file"].toString()), "replace"});
    send({"set_property", "pause", false});
}

void Music::toggle()
{
    if (m_current < 0) { play(m_shuffle && !m_order.isEmpty() ? m_order[0] : 0); return; }
    send({"set_property", "pause", m_playing});
}

void Music::advance(bool userSkip)
{
    if (m_tracks.isEmpty())
        return;
    if (m_repeat == "one" && !userSkip) { play(m_current); return; }
    const int at = m_order.indexOf(m_current);
    if (at + 1 < m_order.size()) { play(m_order[at + 1]); return; }
    if (m_repeat == "all" || userSkip) {
        if (m_shuffle)
            shuffleOrder();
        play(m_order[0]);
        return;
    }
    send({"set_property", "pause", true});   // the end, repeat off
}

void Music::next() { advance(true); }

void Music::prev()
{
    if (m_position > 3) { seekTo(0); return; }   // like most players: back to the start first
    const int at = m_order.indexOf(m_current);
    play(m_order[at > 0 ? at - 1 : m_order.size() - 1]);
}

void Music::seek(double seconds) { send({"seek", seconds, "relative"}); }
void Music::seekTo(double seconds) { send({"seek", seconds, "absolute"}); }

void Music::shuffleOrder()
{
    std::shuffle(m_order.begin(), m_order.end(), *QRandomGenerator::global());
    const int at = m_order.indexOf(m_current);   // the playing song first, the rest after it
    if (at > 0)
        std::swap(m_order[0], m_order[at]);
}

void Music::toggleShuffle()
{
    m_shuffle = !m_shuffle;
    if (m_shuffle)
        shuffleOrder();
    else
        std::iota(m_order.begin(), m_order.end(), 0);
    emit stateChanged();
}

void Music::cycleRepeat()
{
    m_repeat = m_repeat == "off" ? "all" : m_repeat == "all" ? "one" : "off";
    emit stateChanged();
}
