#pragma once

#include <QObject>
#include <QString>
#include <QTimer>

// Asgard Keyboard (asgard-home --osk <app_id>, qml/Osk.qml): a touch keyboard for Tools (Terminal, Firefox) as a
// plain window on the bottom screen. wvkbd's layer surface never got a touch on the Thor (traced 2026-10-27: libinput
// saw every tap, wvkbd none; a window there got all of them). Keys go out through a uinput keyboard of its own, as Home's
// hotkeys do: each press first hands sway's focus back to the target app (a tap focuses this window), then key down;
// key up on release, so holding a key repeats like a real one. SIGUSR1 hides it, SIGUSR2 shows it (wvkbd's signals:
// Home sends them around its in-game menu, through /run/asgard-osk.pid).
class Osk : public QObject
{
    Q_OBJECT
    Q_PROPERTY(bool shown READ shown NOTIFY shownChanged)

public:
    explicit Osk(const QString &target, QObject *parent = nullptr);
    ~Osk() override;

    // key: one character ("a", "A", "|") or a name (Esc Tab Enter Back Space Del Up Down Left Right Home End PgUp
    // PgDn). The modifiers held for it: Shift / Ctrl / Alt toggles of the QML side.
    Q_INVOKABLE void press(const QString &key, bool shift, bool ctrl, bool alt);
    Q_INVOKABLE void release();

    bool shown() const { return m_shown; }

signals:
    void shownChanged();

private:
    void emitKey(int code, int value);

    QString m_target;
    int m_fd = -1;
    QList<int> m_down;                  // the codes of the key being held, modifiers first
    bool m_shown = true;
    QTimer m_signals;
};
