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
    Q_PROPERTY(int pauseFps READ pauseFps NOTIFY gameMenuChanged)  // the game's FPS just before the menu paused it, -1 unknown

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
    int pauseFps() const { return m_fps; }
    QString hostname() const;

    Q_INVOKABLE QVariantList games(const QString &system) const { return m_games.value(system); }
    QList<QVariantMap> allGames() const { return m_byPath.values(); }
    Q_INVOKABLE void launch(const QVariantMap &game);
    Q_INVOKABLE void openSettings(const QVariantMap &game = {}, const QString &page = {});  // classic Thor Settings
    Q_INVOKABLE void runTool(const QString &script, const QStringList &args = {});  // a fullscreen tool (e.g. touch calibration) in place of the frontend
    Q_INVOKABLE QVariantMap playStats(const QString &path) const;  // {playtime (s), lastPlayed (epoch s)}
    Q_INVOKABLE QString getSetting(const QString &key, const QString &fallback = {}) const;  // system.cfg
    Q_INVOKABLE void setSetting(const QString &key, const QString &value);                  // "" removes the key
    Q_INVOKABLE QVariantList emulators(const QString &system) const;  // [{name, cores: [...]}], ROCKNIX's choices
    Q_INVOKABLE void shell(const QString &command);
    Q_INVOKABLE void sound(const QString &name);   // qml/sounds/<name>.wav, unless asgard.sounds=0
    Q_INVOKABLE void exec(const QString &command, const QJSValue &done);  // done(output) when it exits
    Q_INVOKABLE void rescan();
    Q_INVOKABLE QStringList runningGame() const;          // the running emulator's process names
    Q_INVOKABLE QVariantMap launchedGame() const { return m_launched; }   // the game launch() started ({} for tools)
    Q_INVOKABLE void gameKeys(const QString &combo);      // focus the game and press e.g. "F4", "Alt+S"
    Q_INVOKABLE void quitGame(bool saveLog = false);   // saveLog: a hang, kept for debugging
    Q_INVOKABLE void toBackground();   // "Back to Home": the game freezes, its windows hide, we show
    Q_INVOKABLE void resumeGame();     // "Return to <game>"
    Q_INVOKABLE void retroarch(const QString &cmd);       // RetroArch network command, e.g. "PAUSE_TOGGLE"
    Q_INVOKABLE void padChord(const QStringList &buttons); // InputPlumber, past its profile: "Gamepad:Button:Guide"
    Q_INVOKABLE QVariantMap osInfo() const;   // /etc/os-release
    // Stick calibration (Settings > Hardware > Calibration, StickCal.qml, CAL-4). rsinput's parameters, read and written
    // live (writing sets update_params, so the driver re-reads its ranges); the saved calibration (CAL-2); and
    // stickcal(on): InputPlumber stopped while the raw pad is read (pad.setRaw), restarted after.
    Q_INVOKABLE QVariantMap rsinput() const;
    Q_INVOKABLE void setRsinput(const QVariantMap &params);
    Q_INVOKABLE void saveRsinput(const QString &text);
    Q_INVOKABLE void stickcal(bool on);

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
    void sampleFps();
    void play(const QString &name);     // a sound, without the menu-sounds setting
    void topScreenOn();
    void command(const QString &cmd);
    bool togglePause();                 // the running game's own pause, if we know it; false otherwise
    void freezeGame(bool stop);         // SIGSTOP / SIGCONT the game and its children: the menu's pause for the rest
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
    QHash<qint64, qint64> m_frames;   // sway's frame count per game window at m_framesAt (sampleFps)
    qint64 m_framesAt = 0;            // ms, 0 = no sample yet
    int m_fps = -1;
    bool m_sleepPaused = false;   // we paused the game for a sleep ("sleep"), to unpause on "wake"
    bool m_standby = false;       // asgard-transfers.py's standby ("standby"): the game waits, paused or frozen
    bool m_standbyPaused = false; // ...by its own pause (else frozen)
    QList<int> m_frozen;          // the processes the in-game menu froze (freezeGame), continued when it closes
    int m_keys = -1;   // uinput keyboard for emulator hotkeys
    int m_cmd = -1;    // /run/asgard-home.cmd: commands from thor-ayn-button ("menu"), the sleep hook ("sleep", "wake")
};

// InputPlumber's virtual DualSense read straight from evdev (Qt 6 has no gamepad module).
// Emits the Thor's printed button names; the pad is positional, so A = east, B = south, X = north, Y = west.
// The left stick moves like the d-pad, and the back button (InputPlumber's keyboard F1) is B (HOME-1).
class Gamepad : public QObject
{
    Q_OBJECT
    // Raw mode (stick calibration, with InputPlumber stopped): rsinput's own pad, grabbed. Its buttons drive Home as the
    // virtual pad's do, and its sticks and triggers are here as the driver reports them: [x, y, z, rx, ry, rz].
    Q_PROPERTY(bool raw READ raw NOTIFY rawChanged)
    Q_PROPERTY(QVariantList axes READ axes NOTIFY axesChanged)
public:
    // grab: the pad is ours alone (EVIOCGRAB): Home and a paused game don't see the presses (Thor Panel)
    explicit Gamepad(bool disabled = false, bool grab = false, QObject *parent = nullptr);
    Q_INVOKABLE void setRaw(bool on);
    bool raw() const { return m_raw; }
    QVariantList axes() const;
signals:
    void pressed(const QString &button);   // up down left right a b x y lb rb lt rt select start guide
    void rawChanged();
    void axesChanged();
private:
    void close();
    void closeKeyboard();
    void open();
    void lost();
    void read();
    void readKeyboard();
    void hold(const QString &dir, bool down);
    void stick(int axis, int value);
    int m_fd = -1;
    QSocketNotifier *m_notifier = nullptr;
    int m_kbd = -1;      // InputPlumber's keyboard: the back button arrives there as F1
    QSocketNotifier *m_kbdNotifier = nullptr;
    int m_stick[2] = {};            // the left stick as a d-pad: -1, 0, 1 for x (left, right) and y (up, down)
    int m_stickMin[2] = {0, 0}, m_stickMax[2] = {255, 255};   // its range (the DualSense's, until the pad says)
    QTimer m_retry;      // pad not there (yet / any more): look again every 500 ms
    QTimer m_repeat;     // held d-pad direction repeats, like a keyboard
    QString m_held;
    bool m_lb = false, m_rb = false, m_combo = false;   // shoulder state for the LB+RB combo
    bool m_grab = false;
    bool m_disabled = false;
    bool m_raw = false;
    bool m_fdRaw = false;   // m_fd is rsinput's pad: in raw mode, or standing in until InputPlumber's pad is back
    int m_axes[6] = {};
    QTimer m_axesTimer;  // axis changes reach QML at most every 30 ms
};
