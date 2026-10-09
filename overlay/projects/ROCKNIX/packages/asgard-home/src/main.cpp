#include <QDir>
#include <QGuiApplication>
#include <QQmlApplicationEngine>
#include <QQmlContext>
#include <QQuickItem>
#include <QQuickWindow>
#include <QTimer>

#include "backend.h"

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
    Backend backend(gameEnv);
    Gamepad pad(!shot.isEmpty());  // screenshot runs ignore the physical pad (ASGARD_KEYS replays instead)
    QQmlApplicationEngine engine;  // after backend/pad: destroyed first, so QML never sees them gone
    engine.rootContext()->setContextProperty("backend", &backend);
    engine.rootContext()->setContextProperty("pad", &pad);
    engine.rootContext()->setContextProperty("shotMode", !shot.isEmpty());
    // QML from disk, not resources: the source tree in development, /usr/share/asgard-home/qml when installed.
    const QString qml = qEnvironmentVariable("ASGARD_HOME_QML", "/usr/share/asgard-home/qml");
    engine.load(QDir(qml).filePath("Main.qml"));
    if (engine.rootObjects().isEmpty())
        return 1;
    if (!shot.isEmpty()) {
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
            app.quit();
        });
    }
    return app.exec();
}
