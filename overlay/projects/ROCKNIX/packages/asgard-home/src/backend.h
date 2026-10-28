#pragma once
#include <QHash>
#include <QJSValue>
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
    Q_PROPERTY(bool playing READ playing NOTIFY playingChanged)   // a game is running in front (not in the background)
    Q_PROPERTY(QVariantMap background READ background NOTIFY playingChanged)  // the game "Back to Home" left, or {}
    Q_PROPERTY(QString hostname READ hostname CONSTANT)
    Q_PROPERTY(bool screensOff READ screensOff WRITE setScreensOff NOTIFY screensOffChanged)  // OLED rest (X)
    Q_PROPERTY(bool gameMenu READ gameMenu WRITE setGameMenu NOTIFY gameMenuChanged)  // in-game menu (Home tap)

public:
    Backend(const QProcessEnvironment &gameEnv, QObject *parent = nullptr);
    QVariantList systems() const { return m_systems; }
    QVariantList recent() const { return m_recent; }
    int battery() const { return m_battery; }
    bool charging() const { return m_charging; }
    bool playing() const { return m_game != nullptr && !m_background; }
    QVariantMap background() const { return m_background ? m_launched : QVariantMap(); }
    bool screensOff() const { return m_screensOff; }
    void setScreensOff(bool off);
    bool gameMenu() const { return m_gameMenu; }
    void setGameMenu(bool on);
    QString hostname() const;

    Q_INVOKABLE QVariantList games(const QString &system) const { return m_games.value(system); }
    QList<QVariantMap> allGames() const { return m_byPath.values(); }
    Q_INVOKABLE void launch(const QVariantMap &game);
    Q_INVOKABLE void openSettings(const QVariantMap &game = {}, const QString &page = {});  // classic Thor Settings
    Q_INVOKABLE void runTool(const QString &script, const QStringList &args = {});  // a fullscreen tool (e.g. GPcal) in place of the frontend
    Q_INVOKABLE QVariantMap playStats(const QString &path) const;  // {playtime (s), lastPlayed (epoch s)}
    Q_INVOKABLE QString getSetting(const QString &key, const QString &fallback = {}) const;  // system.cfg
    Q_INVOKABLE void setSetting(const QString &key, const QString &value);                  // "" removes the key
    Q_INVOKABLE QVariantList emulators(const QString &system) const;  // [{name, cores: [...]}], ROCKNIX's choices
    Q_INVOKABLE void shell(const QString &command);
    Q_INVOKABLE void sound(const QString &name);   // qml/sounds/<name>.wav, unless asgard.sounds=0
    Q_INVOKABLE void exec(const QString &command, const QJSValue &done);  // done(output) when it exits
    Q_INVOKABLE void rescan();
    Q_INVOKABLE QStringList runningGame() const;          // the running emulator's process names
    Q_INVOKABLE void gameKeys(const QString &combo);      // focus the game and press e.g. "F4", "Alt+S"
    Q_INVOKABLE void quitGame(bool saveLog = false);   // saveLog: a hang, kept for debugging
    Q_INVOKABLE void toBackground();   // "Back to Home": the game freezes, its windows hide, we show
    Q_INVOKABLE void resumeGame();     // "Return to <game>"
    Q_INVOKABLE void retroarch(const QString &cmd);       // RetroArch network command, e.g. "PAUSE_TOGGLE"
    Q_INVOKABLE void padChord(const QStringList &buttons); // InputPlumber, past its profile: "Gamepad:Button:Guide"
    Q_INVOKABLE QVariantMap osInfo() const;   // /etc/os-release

signals:
    void libraryChanged();
    void statusChanged();
    void playingChanged();
    void screensOffChanged();
    void settingsChanged();
    void gameMenuChanged();
    void osd(const QString &what, int value);   // volume/brightness changed (asgard-osd): show the slider

private:
    void scan();
    void readPlaytime();
    void readStatus();
    void play(const QString &name);     // a sound, without the menu-sounds setting
    void topScreenOn();
    void command(const QString &cmd);
    bool togglePause();                 // the running game's own pause, if we know it; false otherwise
    void run(const QString &script, const QStringList &args, const QProcessEnvironment &env);
    QString setting(const QString &sys, const QString &file, const QString &key, const QString &fallback) const;
    QString path(const QString &p) const { return m_root + p; }

    QString m_root;
    QProcessEnvironment m_gameEnv;  // the environment we were started with, without our own Qt settings
    QVariantList m_systems, m_recent;
    QHash<QString, QVariantList> m_games;
    QHash<QString, QVariantMap> m_byPath;
    bool m_screensOff = false;
    int m_battery = -1;
    bool m_charging = false;
    int m_plugged = -1;                   // charger online flag, -1 until first read
    QProcess *m_game = nullptr;
    QVariantMap m_launched;           // the game m_game runs ({} for tools)
    bool m_background = false;
    bool m_gameMenu = false;
    bool m_sleepPaused = false;   // we paused the game for a sleep ("sleep"), to unpause on "wake"
    int m_keys = -1;   // uinput keyboard for emulator hotkeys
    int m_cmd = -1;    // /run/asgard-home.cmd: commands from thor-ayn-button ("menu"), the sleep hook ("sleep", "wake")
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
    bool m_lb = false, m_rb = false, m_combo = false;   // shoulder state for the LB+RB combo
};
