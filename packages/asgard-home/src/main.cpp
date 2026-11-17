#include <QDir>
#include <QFile>
#include <QMetaProperty>
#include <QTextStream>
#include <QGuiApplication>
#include <QQmlApplicationEngine>
#include <QNetworkAccessManager>
#include <QNetworkDiskCache>
#include <QQmlContext>
#include <QQmlNetworkAccessManagerFactory>
#include <QQuickItem>
#include <QQuickWindow>
#include <QPointerEvent>
#include <QTimer>
#include <csignal>
#include <cstdio>
#include <memory>
#include <sys/prctl.h>

#ifdef HAVE_LAYERSHELL
#include <LayerShellQt/window.h>
#endif

#include "achievements.h"
#include "backend.h"
#include "files.h"
#include "osk.h"
#include "music.h"
#include "panel.h"

// Images from the web (RA badges and icons) are cached on disk and served from there first: they never change,
// and the Trophies tab then opens without downloading them again (or offline).
class CachedNetwork : public QQmlNetworkAccessManagerFactory
{
    class Nam : public QNetworkAccessManager
    {
        using QNetworkAccessManager::QNetworkAccessManager;
        QNetworkReply *createRequest(Operation op, const QNetworkRequest &req, QIODevice *data) override
        {
            QNetworkRequest r(req);
            r.setAttribute(QNetworkRequest::CacheLoadControlAttribute, QNetworkRequest::PreferCache);
            return QNetworkAccessManager::createRequest(op, r, data);
        }
    };

public:
    QNetworkAccessManager *create(QObject *parent) override
    {
        auto *nam = new Nam(parent);
        auto *cache = new QNetworkDiskCache(nam);
        cache->setCacheDirectory(qEnvironmentVariable("ASGARD_ROOT") + "/storage/.cache/asgard-home/http");
        cache->setMaximumCacheSize(256 * 1024 * 1024);
        nam->setCache(cache);
        return nam;
    }
};

// ASGARD_DEBUG_INPUT: log every pointer/touch event Qt hands to a window, before Qt Quick sees it.
class InputLog : public QObject
{
    bool eventFilter(QObject *o, QEvent *e) override
    {
        if (e->isPointerEvent() && e->type() != QEvent::MouseMove && e->type() != QEvent::HoverMove)
            qInfo() << "input: qt" << e->type() << o << static_cast<QPointerEvent *>(e)->points().value(0).position();
        return false;
    }
};

// ASGARD_DUMP=<file> (with ASGARD_SHOT, for tests): what each window shows as text, and its root's plain properties, so a
// test can read the state after ASGARD_KEYS without comparing pictures. One "<window>\t<kind>\t<text>" line each.
static void dumpItem(QQuickItem *item, const QString &window, QTextStream &out)
{
    if (!item->isVisible() || item->opacity() <= 0)
        return;
    const QVariant text = item->property("text");
    if (text.isValid() && !text.toString().isEmpty())
        out << window << "\ttext\t" << text.toString().replace('\n', ' ') << "\n";
    for (QQuickItem *child : item->childItems())
        dumpItem(child, window, out);
}

static void dumpState(const QQmlApplicationEngine &engine)
{
    const QString path = qEnvironmentVariable("ASGARD_DUMP");
    QFile file(path);
    if (path.isEmpty() || !file.open(QIODevice::WriteOnly))
        return;
    QTextStream out(&file);
    for (QWindow *win : QGuiApplication::topLevelWindows())
        if (auto *w = qobject_cast<QQuickWindow *>(win))
            dumpItem(w->contentItem(), w->title(), out);
    for (QObject *root : engine.rootObjects()) {
        const QMetaObject *meta = root->metaObject();
        for (int i = meta->propertyOffset(); i < meta->propertyCount(); i++) {
            const QVariant value = meta->property(i).read(root);
            const int type = value.metaType().id();
            if (type == QMetaType::Bool || type == QMetaType::Int || type == QMetaType::Double || type == QMetaType::QString)
                out << root->objectName() << "\tprop\t" << meta->property(i).name() << "=" << value.toString() << "\n";
        }
    }
}

int main(int argc, char *argv[])
{
    // Screenshot mode (development): windows stay hidden, are rendered offscreen and saved as <prefix><title>.png.
    const QString shot = qEnvironmentVariable("ASGARD_SHOT");
    const QProcessEnvironment gameEnv = QProcessEnvironment::systemEnvironment();
    // ROCKNIX exports QT_QPA_PLATFORM=xcb on dual-screen SM8550 (for Azahar); the frontend is a native Wayland
    // client. Games get gameEnv, the environment from before this change.
    if (qEnvironmentVariableIsSet("WAYLAND_DISPLAY"))
        qputenv("QT_QPA_PLATFORM", "wayland");
    QGuiApplication app(argc, argv);
    InputLog inputLog;
    if (qEnvironmentVariableIsSet("ASGARD_DEBUG_INPUT"))
        app.installEventFilter(&inputLog);
    // Asgard Music (asgard-home --music [playlist.m3u], as the Music Player system's emulator): its own QML, a player
    // and the pad. No Backend: it owns Home's command FIFO and uinput keyboard, which the running Home already has.
    // Asgard Keyboard (asgard-home --osk <app_id>, Tools' touch keyboard): one window, no pad (the keys are the app's).
    const int oskArg = app.arguments().indexOf("--osk");
    if (oskArg >= 0) {
        Osk osk(oskArg + 1 < app.arguments().size() ? app.arguments().at(oskArg + 1) : QString());
        QQmlApplicationEngine engine;
        engine.rootContext()->setContextProperty("osk", &osk);
        engine.rootContext()->setContextProperty("shotMode", !shot.isEmpty());
        engine.load(QDir(qEnvironmentVariable("ASGARD_HOME_QML", "/usr/share/asgard-home/qml")).filePath("Osk.qml"));
        if (engine.rootObjects().isEmpty())
            return 1;
        if (!shot.isEmpty())
            QTimer::singleShot(qEnvironmentVariableIntValue("ASGARD_SHOT_MS") ?: 1500, [&] {
                for (QWindow *win : QGuiApplication::topLevelWindows())
                    if (auto *w = qobject_cast<QQuickWindow *>(win)) {
                        w->contentItem()->setSize(w->size());
                        w->grabWindow().save(shot + w->title() + ".png");
                    }
                dumpState(engine);
                QGuiApplication::quit();
            });
        return app.exec();
    }
    // Asgard Files (asgard-home --files, Tools > Files) the same way: its own QML, a Files backend and the pad.
    // Thor Panel (asgard-home --panel, the AYN button) too, with the pad grabbed: the game paused under it never sees it.
    // A game's text prompt (asgard-text-input --text-input, by thor_text_input.py) too, grabbed as well: the text goes to
    // stdout, exit 0; backed out, exit 1; failed, exit 2. It ends with its parent: left behind it would keep the grab.
    const int musicArg = app.arguments().indexOf("--music");
    const bool filesMode = app.arguments().contains("--files");
    const bool panelMode = app.arguments().contains("--panel");
    const bool textMode = app.arguments().contains("--text-input");
    if (textMode)
        prctl(PR_SET_PDEATHSIG, SIGTERM);
    if (musicArg >= 0 || filesMode || panelMode || textMode) {
        const bool musicMode = musicArg >= 0;
        std::unique_ptr<Music> music(musicMode ? new Music : nullptr);   // Music starts mpv: only for Asgard Music
        std::unique_ptr<Files> files(filesMode ? new Files : nullptr);
        std::unique_ptr<Panel> panel(panelMode ? new Panel : nullptr);
        Gamepad pad(!shot.isEmpty(), panelMode || textMode);
        const auto option = [&app](const QString &name) {
            for (const QString &a : app.arguments())
                if (a.startsWith("--" + name + "="))
                    return a.mid(name.size() + 3);
            return QString();
        };
        QQmlApplicationEngine engine;
        engine.rootContext()->setContextProperty("music", music.get());
        engine.rootContext()->setContextProperty("files", files.get());
        engine.rootContext()->setContextProperty("panel", panel.get());
        engine.rootContext()->setContextProperty("textInput", QVariantMap{
            {"title", option("title")}, {"initial", option("initial")}, {"accent", option("accent")},
            {"maxLength", option("max").toInt()}, {"minLength", option("min").toInt()},
            {"digits", app.arguments().contains("--digits")}, {"secret", app.arguments().contains("--secret")},
            {"noCancel", app.arguments().contains("--no-cancel")}});
        engine.rootContext()->setContextProperty("pad", &pad);
        engine.rootContext()->setContextProperty("shotMode", !shot.isEmpty());
        if (music && musicArg + 1 < app.arguments().size())
            music->load(app.arguments().at(musicArg + 1));
        engine.load(QDir(qEnvironmentVariable("ASGARD_HOME_QML", "/usr/share/asgard-home/qml"))
                        .filePath(musicMode ? "Music.qml" : filesMode ? "Files.qml"
                                  : textMode ? "TextInput.qml" : "Panel.qml"));
        if (engine.rootObjects().isEmpty())
            return textMode ? 2 : 1;
        if (!shot.isEmpty()) {   // as Home's screenshot mode below: replay ASGARD_KEYS, then save each window
            const QStringList keys = qEnvironmentVariable("ASGARD_KEYS").split(' ', Qt::SkipEmptyParts);
            for (int i = 0; i < keys.size(); i++)
                QTimer::singleShot(200 + 60 * i, &pad, [&pad, k = keys[i]] { emit pad.pressed(k); });
            QTimer::singleShot(200 + 60 * keys.size() + (qEnvironmentVariableIntValue("ASGARD_SHOT_MS") ?: 1500), [&] {
                for (QWindow *win : QGuiApplication::topLevelWindows())
                    if (auto *w = qobject_cast<QQuickWindow *>(win)) {
                        w->contentItem()->setSize(w->size());
                        w->grabWindow().save(shot + w->title() + ".png");
                    }
                dumpState(engine);
                QGuiApplication::quit();
            });
        }
        const int code = app.exec();
        if (textMode && code == 0 && shot.isEmpty()) {
            const QByteArray text = engine.rootObjects().first()->property("result").toString().toUtf8();
            fwrite(text.constData(), 1, size_t(text.size()), stdout);
            fflush(stdout);
        }
        return code;
    }
    Backend backend(gameEnv);
    // Screenshot runs ignore the physical pad (ASGARD_KEYS replays instead), unless a test gives one (ASGARD_INPUT).
    Gamepad pad(!shot.isEmpty() && !qEnvironmentVariableIsSet("ASGARD_INPUT"));
    Achievements achievements(&backend);
    QQmlApplicationEngine engine;  // after backend/pad: destroyed first, so QML never sees them gone
    CachedNetwork network;
    engine.setNetworkAccessManagerFactory(&network);
    engine.rootContext()->setContextProperty("backend", &backend);
    engine.rootContext()->setContextProperty("pad", &pad);
    engine.rootContext()->setContextProperty("achievements", &achievements);
    engine.rootContext()->setContextProperty("shotMode", !shot.isEmpty());
    engine.rootContext()->setContextProperty("debugInput", qEnvironmentVariableIsSet("ASGARD_DEBUG_INPUT"));
    // QML from disk, not resources: the source tree in development, /usr/share/asgard-home/qml when installed.
    const QString qml = qEnvironmentVariable("ASGARD_HOME_QML", "/usr/share/asgard-home/qml");
    engine.load(QDir(qml).filePath("Main.qml"));
    if (engine.rootObjects().isEmpty())
        return 1;
    // The windows hide while a game runs: keep their GL context and scene graph, so Home's in-game menu shows at once
    // (rebuilding them took ~1.2 s, and a second Home press meanwhile closed the menu as it appeared).
    for (QWindow *win : QGuiApplication::topLevelWindows())
        if (auto *w = qobject_cast<QQuickWindow *>(win)) {
            w->setPersistentGraphics(true);
            w->setPersistentSceneGraph(true);
        }
#ifdef HAVE_LAYERSHELL
    // The OSD is a layer-shell overlay: above fullscreen games, no focus, no input (before it's first shown).
    for (QWindow *win : QGuiApplication::topLevelWindows())
        if (win->objectName() == "osd" && shot.isEmpty()) {
            auto *ls = LayerShellQt::Window::get(win);
            ls->setScope("asgard-osd");
            ls->setLayer(LayerShellQt::Window::LayerOverlay);
            ls->setAnchors(LayerShellQt::Window::AnchorTop);
            ls->setExclusiveZone(-1);
            ls->setKeyboardInteractivity(LayerShellQt::Window::KeyboardInteractivityNone);
        }
#endif
    if (!shot.isEmpty()) {
        // A never-shown window's root item has no size; give it the window's now, so layouts (and which tiles count
        // as on screen) are right from the start, not only at grab time.
        for (QWindow *win : QGuiApplication::topLevelWindows())
            if (auto *w = qobject_cast<QQuickWindow *>(win))
                w->contentItem()->setSize(w->size());
        // ASGARD_KEYS="right right a": button presses replayed before the shot, to capture any state.
        const QStringList keys = qEnvironmentVariable("ASGARD_KEYS").split(' ', Qt::SkipEmptyParts);
        for (int i = 0; i < keys.size(); i++)
            QTimer::singleShot(200 + 60 * i, &pad, [&pad, k = keys[i]] { emit pad.pressed(k); });
        QTimer::singleShot(200 + 60 * keys.size() + (qEnvironmentVariableIntValue("ASGARD_SHOT_MS") ?: 1500), [&] {
            for (QWindow *win : QGuiApplication::topLevelWindows())
                if (auto *w = qobject_cast<QQuickWindow *>(win)) {
                    w->contentItem()->setSize(w->size());  // a never-shown window's root item has no size
                    // Saved at the window's logical size (1:1 with the Thor's panels) whatever the desktop scale.
                    w->grabWindow().scaled(w->size(), Qt::IgnoreAspectRatio, Qt::SmoothTransformation)
                        .save(shot + w->title().replace(' ', '_') + ".png");
                }
            dumpState(engine);
            app.quit();
        });
    }
    return app.exec();
}
