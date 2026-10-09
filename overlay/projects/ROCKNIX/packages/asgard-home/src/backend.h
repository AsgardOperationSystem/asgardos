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

public:
    Backend(const QProcessEnvironment &gameEnv, QObject *parent = nullptr);
    QVariantList systems() const { return m_systems; }
    QVariantList recent() const { return m_recent; }
    int battery() const { return m_battery; }
    bool charging() const { return m_charging; }
    bool playing() const { return m_game != nullptr; }
    QString hostname() const;

    Q_INVOKABLE QVariantList games(const QString &system) const { return m_games.value(system); }
    Q_INVOKABLE void launch(const QVariantMap &game);

signals:
    void libraryChanged();
    void statusChanged();
    void playingChanged();

private:
    void scan();
    void readPlaytime();
    void readStatus();
    QString path(const QString &p) const { return m_root + p; }

    QString m_root;
    QProcessEnvironment m_gameEnv;  // the environment we were started with, without our own Qt settings
    QVariantList m_systems, m_recent;
    QHash<QString, QVariantList> m_games;
    QHash<QString, QVariantMap> m_byPath;
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
    explicit Gamepad(QObject *parent = nullptr);
signals:
    void pressed(const QString &button);   // up down left right a b x y lb rb lt rt select start guide
private:
    void read();
    void hold(const QString &dir, bool down);
    int m_fd = -1;
    QSocketNotifier *m_notifier = nullptr;
    QTimer m_repeat;     // held d-pad direction repeats, like a keyboard
    QString m_held;
};
