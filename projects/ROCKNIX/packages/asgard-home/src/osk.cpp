#include "osk.h"

#include <QHash>
#include <QProcess>

#include <atomic>
#include <csignal>
#include <cstring>
#include <fcntl.h>
#include <linux/uinput.h>
#include <sys/ioctl.h>
#include <unistd.h>

static std::atomic<int> pendingSignal{0};   // SIGUSR1 / SIGUSR2, read by a timer (no Qt calls in a handler)

// The keymap is sway's default (us): a character is a key, with Shift or not.
static QHash<QChar, QPair<int, bool>> charKeys()
{
    QHash<QChar, QPair<int, bool>> m;
    const char *letters = "abcdefghijklmnopqrstuvwxyz";
    const int letterCodes[] = {KEY_A, KEY_B, KEY_C, KEY_D, KEY_E, KEY_F, KEY_G, KEY_H, KEY_I, KEY_J, KEY_K, KEY_L, KEY_M,
                               KEY_N, KEY_O, KEY_P, KEY_Q, KEY_R, KEY_S, KEY_T, KEY_U, KEY_V, KEY_W, KEY_X, KEY_Y, KEY_Z};
    for (int i = 0; i < 26; i++) {
        m[QChar(letters[i])] = {letterCodes[i], false};
        m[QChar(letters[i]).toUpper()] = {letterCodes[i], true};
    }
    const int digitCodes[] = {KEY_0, KEY_1, KEY_2, KEY_3, KEY_4, KEY_5, KEY_6, KEY_7, KEY_8, KEY_9};
    for (int i = 0; i < 10; i++)
        m[QChar('0' + i)] = {digitCodes[i], false};
    const QString shifted = ")!@#$%^&*(";
    for (int i = 0; i < 10; i++)
        m[shifted[i]] = {digitCodes[i], true};
    for (const auto &[c, code, shift] : std::initializer_list<std::tuple<char, int, bool>>{
             {'-', KEY_MINUS, false}, {'_', KEY_MINUS, true}, {'=', KEY_EQUAL, false}, {'+', KEY_EQUAL, true},
             {'[', KEY_LEFTBRACE, false}, {'{', KEY_LEFTBRACE, true}, {']', KEY_RIGHTBRACE, false},
             {'}', KEY_RIGHTBRACE, true}, {';', KEY_SEMICOLON, false}, {':', KEY_SEMICOLON, true},
             {'\'', KEY_APOSTROPHE, false}, {'"', KEY_APOSTROPHE, true}, {'`', KEY_GRAVE, false}, {'~', KEY_GRAVE, true},
             {'\\', KEY_BACKSLASH, false}, {'|', KEY_BACKSLASH, true}, {',', KEY_COMMA, false}, {'<', KEY_COMMA, true},
             {'.', KEY_DOT, false}, {'>', KEY_DOT, true}, {'/', KEY_SLASH, false}, {'?', KEY_SLASH, true},
             {' ', KEY_SPACE, false}})
        m[QChar(c)] = {code, shift};
    return m;
}

static const QHash<QString, int> namedKeys = {
    {"Esc", KEY_ESC}, {"Tab", KEY_TAB}, {"Enter", KEY_ENTER}, {"Back", KEY_BACKSPACE}, {"Space", KEY_SPACE},
    {"Del", KEY_DELETE}, {"Up", KEY_UP}, {"Down", KEY_DOWN}, {"Left", KEY_LEFT}, {"Right", KEY_RIGHT},
    {"Home", KEY_HOME}, {"End", KEY_END}, {"PgUp", KEY_PAGEUP}, {"PgDn", KEY_PAGEDOWN}};

Osk::Osk(const QString &target, QObject *parent) : QObject(parent), m_target(target)
{
    if (!qEnvironmentVariableIsSet("ASGARD_SHOT")) {
        m_fd = ::open("/dev/uinput", O_WRONLY | O_NONBLOCK | O_CLOEXEC);
        if (m_fd >= 0) {
            ioctl(m_fd, UI_SET_EVBIT, EV_KEY);   // no EV_REP: Wayland clients repeat a held key themselves
            for (int k = KEY_ESC; k <= KEY_DELETE; k++)
                ioctl(m_fd, UI_SET_KEYBIT, k);
            uinput_setup us{};
            us.id.bustype = BUS_VIRTUAL;
            strcpy(us.name, "asgard-keyboard");
            if (ioctl(m_fd, UI_DEV_SETUP, &us) < 0 || ioctl(m_fd, UI_DEV_CREATE) < 0) {
                ::close(m_fd);
                m_fd = -1;
            }
        }
    }
    signal(SIGUSR1, [](int) { pendingSignal = SIGUSR1; });
    signal(SIGUSR2, [](int) { pendingSignal = SIGUSR2; });
    m_signals.setInterval(100);
    connect(&m_signals, &QTimer::timeout, this, [this] {
        const int s = pendingSignal.exchange(0);
        if (s && m_shown != (s == SIGUSR2)) {
            m_shown = s == SIGUSR2;
            emit shownChanged();
        }
    });
    m_signals.start();
}

Osk::~Osk()
{
    release();
    if (m_fd >= 0) {
        ioctl(m_fd, UI_DEV_DESTROY);
        ::close(m_fd);
    }
}

void Osk::emitKey(int code, int value)
{
    input_event ev[2] = {};
    ev[0].type = EV_KEY; ev[0].code = code; ev[0].value = value;
    ev[1].type = EV_SYN; ev[1].code = SYN_REPORT;
    (void)!::write(m_fd, ev, sizeof ev);
}

void Osk::press(const QString &key, bool shift, bool ctrl, bool alt)
{
    release();   // one key at a time
    static const auto chars = charKeys();
    int code = namedKeys.value(key, 0);
    if (!code && key.size() == 1 && chars.contains(key[0])) {
        code = chars[key[0]].first;
        shift = shift || chars[key[0]].second;
    }
    if (!code || m_fd < 0)
        return;
    // The tap focused us: the app gets sway's focus back before the key (Home's hotkeys do the same).
    if (!m_target.isEmpty())
        QProcess::execute("swaymsg", {QString("[app_id=\"^%1$\"] focus").arg(m_target)});
    if (ctrl) m_down << KEY_LEFTCTRL;
    if (alt) m_down << KEY_LEFTALT;
    if (shift) m_down << KEY_LEFTSHIFT;
    m_down << code;
    for (int k : m_down)
        emitKey(k, 1);
}

void Osk::release()
{
    for (auto it = m_down.rbegin(); it != m_down.rend(); ++it)
        emitKey(*it, 0);
    m_down.clear();
}
