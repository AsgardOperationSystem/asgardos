#include "achievements.h"
#include "backend.h"

#include <QDateTime>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QNetworkReply>
#include <QSet>
#include <QThread>
#include <QUrlQuery>
#include <algorithm>

extern "C" {
#include "rc_consoles.h"
#include "rc_hash.h"
}

static const char *API = "https://retroachievements.org/API/";
static const char *MEDIA = "https://media.retroachievements.org";
static const QByteArray USER_AGENT = "AsgardHome/0.1 (+https://github.com/AsgardOperationSystem/asgardos)";

int Achievements::consoleFor(const QString &s)
{
    static const QHash<QString, int> map = {
        {"nes", RC_CONSOLE_NINTENDO}, {"famicom", RC_CONSOLE_NINTENDO}, {"fds", RC_CONSOLE_FAMICOM_DISK_SYSTEM},
        {"snes", RC_CONSOLE_SUPER_NINTENDO}, {"sfc", RC_CONSOLE_SUPER_NINTENDO}, {"n64", RC_CONSOLE_NINTENDO_64},
        {"gb", RC_CONSOLE_GAMEBOY}, {"gbc", RC_CONSOLE_GAMEBOY_COLOR}, {"gba", RC_CONSOLE_GAMEBOY_ADVANCE},
        {"nds", RC_CONSOLE_NINTENDO_DS}, {"3ds", RC_CONSOLE_NINTENDO_3DS}, {"gamecube", RC_CONSOLE_GAMECUBE},
        {"wii", RC_CONSOLE_WII}, {"virtualboy", RC_CONSOLE_VIRTUAL_BOY}, {"pokemini", RC_CONSOLE_POKEMON_MINI},
        {"psx", RC_CONSOLE_PLAYSTATION}, {"ps2", RC_CONSOLE_PLAYSTATION_2}, {"psp", RC_CONSOLE_PSP},
        {"megadrive", RC_CONSOLE_MEGA_DRIVE}, {"genesis", RC_CONSOLE_MEGA_DRIVE}, {"mastersystem", RC_CONSOLE_MASTER_SYSTEM},
        {"gamegear", RC_CONSOLE_GAME_GEAR}, {"segacd", RC_CONSOLE_SEGA_CD}, {"sega32x", RC_CONSOLE_SEGA_32X},
        {"saturn", RC_CONSOLE_SATURN}, {"dreamcast", RC_CONSOLE_DREAMCAST}, {"sg-1000", RC_CONSOLE_SG1000},
        {"pcengine", RC_CONSOLE_PC_ENGINE}, {"pcenginecd", RC_CONSOLE_PC_ENGINE_CD}, {"atari2600", RC_CONSOLE_ATARI_2600},
        {"atari7800", RC_CONSOLE_ATARI_7800}, {"atarilynx", RC_CONSOLE_ATARI_LYNX}, {"ngp", RC_CONSOLE_NEOGEO_POCKET},
        {"ngpc", RC_CONSOLE_NEOGEO_POCKET}, {"wonderswan", RC_CONSOLE_WONDERSWAN}, {"wonderswancolor", RC_CONSOLE_WONDERSWAN},
        {"arcade", RC_CONSOLE_ARCADE}, {"colecovision", RC_CONSOLE_COLECOVISION}, {"msx", RC_CONSOLE_MSX},
    };
    return map.value(s.toLower());
}

// system.cfg key=value (the asgard.yml layer writes there too).
static QString setting(const QString &root, const QString &key)
{
    QFile f(root + "/storage/.config/system/configs/system.cfg");
    if (f.open(QIODevice::ReadOnly))
        while (!f.atEnd()) {
            const QString line = QString::fromUtf8(f.readLine()).trimmed();
            if (line.startsWith(key + "="))
                return line.mid(key.size() + 1);
        }
    return {};
}

Achievements::Achievements(Backend *backend, QObject *parent)
    : QObject(parent), m_backend(backend), m_root(qEnvironmentVariable("ASGARD_ROOT")),
      m_user(setting(m_root, "global.retroachievements.username")),
      m_key(setting(m_root, "global.retroachievements.webapikey"))
{
    QDir().mkpath(cache(""));
    refresh();
}

QString Achievements::cache(const QString &name) const { return m_root + "/storage/.config/asgard/ra/" + name; }

void Achievements::setStatus(const QString &s)
{
    if (s != m_status) {
        m_status = s;
        emit statusChanged();
    }
}

// GET <API><endpoint>?<query>&y=<key>, cached in cacheFile for maxAgeHours. A failed request falls back to a
// stale cache (offline). The key is never logged.
void Achievements::fetch(const QString &endpoint, const QString &query, const QString &cacheFile, int maxAgeHours,
                         std::function<void(const QByteArray &)> done, bool staleFirst)
{
    QFile cached(cache(cacheFile));
    const QFileInfo fi(cached);
    const bool fresh = fi.exists() && fi.lastModified().secsTo(QDateTime::currentDateTime()) < maxAgeHours * 3600;
    if ((fresh || (staleFirst && fi.exists())) && cached.open(QIODevice::ReadOnly)) {
        const QByteArray data = cached.readAll();
        QMetaObject::invokeMethod(this, [done, data] { done(data); }, Qt::QueuedConnection);
        if (fresh)
            return;   // staleFirst + stale: answer from the cache now, refresh below (done runs again)
    }
    m_queue << [this, endpoint, query, cacheFile, done] {
        QUrl url(QString(API) + endpoint);
        QUrlQuery q(query);
        q.addQueryItem("y", m_key);
        url.setQuery(q);
        QNetworkRequest req(url);
        req.setHeader(QNetworkRequest::UserAgentHeader, USER_AGENT);
        req.setTransferTimeout(60000);
        QNetworkReply *reply = m_net.get(req);
        connect(reply, &QNetworkReply::finished, this, [this, reply, endpoint, cacheFile, done] {
            reply->deleteLater();
            QByteArray data = reply->readAll();
            const int http = reply->attribute(QNetworkRequest::HttpStatusCodeAttribute).toInt();
            if (reply->error() == QNetworkReply::NoError && !data.isEmpty()) {
                QFile out(cache(cacheFile));
                if (out.open(QIODevice::WriteOnly))
                    out.write(data);
            } else {
                // Never log the URL: it carries the key.
                qWarning("trophies: %s failed (HTTP %d, %s)", qPrintable(endpoint), http, qPrintable(reply->errorString().section('?', 0, 0)));
                QFile stale(cache(cacheFile));
                data = stale.open(QIODevice::ReadOnly) ? stale.readAll() : QByteArray();
                if (data.isEmpty())
                    setStatus(http == 401 || http == 403 ? "RetroAchievements refused the web API key" : "Can't reach RetroAchievements");
            }
            done(data);
            m_busy = false;
            next();
        });
    };
    next();
}

void Achievements::next()
{
    if (m_busy || m_queue.isEmpty())
        return;
    m_busy = true;
    m_queue.takeFirst()();
}

// 1. game lists (with hashes) of the consoles we have games for; 2. hash only ROMs of consoles that have sets;
// 3. the user's progress; 4. match.
void Achievements::refresh()
{
    // Re-read: Settings > Achievements can change the web API key at runtime.
    m_user = setting(m_root, "global.retroachievements.username");
    m_key = setting(m_root, "global.retroachievements.webapikey");
    if (m_user.isEmpty() || m_key.isEmpty()) {
        setStatus("Add your RetroAchievements username and web API key in Settings > Achievements");
        return;
    }
    QSet<int> consoles;
    for (const QVariantMap &g : m_backend->allGames())
        if (int c = consoleFor(g["sys"].toString()))
            consoles << c;
    m_pending = consoles.size() + 1;
    auto step = [this] {
        if (--m_pending)
            return;
        // Hash ROMs whose console has at least one set, on a worker thread (big ISOs take a while).
        QSet<int> withSets;
        for (auto it = m_lists.cbegin(); it != m_lists.cend(); ++it)
            if (!it->toArray().isEmpty())
                withSets << it.key();
        QList<QPair<QString, int>> todo;
        for (const QVariantMap &g : m_backend->allGames())
            if (int c = consoleFor(g["sys"].toString()); withSets.contains(c))
                todo << qMakePair(g["path"].toString(), c);
        const QString root = m_root, cacheFile = cache("hashes.json");
        QThread *t = QThread::create([this, todo, root, cacheFile] {
            QFile f(cacheFile);
            QJsonObject known = f.open(QIODevice::ReadOnly) ? QJsonDocument::fromJson(f.readAll()).object() : QJsonObject();
            f.close();
            QHash<QString, QString> out;
            for (const auto &[path, console] : todo) {
                const QFileInfo fi(root + path);
                const QString stamp = QString::number(fi.size()) + ":" + QString::number(fi.lastModified().toSecsSinceEpoch());
                QJsonObject e = known.value(path).toObject();
                if (e.value("stamp").toString() != stamp) {
                    char hash[33] = {0};
                    e = {{"stamp", stamp}, {"hash", rc_hash_generate_from_file(hash, console, qPrintable(root + path)) ? QString(hash) : ""}};
                    known[path] = e;
                }
                if (!e.value("hash").toString().isEmpty())
                    out[path] = e.value("hash").toString();
            }
            if (f.open(QIODevice::WriteOnly))
                f.write(QJsonDocument(known).toJson(QJsonDocument::Compact));
            QMetaObject::invokeMethod(this, [this, out] { hashed(out); }, Qt::QueuedConnection);
        });
        connect(t, &QThread::finished, t, &QObject::deleteLater);
        t->start(QThread::LowPriority);
    };
    for (int c : consoles)
        fetch("API_GetGameList.php", QString("i=%1&h=1&f=1").arg(c), QString("console-%1.json").arg(c), 24 * 7,
              [this, c, step](const QByteArray &data) { m_lists[c] = QJsonDocument::fromJson(data).array(); step(); });
    fetch("API_GetUserCompletionProgress.php", "u=" + QUrl::toPercentEncoding(m_user) + "&c=500", "progress.json", 1,
          [this, step](const QByteArray &data) {
              m_progress.clear();
              for (const QJsonValue &v : QJsonDocument::fromJson(data).object().value("Results").toArray())
                  m_progress[v["GameID"].toInt()] = v.toObject().toVariantMap();
              step();
          });
}

void Achievements::hashed(const QHash<QString, QString> &hashes)
{
    m_hashes = hashes;
    match();
}

void Achievements::match()
{
    QHash<QString, QJsonObject> byHash;   // RA hash -> RA game (lowercase md5)
    for (const QJsonValue &list : std::as_const(m_lists))
        for (const QJsonValue &g : list.toArray())
            for (const QJsonValue &h : g["Hashes"].toArray())
                byHash[h.toString().toLower()] = g.toObject();
    QList<QVariantMap> found;
    for (const QVariantMap &g : m_backend->allGames()) {
        const QJsonObject ra = byHash.value(m_hashes.value(g["path"].toString()));
        if (ra.isEmpty())
            continue;
        const int id = ra["ID"].toInt();
        const QVariantMap p = m_progress.value(id);
        QVariantMap e;
        e["game"] = g;
        e["raId"] = id;
        e["title"] = ra["Title"].toString();
        e["icon"] = QString(MEDIA) + ra["ImageIcon"].toString();
        e["total"] = ra["NumAchievements"].toInt();
        e["points"] = ra["Points"].toInt();
        e["earned"] = std::max(p.value("NumAwarded").toInt(), p.value("NumAwardedHardcore").toInt());
        e["award"] = p.value("HighestAwardKind").toString();   // "mastered", "completed", "beaten-hardcore", ...
        e["recent"] = p.value("MostRecentAwardedDate").toString();
        found << e;
    }
    // Games with progress first (most recent unlock on top), then the rest by name.
    std::sort(found.begin(), found.end(), [](const QVariantMap &a, const QVariantMap &b) {
        if ((a["earned"].toInt() > 0) != (b["earned"].toInt() > 0))
            return a["earned"].toInt() > 0;
        if (a["recent"] != b["recent"])
            return a["recent"].toString() > b["recent"].toString();
        return a["title"].toString().compare(b["title"].toString(), Qt::CaseInsensitive) < 0;
    });
    m_games.clear();
    for (const QVariantMap &e : found)
        m_games << e;
    qInfo("trophies: %lld of %lld hashed games have RetroAchievements sets", qsizetype(m_games.size()), qsizetype(m_hashes.size()));
    if (m_status.startsWith("Add your") || m_games.size())
        setStatus(m_games.isEmpty() ? "No games with RetroAchievements found" : "");
    emit gamesChanged();
}

void Achievements::details(int raId)
{
    fetch("API_GetGameInfoAndUserProgress.php", QString("g=%1&u=%2").arg(raId).arg(QString(QUrl::toPercentEncoding(m_user))),
          QString("game-%1.json").arg(raId), 1, [this, raId](const QByteArray &data) {
              if (data.isEmpty())
                  return;
              const QJsonObject o = QJsonDocument::fromJson(data).object();
              QVariantList list;
              for (const QJsonValue &a : o["Achievements"].toObject()) {
                  const QString badge = a["BadgeName"].toString();
                  const QString date = a["DateEarnedHardcore"].toString().isEmpty() ? a["DateEarned"].toString()
                                                                                       : a["DateEarnedHardcore"].toString();
                  list << QVariantMap{{"title", a["Title"].toString()}, {"description", a["Description"].toString()},
                                      {"points", a["Points"].toInt()}, {"earned", !date.isEmpty()}, {"date", date.left(10)},
                                      {"hardcore", !a["DateEarnedHardcore"].toString().isEmpty()},
                                      {"order", a["DisplayOrder"].toInt()},
                                      {"badge", QString("%1/Badge/%2.png").arg(MEDIA, badge)},
                                      {"badgeLocked", QString("%1/Badge/%2_lock.png").arg(MEDIA, badge)}};
              }
              // Unlocked first (newest first), then locked in the set's display order.
              std::sort(list.begin(), list.end(), [](const QVariant &x, const QVariant &y) {
                  const QVariantMap a = x.toMap(), b = y.toMap();
                  if (a["earned"].toBool() != b["earned"].toBool())
                      return a["earned"].toBool();
                  if (a["earned"].toBool())
                      return a["date"].toString() > b["date"].toString();
                  return a["order"].toInt() < b["order"].toInt();
              });
              emit detailsReady(raId, {{"achievements", list}, {"completion", o["UserCompletionHardcore"].toString()},
                                       {"boxArt", QString(MEDIA) + o["ImageBoxArt"].toString()}});
          }, true);
}
