#pragma once

#include <QObject>
#include <QProcess>
#include <QStringList>
#include <QTimer>
#include <QVariantList>

// Asgard Files (asgard-home --files, qml/Files.qml): one folder at a time, a clipboard of paths and one file operation
// at a time (copy, move, delete) run by cp / mv / rm in the background, so a big copy never freezes the UI. Progress:
// the bytes at the destination (du, polled) against the sources' total. Paths in QML are the Thor's (no ASGARD_ROOT).
class Files : public QObject
{
    Q_OBJECT
    Q_PROPERTY(QString path READ path NOTIFY changed)
    Q_PROPERTY(QVariantList entries READ entries NOTIFY changed)       // [{name, dir, size, modified}] folders first
    Q_PROPERTY(QString space READ space NOTIFY changed)                // "120 GB free of 465 GB"
    Q_PROPERTY(QVariantList places READ places CONSTANT)               // [{name, path}]
    Q_PROPERTY(bool hidden READ hidden NOTIFY changed)                 // dotfiles shown
    Q_PROPERTY(int clipCount READ clipCount NOTIFY clipChanged)
    Q_PROPERTY(bool clipCut READ clipCut NOTIFY clipChanged)           // the clipboard moves instead of copying
    Q_PROPERTY(QString busy READ busy NOTIFY busyChanged)              // "Copying 3 items" while an operation runs
    Q_PROPERTY(double progress READ progress NOTIFY busyChanged)       // 0..1, -1 when unknown
    Q_PROPERTY(QString message READ message NOTIFY messageChanged)     // the last error, "" when fine

public:
    explicit Files(QObject *parent = nullptr);
    ~Files() override;

    Q_INVOKABLE void open(const QString &path);     // a folder
    Q_INVOKABLE void up();
    Q_INVOKABLE void refresh();
    Q_INVOKABLE void toggleHidden();
    Q_INVOKABLE void copy(const QStringList &names, bool cut);   // names in the current folder
    Q_INVOKABLE void paste();                       // into the current folder
    Q_INVOKABLE void remove(const QStringList &names);
    Q_INVOKABLE bool rename(const QString &from, const QString &to);
    Q_INVOKABLE bool makeDir(const QString &name);
    Q_INVOKABLE void cancel();
    Q_INVOKABLE QString setting(const QString &key, const QString &fallback = QString()) const;   // system.cfg

    QString path() const { return m_path; }
    QVariantList entries() const { return m_entries; }
    QString space() const { return m_space; }
    QVariantList places() const;
    bool hidden() const { return m_hidden; }
    int clipCount() const { return m_clip.size(); }
    bool clipCut() const { return m_clipCut; }
    QString busy() const { return m_busy; }
    double progress() const { return m_progress; }
    QString message() const { return m_message; }

signals:
    void changed();
    void clipChanged();
    void busyChanged();
    void messageChanged();

private:
    QString host(const QString &p) const { return m_root + p; }   // ASGARD_ROOT: the desktop dev fixture
    void run(const QString &label, const QString &script, const QStringList &args, const QStringList &measure, qint64 total);
    void fail(const QString &m) { m_message = m; emit messageChanged(); }
    QString unique(const QString &dir, const QString &name) const;

    QString m_root, m_path, m_space, m_busy, m_message;
    QVariantList m_entries;
    QStringList m_clip;                 // full Thor paths
    bool m_clipCut = false, m_hidden = false;
    double m_progress = -1;
    qint64 m_total = 0;
    QStringList m_measure;              // destination paths du sums while copying
    QProcess *m_op = nullptr, *m_du = nullptr;
    QTimer m_poll;
};
