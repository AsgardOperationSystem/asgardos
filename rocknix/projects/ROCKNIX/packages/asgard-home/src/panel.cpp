#include "panel.h"

Panel::Panel(QObject *parent) : QObject(parent)
{
    m_py.setProcessChannelMode(QProcess::ForwardedErrorChannel);   // its tracebacks go to our log
    connect(&m_py, &QProcess::readyReadStandardOutput, this, [this] {
        while (m_py.canReadLine()) {   // "<id>\t<json>"
            const QString line = QString::fromUtf8(m_py.readLine()).trimmed();
            QJSValue done = m_waiting.take(line.section('\t', 0, 0).toInt());
            if (done.isCallable())
                done.call({line.section('\t', 1)});
        }
    });
    m_py.start("python3", {qEnvironmentVariable("ASGARD_PANEL", "/usr/share/asgard/thor_panel.py"), "--serve"});
}

void Panel::call(const QString &command, const QString &value, const QJSValue &done)
{
    m_waiting.insert(++m_next, done);
    m_py.write(QString("%1\t%2\t%3\n").arg(m_next).arg(command, value).toUtf8());
}
