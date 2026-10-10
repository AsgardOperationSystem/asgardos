#!/usr/bin/env python3
"""steam-art: art and details for the Steam games in Asgard Home's Steam system (the .desktop files Steam writes).

Cover (library_600x900, 2x if there is one), logo (marquee) and a screenshot from Steam's public CDN, and the name,
description, developer, year and genre from the store's appdetails API, into ES-DE's downloaded_media/steam and
gamelists/steam/gamelist.xml. Files already there are kept. start_steam_arm64.sh runs it on every Steam start.
"""
import datetime
import json
import os
import re
import sys
import urllib.request
from xml.sax.saxutils import escape

APPS = "/storage/.local/share/applications"
MEDIA = "/storage/ES-DE/downloaded_media/steam"
GAMELIST = "/storage/ES-DE/gamelists/steam/gamelist.xml"
CDN = "https://shared.cloudflare.steamstatic.com/store_item_assets/steam/apps/{}/{}"
THEME_ART = "/usr/share/themes/es-theme-art-book-next/_inc/systems/artwork-default/steam.png"


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "asgard-steam-art"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read()


def save(url, path):
    if os.path.exists(path):
        return True
    try:
        data = get(url)
    except Exception:
        return False
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + ".part", "wb") as f:
        f.write(data)
    os.replace(path + ".part", path)
    return True


def release(date):
    """'24 Feb, 2017' / 'Feb 24, 2017' -> ES-DE's 20170224T000000."""
    for fmt in ("%d %b, %Y", "%b %d, %Y", "%Y"):
        try:
            return datetime.datetime.strptime(date, fmt).strftime("%Y%m%dT000000")
        except ValueError:
            pass
    return ""


def games():
    """[(stem, appid)] from the .desktop files with a steam://rungameid/ link."""
    out = []
    for f in sorted(os.listdir(APPS)):
        if not f.endswith(".desktop"):
            continue
        m = re.search(r"steam://rungameid/(\d+)", open(os.path.join(APPS, f), errors="replace").read())
        if m:
            out.append((f[:-len(".desktop")], m.group(1)))
    return out


def main():
    # Steam itself (Steam.desktop, Big Picture) has no store page: the theme's Steam artwork as its cover.
    entries = [{"path": "./Steam.desktop", "name": "Steam",
                "desc": "Steam in Big Picture mode: store, library, downloads and settings."}]
    if os.path.exists(THEME_ART) and not os.path.exists(f"{MEDIA}/covers/Steam.png"):
        os.makedirs(f"{MEDIA}/covers", exist_ok=True)
        os.symlink(THEME_ART, f"{MEDIA}/covers/Steam.png")
    # Other PC apps (no Steam link, e.g. Gen1 Recomp): their own Name and Comment; art is left to whoever added them.
    for f in sorted(os.listdir(APPS)):
        text = open(os.path.join(APPS, f), errors="replace").read() if f.endswith(".desktop") else ""
        if f != "Steam.desktop" and text and "steam://" not in text:
            field = lambda k: (re.search(rf"^{k}=(.*)$", text, re.M) or [None, ""])[1].strip()
            entries.append({"path": f"./{f}", "name": field("Name") or f[:-8], "desc": field("Comment")})
    for stem, appid in games():
        try:
            info = json.loads(get(f"https://store.steampowered.com/api/appdetails?appids={appid}&l=english"))
            d = info.get(appid, {}).get("data", {}) if info.get(appid, {}).get("success") else {}
        except Exception as e:
            print(f"{stem}: no store details ({e})", file=sys.stderr)
            d = {}
        cover = any(save(CDN.format(appid, art), f"{MEDIA}/covers/{stem}.jpg")
                    for art in ("library_600x900_2x.jpg", "library_600x900.jpg", "header.jpg"))
        save(CDN.format(appid, "logo.png"), f"{MEDIA}/marquees/{stem}.png")
        shots = d.get("screenshots") or []
        if shots:
            save(shots[0]["path_full"].split("?")[0], f"{MEDIA}/screenshots/{stem}.jpg")
        else:
            save(CDN.format(appid, "library_hero.jpg"), f"{MEDIA}/screenshots/{stem}.jpg")
        print(f"{stem} ({appid}): {'art' if cover else 'no cover'}, {'details' if d else 'no details'}")
        e = {"path": f"./{stem}.desktop", "name": d.get("name") or stem}
        if d:
            e["desc"] = re.sub(r"<[^>]+>", "", d.get("short_description", "")).strip()
            e["developer"] = ", ".join(d.get("developers") or [])
            e["publisher"] = ", ".join(d.get("publishers") or [])
            e["releasedate"] = release(d.get("release_date", {}).get("date", ""))
            e["genre"] = ", ".join(g["description"] for g in (d.get("genres") or [])[:2])
        entries.append(e)

    os.makedirs(os.path.dirname(GAMELIST), exist_ok=True)
    with open(GAMELIST + ".part", "w") as f:
        f.write('<?xml version="1.0"?>\n<gameList>\n')
        for e in entries:
            f.write("\t<game>\n" + "".join(f"\t\t<{k}>{escape(v)}</{k}>\n" for k, v in e.items() if v) + "\t</game>\n")
        f.write("</gameList>\n")
    os.replace(GAMELIST + ".part", GAMELIST)


if __name__ == "__main__":
    assert release("24 Feb, 2017") == "20170224T000000" and release("Feb 24, 2017") == "20170224T000000"
    main()
