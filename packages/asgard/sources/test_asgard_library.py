#!/usr/bin/env python3
# spec: LIB-1 LIB-2 LIB-3 LIB-4
"""Run: python -I test_asgard_library.py  (no Thor): asgard-library.py's HTTP service on a fake root and its own port, with a
stand-in Home that shows the pairing code, and a stand-in transfers service. LIB-1: it serves the web app and answers hello.
LIB-2: nothing but hello and pairing without a token; the code Home shows pairs, three wrong codes get a new code and a wait that
grows; asking again or cancelling doesn't give tries back; another browser can't butt in; Home refusing ends it; forget unpairs.
LIB-3: chunked uploads land only when whole, resume from what arrived, refuse too little space; names that climb out of a system's
folder (.., absolute, hidden, a symlink out) are refused for upload, delete and rename. LIB-4: routing by extension, and by CRC
through the scrape index. The web app itself is the asgard-library-manager repository's test."""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = tempfile.mkdtemp()
SHARE = tempfile.mkdtemp()
os.environ.update(ASGARD_ROOT=ROOT, ASGARD_SHARE=SHARE)


def write(path, data=""):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb" if isinstance(data, bytes) else "w") as f:
        f.write(data)


ES = """<systemList>
<system><name>gba</name><fullname>Game Boy Advance</fullname><path>/storage/roms/gba</path><extension>.gba .GBA .zip</extension></system>
<system><name>snes</name><fullname>Super Nintendo</fullname><path>/storage/roms/snes</path><extension>.sfc .smc .zip</extension></system>
<system><name>steam</name><fullname>Steam</fullname><path>/storage/roms/steam</path><extension>.desktop</extension></system>
</systemList>"""
write(f"{ROOT}/usr/config/emulationstation/es_systems.cfg", ES)
write(f"{ROOT}/storage/roms/gba/Zelda.gba", b"z" * 100)
write(f"{ROOT}/storage/roms/gba/notes.txt", "not a game")
write(f"{ROOT}/storage/ES-DE/gamelists/gba/gamelist.xml",
      "<gameList><game><path>./Zelda.gba</path><name>The Legend of Zelda: The Minish Cap</name>"
      "<developer>Capcom</developer><releasedate>20041104T000000</releasedate></game></gameList>")
write(f"{ROOT}/storage/ES-DE/downloaded_media/gba/covers/Zelda.png", b"\x89PNG cover")
write(f"{ROOT}/storage/.config/system/configs/system.cfg", "system.hostname=THOR\n")
write(f"{ROOT}/usr/share/asgard-library-manager/index.html", "<!doctype html><title>Library Manager</title>")
write(f"{ROOT}/storage/outside.gba", "secret")
os.symlink(f"{ROOT}/storage", f"{ROOT}/storage/roms/gba/escape")
# the scrape index: asgard-scrape.py's SYSTEMS and INDEX, stood in for
write(f"{SHARE}/asgard-scrape.py", f"INDEX = {SHARE!r} + '/index'\nSYSTEMS = {{'snes': ('Nintendo - SNES', 4), "
                                   f"'gba': ('Nintendo - GBA', 12)}}\n")
write(f"{SHARE}/index/Nintendo - SNES.tsv", "Super Mario World (USA)\tB19ED489 0000AAAA\tNintendo\n")
write(f"{SHARE}/index/Nintendo - GBA.tsv", "Metroid Fusion (USA)\t6C6D6E6F\tNintendo\n")
# the transfers service: logs what it's asked
write(f"{SHARE}/asgard-transfers.py", f"import json,sys\nopen({SHARE!r}+'/transfers.log','a').write(' '.join(sys.argv[1:])+'\\n')\n"
                                      "print(json.dumps({'added': [1]} if sys.argv[1] == 'add' else {'busy': False}))\n")
os.makedirs(f"{ROOT}/run", exist_ok=True)

spec = importlib.util.spec_from_file_location("library", os.path.join(HERE, "asgard-library.py"))
lib = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lib)
lib.COOLDOWN = 1
lib.SHOWN_WAIT = 1.0
lib.MARGIN = 0

# Home: shows each code it's sent by writing it back, as Main.qml does; "refuse" makes it refuse the next one
shown, home_log = [], []
home_mode = {"show": True}


def fake_home(cmd):
    home_log.append(cmd)
    if cmd.startswith("pair ") and home_mode["show"]:
        shown.append(cmd.split()[1])
        write(lib.PIN_SHOWN, cmd.split()[1])


lib.home = fake_home
lib.Handler.svc = lib.Service()
srv = lib.Server(("::", 0), lib.Handler)
threading.Thread(target=srv.serve_forever, daemon=True).start()
BASE = f"http://127.0.0.1:{srv.server_address[1]}"


def call(method, path, body=None, token=None, raw=None, headers=None):
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    req = urllib.request.Request(BASE + path, data=data, method=method, headers=dict(headers or {}))
    if token:
        req.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            out = r.read()
            code, hdrs = r.status, r.headers
    except urllib.error.HTTPError as e:
        out, code, hdrs = e.read(), e.code, e.headers
    try:
        return code, json.loads(out), hdrs
    except ValueError:
        return code, out, hdrs


# LIB-1: the web app at /, hello without a token, CORS for a page opened from disk
code, page, hdrs = call("GET", "/")
assert code == 200 and b"Library Manager" in page and "text/html" in hdrs["Content-Type"], (code, page)
code, out, hdrs = call("GET", "/api/hello")
assert code == 200 and out["name"] == "THOR" and out["paired"] is False, out
assert hdrs["Access-Control-Allow-Origin"] == "*" and hdrs["Access-Control-Allow-Private-Network"] == "true"
assert call("OPTIONS", "/api/systems")[0] == 204
assert call("GET", "/../../etc/passwd")[0] == 404

# LIB-2: no token, no library
for method, path in (("GET", "/api/systems"), ("GET", "/api/games?system=gba"), ("GET", "/api/transfers"),
                     ("POST", "/api/delete"), ("PUT", "/api/upload?system=gba&path=x.gba&offset=0&total=1")):
    assert call(method, path, {} if method == "POST" else None, raw=b"x" if method == "PUT" else None,
                token="made-up")[0] == 401, (method, path)

# pairing: the code Home shows; three wrong guesses -> a new code, and a wait before it may be guessed
code, p, _ = call("POST", "/api/pair", {})
assert code == 200 and p["tries"] == 3 and len(shown) == 1 and len(shown[0]) == 6 and shown[0].isdigit(), (p, shown)
wrong = "000000" if shown[0] != "000000" else "111111"
assert call("POST", "/api/pair", {})[1]["pairing"] == p["pairing"] and len(shown) == 1   # asking again: the same code
for left in (2, 1):
    code, out, _ = call("POST", "/api/pair/confirm", {"pairing": p["pairing"], "code": wrong})
    assert code == 401 and out["tries"] == left, out
code, out, _ = call("POST", "/api/pair/confirm", {"pairing": p["pairing"], "code": wrong})
assert code == 401 and out["new_code"] and out["tries"] == 3 and out["retry_in"] == 1 and len(shown) == 2, out
first_pin = shown[0]
code, out, _ = call("POST", "/api/pair/confirm", {"pairing": p["pairing"], "code": shown[1]})
assert code == 429, out                                              # the right new code, but too soon
time.sleep(1.1)
code, out, _ = call("POST", "/api/pair/confirm", {"pairing": p["pairing"], "code": first_pin if first_pin != shown[1] else wrong})
assert code == 401 and out["tries"] == 2, out                        # the old code is gone
# cancelling and asking again doesn't give the tries back
call("POST", "/api/pair/cancel", {"pairing": p["pairing"]})
assert home_log[-1] == "pair-end"
code, p, _ = call("POST", "/api/pair", {})
assert code == 200 and p["tries"] == 2, p
call("POST", "/api/pair/confirm", {"pairing": p["pairing"], "code": wrong})
code, out, _ = call("POST", "/api/pair/confirm", {"pairing": p["pairing"], "code": wrong})
assert code == 401 and out["retry_in"] == 2, out                     # the second failed round waits twice as long
time.sleep(2.1)
code, out, _ = call("POST", "/api/pair/confirm", {"pairing": p["pairing"], "code": shown[-1], "name": "Firefox on PC"})
assert code == 200 and len(out["token"]) > 30, out
token = out["token"]
assert home_log[-1] == "pair-end"
saved = json.load(open(lib.SESSIONS))["sessions"]
assert len(saved) == 1 and token not in json.dumps(saved), saved     # kept hashed
assert oct(os.stat(lib.SESSIONS).st_mode & 0o777) == "0o600"
assert call("GET", "/api/hello", token=token)[1]["paired"] is True

# Home can't show it (a game in front): no code, and says where to go
home_mode["show"] = False
code, out, _ = call("POST", "/api/pair", {})
assert code == 503 and "Asgard Home" in out["error"], out
home_mode["show"] = True
# Home refuses: the pairing ends
code, p, _ = call("POST", "/api/pair", {})
write(lib.PAIR_CANCEL)
code, out, _ = call("POST", "/api/pair/confirm", {"pairing": p["pairing"], "code": shown[-1]})
assert code == 403, out
time.sleep(1.1)
# another browser can't take over a pairing under way
code, p, _ = call("POST", "/api/pair", {})
pairing = lib.Handler.svc.pairing
pairing.active["client"] = "192.168.1.99"
assert call("POST", "/api/pair", {})[0] == 409
assert call("POST", "/api/pair/confirm", {"pairing": p["pairing"], "code": shown[-1]})[0] == 404
pairing.active = None

# the library: systems with counts (Steam's apps aren't games), games with their scraped details and art
code, out, _ = call("GET", "/api/systems", token=token)
assert [s["name"] for s in out["systems"]] == ["gba", "snes"], out
assert out["systems"][0]["count"] == 1 and out["systems"][0]["extensions"] == [".gba", ".zip"] and out["free"] > 0, out
code, out, _ = call("GET", "/api/games?system=gba", token=token)
g = out["games"]
assert [x["path"] for x in g] == ["Zelda.gba"] and g[0]["name"] == "The Legend of Zelda: The Minish Cap", g
assert g[0]["developer"] == "Capcom" and g[0]["media"] == ["covers"] and g[0]["size"] == 100, g
code, img, hdrs = call("GET", "/api/media?system=gba&stem=Zelda&kind=covers", token=token)
assert code == 200 and img == b"\x89PNG cover" and hdrs["Content-Type"] == "image/png"
assert call("GET", "/api/media?system=gba&stem=../../../storage/outside&kind=covers", token=token)[0] == 404

# LIB-4: routing by extension; an extension two systems take is told apart by CRC through the scrape index
assert call("GET", "/api/route?name=Metroid.GBA", token=token)[1]["systems"] == ["gba"]
assert call("GET", "/api/route?name=game.zip", token=token)[1]["systems"] == ["gba", "snes"]
assert call("GET", "/api/route?name=game.exe", token=token)[1]["systems"] == []
out = call("GET", "/api/route?name=smw.zip&crc=b19ed489", token=token)[1]
assert out["identified"] == [{"system": "snes", "game": "Super Mario World (USA)"}], out
assert call("GET", "/api/route?name=x.zip&crc=12345678", token=token)[1]["identified"] == []

# LIB-3: a chunked upload: invisible until whole, resumes from what arrived, then scraped through the queue
rom = os.urandom(3000)
up = "/api/upload?system=gba&path=Metroid.gba&total=3000&scrape=1"
code, out, _ = call("PUT", up + "&offset=0", raw=rom[:1000], token=token)
assert code == 200 and out == {"received": 1000, "done": False}, out
assert not os.path.exists(f"{ROOT}/storage/roms/gba/Metroid.gba")   # not a game until whole
assert call("GET", "/api/upload?system=gba&path=Metroid.gba", token=token)[1]["received"] == 1000
code, out, _ = call("PUT", up + "&offset=0", raw=rom[:1000], token=token)
assert code == 409 and out["received"] == 1000, out                  # a chunk again: resume from here
code, out, _ = call("PUT", up + "&offset=1000", raw=rom[1000:], token=token)
assert code == 200 and out["done"], out
assert open(f"{ROOT}/storage/roms/gba/Metroid.gba", "rb").read() == rom
assert not os.path.exists(f"{ROOT}/storage/roms/gba/Metroid.gba{lib.PART}")
log = open(f"{SHARE}/transfers.log").read()
assert "hold library-upload 120" in log and "add scrape gba /storage/roms/gba/Metroid.gba Metroid" in log, log
code, out, _ = call("PUT", up + "&offset=0", raw=rom[:10], token=token)
assert code == 409, out                                              # already there, and not asked to replace it
# a game's own folder (multi-disc, Switch updates)
code, out, _ = call("PUT", "/api/upload?system=gba&path=Pokemon/Disc%201.gba&offset=0&total=4", raw=b"disc", token=token)
assert out["done"] and os.path.isfile(f"{ROOT}/storage/roms/gba/Pokemon/Disc 1.gba"), out
# too little space: refused before anything is written
lib.MARGIN = 1 << 62
code, out, _ = call("PUT", "/api/upload?system=gba&path=Big.gba&offset=0&total=10", raw=b"0123456789", token=token)
assert code == 507 and not os.path.exists(f"{ROOT}/storage/roms/gba/Big.gba{lib.PART}"), out
lib.MARGIN = 0
# cancelling an upload drops what arrived
call("PUT", "/api/upload?system=gba&path=Half.gba&offset=0&total=10", raw=b"01234", token=token)
call("DELETE", "/api/upload?system=gba&path=Half.gba", token=token)
assert not os.path.exists(f"{ROOT}/storage/roms/gba/Half.gba{lib.PART}")

# names that leave the system's folder: refused everywhere, nothing written or removed outside
for bad in ("../outside.gba", "../../storage/outside.gba", "/storage/outside.gba", ".hidden.gba", "a/../../x.gba",
            "escape/outside.gba", "a/b/c/d.gba", "x.gba" + lib.PART, "", " x.gba"):
    q = urllib.request.quote(bad)
    assert call("PUT", f"/api/upload?system=gba&path={q}&offset=0&total=1", raw=b"x", token=token)[0] == 400, bad
    assert call("POST", "/api/delete", {"system": "gba", "path": bad}, token=token)[0] == 404, bad
    assert call("POST", "/api/rename", {"system": "gba", "path": "Zelda.gba", "to": bad}, token=token)[0] in (400, 409), bad
assert open(f"{ROOT}/storage/outside.gba").read() == "secret"
assert call("POST", "/api/delete", {"system": "nope", "path": "Zelda.gba"}, token=token)[0] == 404

# rename and delete; Home rescans once, a moment after the last change
home_log.clear()
code, out, _ = call("POST", "/api/rename", {"system": "gba", "path": "Metroid.gba", "to": "Metroid Fusion.gba"}, token=token)
assert code == 200 and os.path.isfile(f"{ROOT}/storage/roms/gba/Metroid Fusion.gba"), out
assert call("POST", "/api/rename", {"system": "gba", "path": "Zelda.gba", "to": "Metroid Fusion.gba"}, token=token)[0] == 409
assert call("POST", "/api/delete", {"system": "gba", "path": "Pokemon/Disc 1.gba"}, token=token)[0] == 200
assert not os.path.exists(f"{ROOT}/storage/roms/gba/Pokemon")         # its folder, now empty, goes too
assert call("POST", "/api/scrape", {"system": "gba", "paths": ["Zelda.gba", "../outside.gba"]}, token=token)[0] == 200
assert open(f"{SHARE}/transfers.log").read().splitlines()[-1] == "add scrape gba /storage/roms/gba/Zelda.gba Zelda"
time.sleep(3.3)
assert home_log.count("rescan") == 1, home_log

# forget: every browser unpaired at once (Settings); logout: this one
env = dict(os.environ)
out = subprocess.run([sys.executable, "-I", os.path.join(HERE, "asgard-library.py"), "sessions"], env=env,
                     capture_output=True, text=True).stdout
assert json.loads(out) == {"paired": 1}, out
subprocess.run([sys.executable, "-I", os.path.join(HERE, "asgard-library.py"), "forget"], env=env, check=True,
               capture_output=True)
assert call("GET", "/api/systems", token=token)[0] == 401
srv.shutdown()
print("ok")
