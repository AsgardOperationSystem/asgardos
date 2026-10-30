#pragma once

#include <QByteArray>
#include <QJsonArray>
#include <QLocalSocket>
#include <QObject>
#include <QProcess>
#include <QTimer>
#include <QVariantList>
#include <QVector>

// Asgard Music's player (asgard-home --music, qml/Music.qml): an mpv child (no video, idle) driven over its JSON IPC
// socket. The queue is ours, read from the .m3u (titles and artists from #EXTINF), with shuffle and repeat; mpv plays
// one file at a time. mpv dies with us (PR_SET_PDEATHSIG), so a killed player never leaves music playing.
class Music : public QObject
{
    Q_OBJECT
    Q_PROPERTY(QString name READ name NOTIFY playlistChanged)              // the loaded playlist, "" for none
    Q_PROPERTY(QVariantList tracks READ tracks NOTIFY playlistChanged)     // [{title, artist, file, cover, length}]
    Q_PROPERTY(QVariantList playlists READ playlists CONSTANT)             // [{name, path, cover, songs}]
    Q_PROPERTY(int current READ current NOTIFY currentChanged)             // index into tracks, -1 before the first
    Q_PROPERTY(bool playing READ playing NOTIFY stateChanged)
    Q_PROPERTY(bool shuffle READ shuffle NOTIFY stateChanged)
    Q_PROPERTY(QString repeat READ repeat NOTIFY stateChanged)             // off | all | one
    Q_PROPERTY(double position READ position NOTIFY positionChanged)       // seconds
    Q_PROPERTY(double duration READ duration NOTIFY positionChanged)

public:
    explicit Music(QObject *parent = nullptr);
    ~Music() override;

    Q_INVOKABLE void load(const QString &m3u);      // and start playing it
    Q_INVOKABLE void play(int index);
    Q_INVOKABLE void toggle();
    Q_INVOKABLE void next();
    Q_INVOKABLE void prev();
    Q_INVOKABLE void seek(double seconds);          // relative
    Q_INVOKABLE void seekTo(double seconds);
    Q_INVOKABLE void toggleShuffle();
    Q_INVOKABLE void cycleRepeat();
    Q_INVOKABLE QString setting(const QString &key, const QString &fallback = QString()) const;   // system.cfg

    QString name() const { return m_name; }
    QVariantList tracks() const { return m_tracks; }
    QVariantList playlists() const;
    int current() const { return m_current; }
    bool playing() const { return m_playing; }
    bool shuffle() const { return m_shuffle; }
    QString repeat() const { return m_repeat; }
    double position() const { return m_position; }
    double duration() const { return m_duration; }

signals:
    void playlistChanged();
    void currentChanged();
    void stateChanged();
    void positionChanged();

private:
    QString path(const QString &p) const { return m_root + p; }   // ASGARD_ROOT: the desktop dev fixture
    QString coverFor(const QString &file) const;
    void send(const QJsonArray &command);
    void connectMpv();
    void readMpv();
    void advance(bool userSkip);    // the next track in play order, or stop at the end (repeat off)
    void shuffleOrder();

    QString m_root;
    QProcess m_mpv;
    QLocalSocket m_sock;
    QTimer m_connect;               // until mpv's socket is up
    QString m_sockPath;
    QByteArray m_buf;
    QVector<QByteArray> m_pending;  // commands sent before the socket connected
    QString m_name;
    QVariantList m_tracks;
    QVector<int> m_order;           // play order (indices into m_tracks); shuffled or 0..n-1
    int m_current = -1;
    bool m_playing = false, m_shuffle = false;
    QString m_repeat = "all";
    double m_position = 0, m_duration = 0;
};
