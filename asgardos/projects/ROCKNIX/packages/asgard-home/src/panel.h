#pragma once

#include <QHash>
#include <QJSValue>
#include <QObject>
#include <QProcess>

// Thor Panel (asgard-panel --panel, qml/Panel.qml): the AYN button's quick panel. The hardware side stays in Python:
// one `thor_panel.py --serve` for the panel's lifetime (ASGARD_PANEL overrides its path), asked one line at a time;
// each answer is JSON, handed to the QML callback as text.
class Panel : public QObject
{
    Q_OBJECT

public:
    explicit Panel(QObject *parent = nullptr);
    Q_INVOKABLE void call(const QString &command, const QString &value, const QJSValue &done);   // done(json)

private:
    QProcess m_py;
    QHash<int, QJSValue> m_waiting;
    int m_next = 0;
};
