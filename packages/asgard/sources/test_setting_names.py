#!/usr/bin/env python3
# spec: CFG-5
# gap: asgardos.bottomscreen.type renames ROCKNIX's rocknix.bottomscreen.type; screenscraper.* and global.retroachievements.webapikey are new keys without asgard.
"""The settings that don't follow CFG-5 today. The rest of the tree is test_config_conventions.py."""
import os

SOURCES = os.path.dirname(os.path.abspath(__file__))
QML = open(os.path.join(SOURCES, "../../asgard-home/src/qml/Settings.qml")).read()
SCRAPE = open(os.path.join(SOURCES, "asgard-scrape.py")).read()
ACHIEVEMENTS = open(os.path.join(SOURCES, "../../asgard-home/src/achievements.cpp")).read()
bad = [key for key, text in (("asgardos.bottomscreen.type", QML), ("screenscraper.devid", SCRAPE),
                             ("screenscraper.devpassword", SCRAPE), ("screenscraper.username", SCRAPE),
                             ("screenscraper.password", SCRAPE), ("global.retroachievements.webapikey", ACHIEVEMENTS))
       if key in text]
assert not bad, bad
