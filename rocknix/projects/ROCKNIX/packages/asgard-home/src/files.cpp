#include "files.h"

#include <QDateTime>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QStorageInfo>
#include <QTextStream>

static QString human(qint64 b)
{
    const char *units[] = {"B", "KB", "MB", "GB", "TB"};
    double v = b;
    int u = 0;
    while (v >= 1000 && u < 4) { v /= 1000; u++; }
    return QString::number(v, 'f', v < 10 && u ? 1 : 0) + " " + units[u];
}

// The last line of du -sbc: the total, in bytes.
static qint64 duTotal(QProcess *p)
{
    const QList<QByteArray> lines = p->readAllStandardOutput().trimmed().split('\n');
    return lines.isEmpty() ? 0 : lines.last().split('\t').first().toLongLong();
}

Files::Files(QObject *parent) : QObject(parent), m_root(qEnvironmentVariable("ASGARD_ROOT"))
{
    m_poll.setInterval(800);
    connect(&m_poll, &QTimer::timeout, this, [this] {
        if (m_du || m_measure.isEmpty())
            return;
        m_du = new QProcess(this);
        connect(m_du, &QProcess::finished, this, [this] {
            const qint64 done = duTotal(m_du);
            m_du->deleteLater();
            m_du = nullptr;
            if (m_total > 0 && !m_busy.isEmpty()) {
                m_progress = qMin(1.0, double(done) / m_total);
                emit busyChanged();
            }
        });
        m_du->start("du", QStringList{"-sbc", "--"} + m_measure);
    });
    const QVariantList p = places();
    open(p.isEmpty() ? "/" : p.first().toMap()["path"].toString());
}

Files::~Files()
{
    if (m_op)
        m_op->kill();   // a half-done copy stays half done; nothing runs on behind the app's back
}

QVariantList Files::places() const
{
    QVariantList out;
    for (const auto &[name, p] : {std::pair{"SD card", "/storage/games-external"}, {"ROMs", "/storage/roms"},
                                  {"Thor", "/storage"}})
        if (QFileInfo(host(p)).isDir())
            out << QVariantMap{{"name", name}, {"path", p}};
    return out;
}

void Files::open(const QString &path)
{
    const QString p = QDir::cleanPath(path.isEmpty() ? "/" : path);
    QDir d(host(p));
    if (!d.exists() || !d.isReadable()) {
        fail("Can't open " + p);
        return;
    }
    QDir::Filters f = QDir::AllEntries | QDir::NoDotAndDotDot | QDir::System;
    if (m_hidden)
        f |= QDir::Hidden;
    m_entries.clear();
    for (const QFileInfo &fi : d.entryInfoList(f, QDir::DirsFirst | QDir::Name | QDir::IgnoreCase))
        m_entries << QVariantMap{{"name", fi.fileName()}, {"dir", fi.isDir()}, {"size", fi.isDir() ? -1 : fi.size()},
                                 {"modified", fi.lastModified().toMSecsSinceEpoch()}};
    const QStorageInfo st(d);
    m_space = st.isValid() ? human(st.bytesAvailable()) + " free of " + human(st.bytesTotal()) : QString();
    m_path = p;
    emit changed();
}

void Files::up()
{
    if (m_path != "/")
        open(QFileInfo(m_path).path());
}

void Files::refresh() { open(m_path); }

void Files::toggleHidden()
{
    m_hidden = !m_hidden;
    refresh();
}

void Files::copy(const QStringList &names, bool cut)
{
    m_clip.clear();
    for (const QString &n : names)
        m_clip << host(m_path) + "/" + n;
    m_clipCut = cut;
    emit clipChanged();
}

// "name", else "name 2", "name 3"... (before the extension for files)
QString Files::unique(const QString &dir, const QString &name) const
{
    if (!QFileInfo::exists(dir + "/" + name))
        return dir + "/" + name;
    const QFileInfo fi(name);
    const bool ext = !QFileInfo(dir + "/" + name).isDir() && !fi.suffix().isEmpty() && !fi.completeBaseName().isEmpty();
    const QString base = ext ? fi.completeBaseName() : name, suffix = ext ? "." + fi.suffix() : QString();
    for (int i = 2;; i++)
        if (!QFileInfo::exists(dir + "/" + base + " " + QString::number(i) + suffix))
            return dir + "/" + base + " " + QString::number(i) + suffix;
}

void Files::paste()
{
    if (m_clip.isEmpty() || !m_busy.isEmpty())
        return;
    const QString dest = host(m_path);
    QStringList args{m_clipCut ? "mv" : "cp"}, sources, targets;
    for (const QString &src : m_clip) {
        if (dest == src || dest.startsWith(src + "/")) {
            fail("A folder can't go inside itself");
            return;
        }
        if (m_clipCut && QFileInfo(src).path() == dest)
            continue;   // moved onto itself: nothing to do
        const QString to = unique(dest, QFileInfo(src).fileName());
        args << src << to;
        sources << src;
        targets << to;
    }
    if (sources.isEmpty()) {
        m_clip.clear();
        emit clipChanged();
        return;
    }
    // cp -R, not -a: the SD card is exFAT (no owners or modes to keep, and failing to keep them is an error)
    const QString script = "m=$1; shift; while [ $# -gt 1 ]; do "
                           "if [ \"$m\" = mv ]; then mv -- \"$1\" \"$2\"; else cp -R -- \"$1\" \"$2\"; fi || exit 1; "
                           "shift 2; done";
    const int n = sources.size();
    run(QString(m_clipCut ? "Moving " : "Copying ") + QString::number(n) + (n == 1 ? " item" : " items"), script, args,
        targets, -1);
    // The total to measure progress against, in the background too (du over a big folder takes a while)
    auto *sizer = new QProcess(this);
    connect(sizer, &QProcess::finished, this, [this, sizer] { m_total = duTotal(sizer); sizer->deleteLater(); });
    sizer->start("du", QStringList{"-sbc", "--"} + sources);
    if (m_clipCut) {
        m_clip.clear();
        emit clipChanged();
    }
}

void Files::remove(const QStringList &names)
{
    if (names.isEmpty() || !m_busy.isEmpty())
        return;
    QStringList paths;
    for (const QString &n : names)
        paths << host(m_path) + "/" + n;
    const int n = paths.size();
    run("Deleting " + QString::number(n) + (n == 1 ? " item" : " items"), "rm -rf -- \"$@\"", paths, {}, 0);
}

void Files::run(const QString &label, const QString &script, const QStringList &args, const QStringList &measure,
                qint64 total)
{
    m_busy = label;
    m_progress = -1;
    m_total = total;
    m_measure = measure;
    m_message.clear();
    emit messageChanged();
    emit busyChanged();
    m_op = new QProcess(this);
    connect(m_op, &QProcess::finished, this, [this](int code, QProcess::ExitStatus status) {
        const QString err = QString::fromUtf8(m_op->readAllStandardError()).trimmed().section('\n', -1);
        m_op->deleteLater();
        m_op = nullptr;
        m_poll.stop();
        m_measure.clear();
        m_busy.clear();
        emit busyChanged();
        if (status != QProcess::NormalExit)
            fail("Stopped");
        else if (code != 0)
            fail(err.isEmpty() ? "It didn't work" : err);
        refresh();
    });
    m_op->start("/bin/sh", QStringList{"-c", script, "sh"} + args);
    if (!measure.isEmpty())
        m_poll.start();
}

void Files::cancel()
{
    if (m_op)
        m_op->kill();
}

bool Files::rename(const QString &from, const QString &to)
{
    if (to.isEmpty() || to.contains('/') || to == from)
        return false;
    const QString dir = host(m_path);
    if (QFileInfo::exists(dir + "/" + to)) {
        fail(to + " already exists");
        return false;
    }
    if (!QDir(dir).rename(from, to)) {
        fail("Couldn't rename " + from);
        return false;
    }
    refresh();
    return true;
}

bool Files::makeDir(const QString &name)
{
    if (name.isEmpty() || name.contains('/'))
        return false;
    if (!QDir(host(m_path)).mkdir(name)) {
        fail("Couldn't make " + name);
        return false;
    }
    refresh();
    return true;
}

QString Files::setting(const QString &key, const QString &fallback) const
{
    QFile f(host("/storage/.config/system/configs/system.cfg"));
    QString value = fallback;
    if (f.open(QIODevice::ReadOnly | QIODevice::Text)) {
        QTextStream in(&f);
        while (!in.atEnd()) {   // the last one wins, as in ROCKNIX's get_setting
            const QString line = in.readLine();
            if (line.startsWith(key + "=") && line.size() > key.size() + 1)
                value = line.mid(key.size() + 1);
        }
    }
    return value;
}
