#pragma once
#include <QHash>
#include <QJsonValue>
#include <functional>
#include <QNetworkAccessManager>
#include <QObject>
#include <QVariant>

class Backend;

// RetroAchievements for the Trophies tab, through RA's Web API (needs the user's web API key):
// local ROMs hashed the way RA identifies games (rcheevos), matched against each console's game list,
// progress per game. Everything is cached under /storage/.config/asgard/ra so the tab works offline.
class Achievements : public QObject
{
    Q_OBJECT
    Q_PROPERTY(QVariantList games READ games NOTIFY gamesChanged)    // local games with an RA set + progress
    Q_PROPERTY(QString status READ status NOTIFY statusChanged)      // empty when all is well
    Q_PROPERTY(QString user READ user CONSTANT)

public:
    Achievements(Backend *backend, QObject *parent = nullptr);
    QVariantList games() const { return m_games; }
    QString status() const { return m_status; }
    QString user() const { return m_user; }

    Q_INVOKABLE void refresh();
    Q_INVOKABLE void details(int raId);   // -> detailsReady(raId, {achievements: [...], ...})

    static int consoleFor(const QString &system);   // ROCKNIX system name -> RA console id (0 = none)

signals:
    void gamesChanged();
    void statusChanged();
    void detailsReady(int raId, const QVariantMap &details);

private:
    void setStatus(const QString &s);
    void hashed(const QHash<QString, QString> &hashes);
    void match();
    QString cache(const QString &name) const;
    void fetch(const QString &endpoint, const QString &query, const QString &cacheFile, int maxAgeHours,
               std::function<void(const QByteArray &)> done);

    Backend *m_backend;
    QNetworkAccessManager m_net;
    QString m_root, m_user, m_key;
    QHash<QString, QString> m_hashes;               // ROM path -> RA hash
    QHash<int, QJsonValue> m_lists;                 // console id -> API_GetGameList (with hashes)
    QHash<int, QVariantMap> m_progress;             // RA game id -> the user's completion progress
    QVariantList m_games;
    QString m_status;
    int m_pending = 0;
    QList<std::function<void()>> m_queue;          // RA requests go out one at a time (RA throttles bursts)
    bool m_busy = false;
    void next();
};
