#pragma once
#include <QHash>
#include <QObject>
#include <QProcess>
#include <QProcessEnvironment>
#include <QSocketNotifier>
#include <QTimer>
#include <QVariant>

// Library (ROCKNIX es_systems.cfg + ROM dirs + scraped media), playtime, battery, game launching.
// ASGARD_ROOT prefixes /storage and /usr/config so a desktop build can run on a copied fixture.
class Backend : public QObject
{
    Q_OBJECT
    Q_PROPERTY(QVariantList systems READ systems NOTIFY libraryChanged)
    Q_PROPERTY(QVariantList recent READ recent NOTIFY libraryChanged)
    Q_PROPERTY(int battery READ battery NOTIFY statusChanged)       // -1 = no battery (desktop)
    Q_PROPERTY(bool charging READ charging NOTIFY statusChanged)
    Q_PROPERTY(bool playing READ playing NOTIFY playingChanged)
    Q_PROPERTY(QString hostname READ hostname CONSTANT)
    Q_PROPERTY(bool screensOff READ screensOff WRITE setScreensOff NOTIFY screensOffChanged)  // OLED rest (X)

public:
    Backend(const QProcessEnvironment &gameEnv, QObject *parent = nullptr);
    QVariantList systems() const { return m_systems; }
    QVariantList recent() const { return m_recent; }
    int battery() const { return m_battery; }
    bool charging() const { return m_charging; }
    bool playing() const { return m_game != nullptr; }
    bool screensOff() const { return m_screensOff; }
    void setScreensOff(bool off);
    QString hostname() const;

    Q_INVOKABLE QVariantList games(const QString &system) const { return m_games.value(system); }
    QList<QVariantMap> allGames() const { return m_byPath.values(); }
    Q_INVOKABLE void launch(const QVariantMap &game);
    Q_INVOKABLE void openSettings(const QVariantMap &game = {});   // Thor Settings (Start)
    Q_INVOKABLE QVariantMap playStats(const QString &path) const;  // {playtime (s), lastPlayed (epoch s)}

signals:
    void libraryChanged();
    void statusChanged();
    void playingChanged();
    void screensOffChanged();

private:
    void scan();
    void readPlaytime();
    void readStatus();
    void run(const QString &script, const QStringList &args, const QProcessEnvironment &env);
    QString path(const QString &p) const { return m_root + p; }

    QString m_root;
    QProcessEnvironment m_gameEnv;  // the environment we were started with, without our own Qt settings
    QVariantList m_systems, m_recent;
    QHash<QString, QVariantList> m_games;
    QHash<QString, QVariantMap> m_byPath;
    bool m_screensOff = false;
    int m_battery = -1;
    bool m_charging = false;
    QProcess *m_game = nullptr;
};

// InputPlumber's virtual DualSense read straight from evdev (Qt 6 has no gamepad module).
// Emits the Thor's printed button names; the pad is positional, so A = east, B = south, X = north, Y = west.
class Gamepad : public QObject
{
    Q_OBJECT
public:
    explicit Gamepad(bool disabled = false, QObject *parent = nullptr);
signals:
    void pressed(const QString &button);   // up down left right a b x y lb rb lt rt select start guide
private:
    void open();
    void lost();
    void read();
    void hold(const QString &dir, bool down);
    int m_fd = -1;
    QSocketNotifier *m_notifier = nullptr;
    QTimer m_retry;      // pad not there (yet / any more): look again every 500 ms
    QTimer m_repeat;     // held d-pad direction repeats, like a keyboard
    QString m_held;
};
