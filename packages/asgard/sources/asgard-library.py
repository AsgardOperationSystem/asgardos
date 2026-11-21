#!/usr/bin/env python3
"""asgard-library.py: the Library Manager's service (LIB-1): manage the Thor's games from a browser on the same network.

  asgard-library.py serve        the HTTP service on PORT (asgard-library.service; off with asgard.library_manager=0)
  asgard-library.py sessions     JSON: how many browsers are paired
  asgard-library.py forget       unpair every browser (Settings > Network > Library Manager)

The web app (the asgard-library-manager repository) is served at / and talks to /api. A browser pairs once (LIB-2): it
asks for a code, the Thor's screen shows six random digits, and the browser has three tries; after three wrong ones the
Thor picks new digits, and each failed round makes the next wait longer. A right code gives the browser a token, kept
hashed in SESSIONS, that it sends from then on. Without one, only /api/hello and pairing answer.

Everything it changes stays inside the systems' ROM folders from es_systems.cfg (LIB-3): uploads arrive in chunks into a
.asgard-part file that becomes the game only once whole (UPD-2's rule for updates, kept for games), names are checked
one path component at a time, and nothing outside those folders is read or written. Scrapes go through the transfers
queue (XFER-1), and uploads hold the Thor awake while they arrive (XFER-3). Python's standard library only (DEV-17).
"""
import hashlib
import http.server
import importlib.util
import json
import mimetypes
import os
import re
import secrets
import socket
import subprocess
import sys
import threading
import time
import urllib.parse
import xml.etree.ElementTree as ET

ROOT = os.environ.get("ASGARD_ROOT", "")
SHARE = os.environ.get("ASGARD_SHARE", "/usr/share/asgard")
PORT = int(os.environ.get("ASGARD_LIBRARY_PORT", "8467"))   # THOR on a phone keypad
ES_SYSTEMS = ROOT + "/usr/config/emulationstation/es_systems.cfg"   # what Asgard Home reads
GAMELISTS = ROOT + "/storage/ES-DE/gamelists"
MEDIA = ROOT + "/storage/ES-DE/downloaded_media"
CFG = ROOT + "/storage/.config/system/configs/system.cfg"
SESSIONS = ROOT + "/storage/.config/asgard/library-manager.json"   # CFG-6
WEBAPP = os.environ.get("ASGARD_LIBRARY_WEBAPP", ROOT + "/usr/share/asgard-library-manager")
HOME_FIFO = ROOT + "/run/asgard-home.cmd"
PIN_SHOWN = ROOT + "/run/asgard-library-pin"          # Home writes the code it shows here
PAIR_CANCEL = ROOT + "/run/asgard-library-pair.cancel"  # Home: the user refused on the Thor
OS_RELEASE = ROOT + "/etc/os-release"
PART = ".asgard-part"
TRIES = 3                 # wrong codes before the Thor picks another
PAIR_SECS = 120           # a code lasts this long
COOLDOWN, COOLDOWN_MAX = 10, 900   # s after a failed round, doubling each round, up to 15 min
CHUNK_MAX = 64 << 20      # one upload request
MARGIN = 256 << 20        # free space an upload leaves in /storage
HOLD_SECS = 120           # an upload keeps the Thor out of sleep this long after its last chunk (XFER-3)
SHOWN_WAIT = 3.0          # s to wait for Home to show the code
MEDIA_KINDS = ("covers", "screenshots", "marquees")
HIDDEN = ("music", "steam")   # Tools and PC hold apps, not games


def setting(key, default=""):
    try:
        for line in open(CFG, encoding="utf-8", errors="replace"):
            if line.startswith(key + "="):
                default = line.split("=", 1)[1].strip()
    except OSError:
        pass
    return default


def os_version():
    try:
        for line in open(OS_RELEASE):
            if line.startswith("OS_VERSION="):
                return line.split("=", 1)[1].strip().strip('"')
    except OSError:
        pass
    return ""


def home(cmd):
    """A line to Asgard Home's command FIFO; never blocks when Home isn't reading it."""
    if os.path.exists(HOME_FIFO):
        subprocess.run(["timeout", "1", "sh", "-c", 'echo "$0" > "$1"', cmd, HOME_FIFO])


def transfers(*args):
    try:
        r = subprocess.run(["python3", f"{SHARE}/asgard-transfers.py", *args], capture_output=True, text=True, timeout=15)
        return json.loads(r.stdout or "{}")
    except (subprocess.TimeoutExpired, ValueError, OSError):
        return {"error": "The transfers service didn't answer"}


def scrape_index():
    """asgard-scrape.py's SYSTEMS and INDEX: which libretro database each system is, for identify()."""
    spec = importlib.util.spec_from_file_location("asgard_scrape", f"{SHARE}/asgard-scrape.py")
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except (OSError, SyntaxError):
        return {}, ""
    return mod.SYSTEMS, mod.INDEX


# --- the library --------------------------------------------------------------------------------------------------------

def systems():
    """{name: {name, fullname, path, extensions}} from es_systems.cfg, as Asgard Home reads it."""
    out = {}
    try:
        tree = ET.parse(ES_SYSTEMS)
    except (OSError, ET.ParseError):
        return out
    for s in tree.getroot().iter("system"):
        name = (s.findtext("name") or "").strip()
        path = (s.findtext("path") or "").strip()
        if not name or not path or name in HIDDEN:
            continue
        exts = sorted({e.lower() for e in (s.findtext("extension") or "").split() if e.startswith(".")})
        out[name] = {"name": name, "fullname": (s.findtext("fullname") or name).strip(), "path": ROOT + path,
                     "extensions": exts, "manufacturer": (s.findtext("manufacturer") or "").strip()}
    return out


def gamelist(system):
    """./relative path -> {field: value} from the system's ES-DE gamelist (what scraping wrote)."""
    out = {}
    try:
        root = ET.parse(f"{GAMELISTS}/{system}/gamelist.xml").getroot()
    except (OSError, ET.ParseError):
        return out
    for g in root.iter("game"):
        p = os.path.normpath((g.findtext("path") or "").strip())
        if p:
            out[p] = {c.tag: (c.text or "").strip() for c in g if c.tag != "path" and (c.text or "").strip()}
    return out


def media_file(system, stem, kind):
    for ext in ("png", "jpg", "jpeg", "webp"):
        f = f"{MEDIA}/{system}/{kind}/{stem}.{ext}"
        if os.path.isfile(f):
            return f
    return None


def game_files(sysinfo):
    """Games in a system's folder and one level of subfolders (as Home scans it), by extension."""
    d, exts = sysinfo["path"], set(sysinfo["extensions"])
    out = []
    try:
        entries = sorted(os.scandir(d), key=lambda e: e.name.lower())
    except OSError:
        return out
    for e in entries:
        if e.name.startswith("."):
            continue
        if e.is_dir(follow_symlinks=False):
            try:
                subs = sorted(os.scandir(e.path), key=lambda x: x.name.lower())
            except OSError:
                continue
            out += [(f"{e.name}/{s.name}", s) for s in subs if s.is_file() and not s.name.startswith(".")
                    and os.path.splitext(s.name)[1].lower() in exts]
        elif e.is_file() and os.path.splitext(e.name)[1].lower() in exts:
            out.append((e.name, e))
    return out


def games(sysinfo):
    meta = gamelist(sysinfo["name"])
    out = []
    for rel, entry in game_files(sysinfo):
        st = entry.stat()
        stem = os.path.splitext(rel)[0]
        g = {"path": rel, "stem": stem, "size": st.st_size, "mtime": int(st.st_mtime),
             "media": [k for k in MEDIA_KINDS if media_file(sysinfo["name"], stem, k)]}
        g.update({k: v for k, v in meta.get(os.path.normpath(rel), {}).items()
                  if k in ("name", "desc", "developer", "publisher", "genre", "players", "releasedate", "rating")})
        g.setdefault("name", os.path.basename(stem))
        out.append(g)
    return out


def free_bytes(path):
    while path and not os.path.exists(path):
        path = os.path.dirname(path)
    try:
        st = os.statvfs(path or "/")
    except OSError:
        return 0
    return st.f_bavail * st.f_frsize


def safe_rel(rel):
    """A path inside a system folder, as the browser names it: 1-3 components, none empty, hidden, '.' or '..'."""
    if not isinstance(rel, str) or "\0" in rel or "\\" in rel or len(rel) > 1024:
        return None
    parts = rel.split("/")
    if not 1 <= len(parts) <= 3:
        return None
    for p in parts:
        if not p or p.startswith(".") or p.strip() != p or len(p.encode()) > 255 or p.endswith(PART):
            return None
    return "/".join(parts)


def resolve(sysinfo, rel):
    """The absolute path for rel in the system's folder, or None if it would land anywhere else (symlinks included)."""
    rel = safe_rel(rel)
    if not rel:
        return None
    base = os.path.realpath(sysinfo["path"])
    target = os.path.realpath(os.path.join(base, rel))
    if os.path.commonpath([base, target]) != base or target == base:
        return None
    return target


def route(name, all_systems):
    """The systems a file of this name can go to, by extension (LIB-4)."""
    ext = os.path.splitext(name)[1].lower()
    return sorted((s for s in all_systems.values() if ext and ext in s["extensions"]), key=lambda s: s["fullname"])


def identify(crc, all_systems):
    """The systems whose libretro database has a game with this CRC32, and its name: scrape data routing an upload whose
    extension many systems take (.zip, .chd, .iso)."""
    crc = (crc or "").upper()
    if not re.fullmatch(r"[0-9A-F]{8}", crc):
        return []
    sysmap, index = scrape_index()
    hits = []
    by_playlist = {}
    for name, (playlist, _) in sysmap.items():
        if playlist and name in all_systems:
            by_playlist.setdefault(playlist, []).append(name)
    for playlist, names in sorted(by_playlist.items()):
        try:
            text = open(f"{index}/{playlist}.tsv", encoding="utf-8").read()
        except OSError:
            continue
        if crc not in text:
            continue
        for line in text.splitlines():
            cols = line.split("\t")
            if len(cols) > 1 and crc in cols[1].split():
                hits += [{"system": n, "game": cols[0]} for n in sorted(names)]
                break
    return hits


# --- pairing and sessions ----------------------------------------------------------------------------------------------

def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def load_sessions():
    try:
        return json.load(open(SESSIONS)).get("sessions", {})
    except (OSError, ValueError, AttributeError):
        return {}


def save_sessions(sessions):
    os.makedirs(os.path.dirname(SESSIONS), exist_ok=True)
    tmp = SESSIONS + ".tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump({"sessions": sessions}, f)
    os.replace(tmp, SESSIONS)


class Pairing:
    """One code at a time. A round is TRIES wrong guesses; a failed round picks a new code at once, but the browser has to
    wait before guessing it, longer each round (10 s, 20 s, 40 s... up to 15 min). Wrong guesses count until a right one,
    whatever happens between: asking for a new code, cancelling or letting one run out doesn't give the tries back."""

    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.lock = threading.Lock()
        self.active = None      # {"id", "pin", "expires", "client", "not_before"}
        self.wrong = 0          # wrong guesses since the last right one
        self.failed_rounds = 0
        self.wait_until = 0.0   # no new pairing or guess before this

    def tries(self):
        return TRIES - self.wrong % TRIES

    def _new_pin(self):
        return f"{secrets.randbelow(10 ** 6):06d}"

    def _show(self, pin, client):
        """Ask Home to show the code; True once it says it does."""
        try:
            os.remove(PIN_SHOWN)
        except OSError:
            pass
        home(f"pair {pin} {client}")
        end = time.monotonic() + SHOWN_WAIT
        while time.monotonic() < end:
            try:
                if open(PIN_SHOWN).read().strip() == pin:
                    return True
            except OSError:
                pass
            time.sleep(0.05)
        return False

    def _end(self):
        if self.active:
            self.active = None
            home("pair-end")

    def _refused(self):
        if os.path.exists(PAIR_CANCEL):
            os.remove(PAIR_CANCEL)
            return True
        return False

    def start(self, client):
        with self.lock:
            now = self.clock()
            if self._refused():
                self._end()
                self.wait_until = max(self.wait_until, now + COOLDOWN)
            if self.active and self.active["expires"] > now:
                if self.active["client"] != client:
                    return 409, {"error": "Another browser is pairing with this Thor right now"}
                return 200, {"pairing": self.active["id"], "tries": self.tries(),   # the same code, still on screen
                             "expires_in": int(self.active["expires"] - now),
                             "retry_in": max(0, int(self.active["not_before"] - now))}
            if now < self.wait_until:
                return 429, {"error": "Too many wrong codes: wait a moment", "retry_in": int(self.wait_until - now) + 1}
            pin = self._new_pin()
            if not self._show(pin, client):
                self.active = None
                home("pair-end")
                return 503, {"error": "The Thor can't show the code: go to Asgard Home on its screen, then try again"}
            self.active = {"id": secrets.token_hex(8), "pin": pin, "expires": now + PAIR_SECS, "client": client,
                           "not_before": now}
            return 200, {"pairing": self.active["id"], "tries": self.tries(), "expires_in": PAIR_SECS}

    def confirm(self, pairing, pin, client, name):
        with self.lock:
            now = self.clock()
            a = self.active
            if self._refused():
                self._end()
                self.wait_until = max(self.wait_until, now + COOLDOWN)
                return 403, {"error": "Refused on the Thor"}
            if not a or a["id"] != pairing or a["client"] != client:
                return 404, {"error": "No pairing under way: ask for a new code"}
            if a["expires"] <= now:
                self._end()
                return 410, {"error": "The code ran out: ask for a new one"}
            if now < a["not_before"]:
                return 429, {"error": "Wait before trying the new code", "retry_in": int(a["not_before"] - now) + 1}
            if isinstance(pin, str) and secrets.compare_digest(pin.strip().encode(), a["pin"].encode()):
                self.failed_rounds = self.wrong = 0
                self._end()
                token = secrets.token_urlsafe(32)
                sessions = load_sessions()
                sessions[token_hash(token)] = {"name": str(name or "Browser")[:80], "client": client,
                                               "paired": int(time.time()), "seen": int(time.time())}
                save_sessions(sessions)
                return 200, {"token": token}
            self.wrong += 1
            if self.wrong % TRIES:
                return 401, {"error": "Wrong code", "tries": self.tries()}
            # A round failed: a new code now, guessed only after a wait that doubles each round.
            self.failed_rounds += 1
            wait = min(COOLDOWN * 2 ** (self.failed_rounds - 1), COOLDOWN_MAX)
            pin = self._new_pin()
            if not self._show(pin, client):
                self._end()
                self.wait_until = now + wait
                return 401, {"error": "Wrong code three times", "tries": 0, "new_code": False, "retry_in": wait}
            a.update(pin=pin, expires=now + wait + PAIR_SECS, not_before=now + wait)
            return 401, {"error": "Wrong code three times: the Thor shows a new one", "tries": TRIES, "new_code": True,
                         "retry_in": wait}

    def cancel(self, pairing, client):
        with self.lock:
            if self.active and self.active["id"] == pairing and self.active["client"] == client:
                self._end()


# --- HTTP ---------------------------------------------------------------------------------------------------------------

class Service:
    def __init__(self):
        self.pairing = Pairing()
        self.rescan_timer = None
        self.rescan_lock = threading.Lock()
        self.upload_locks = {}
        self.locks_lock = threading.Lock()

    def rescan_soon(self):
        """Home rescans 3 s after the last change, not once per file of a batch."""
        with self.rescan_lock:
            if self.rescan_timer:
                self.rescan_timer.cancel()
            self.rescan_timer = threading.Timer(3, home, args=("rescan",))
            self.rescan_timer.daemon = True
            self.rescan_timer.start()

    def upload_lock(self, path):
        with self.locks_lock:
            return self.upload_locks.setdefault(path, threading.Lock())


class Handler(http.server.BaseHTTPRequestHandler):
    server_version = "AsgardLibrary/1"
    protocol_version = "HTTP/1.1"
    svc = None   # set by serve()

    def log_message(self, fmt, *args):   # no access log: it would name the user's files in the journal
        pass

    # --- plumbing ---

    def cors(self):
        # Any origin: the web app may be a file opened from disk. Safe because the token travels in a header the page
        # must hold, never in a cookie a browser would send on its own.
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Private-Network", "true")
        self.send_header("Access-Control-Max-Age", "600")

    def reply(self, code, body, ctype="application/json", extra=None):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.cors()
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    def body_json(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n > 1 << 20:
            raise ValueError("too large")
        try:
            return json.loads(self.rfile.read(n) or b"{}")
        except ValueError:
            return {}

    def query(self):
        return {k: v[-1] for k, v in urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query).items()}

    def route_path(self):
        return urllib.parse.urlsplit(self.path).path

    def client(self):
        ip = self.client_address[0]
        return ip[7:] if ip.startswith("::ffff:") else ip   # IPv4 through the IPv6 socket

    def session(self):
        auth = self.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return None
        h = token_hash(auth[7:].strip())
        sessions = load_sessions()
        if h not in sessions:
            return None
        if time.time() - sessions[h].get("seen", 0) > 3600:   # last seen, coarse: one write an hour at most
            sessions[h]["seen"] = int(time.time())
            save_sessions(sessions)
        return h

    def system(self, q, all_systems):
        return all_systems.get(q.get("system", ""))

    # --- methods ---

    def do_OPTIONS(self):
        self.send_response(204)
        self.cors()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        p = self.route_path()
        if not p.startswith("/api/"):
            return self.static(p)
        if p == "/api/hello":
            return self.reply(200, {"app": "asgard-library", "name": setting("system.hostname", socket.gethostname()),
                                    "version": os_version(), "paired": bool(self.session())})
        if not self.session():
            return self.reply(401, {"error": "Not paired"})
        q, all_systems = self.query(), systems()
        if p == "/api/systems":
            out = []
            for s in sorted(all_systems.values(), key=lambda s: s["fullname"].lower()):
                files = game_files(s)
                out.append({k: s[k] for k in ("name", "fullname", "manufacturer", "extensions")} |
                           {"count": len(files), "size": sum(e.stat().st_size for _, e in files)})
            roms = ROOT + "/storage/roms"
            return self.reply(200, {"systems": out, "free": free_bytes(roms)})
        if p == "/api/games":
            s = self.system(q, all_systems)
            return self.reply(200, {"games": games(s)}) if s else self.reply(404, {"error": "No such system"})
        if p == "/api/media":
            s = self.system(q, all_systems)
            stem = safe_rel(q.get("stem", "")) if s else None
            f = media_file(s["name"], stem, q.get("kind")) if stem and q.get("kind") in MEDIA_KINDS else None
            if not f:
                return self.reply(404, {"error": "No such image"})
            data = open(f, "rb").read()
            return self.reply(200, data, mimetypes.guess_type(f)[0] or "application/octet-stream",
                              {"Cache-Control": "private, max-age=300"})
        if p == "/api/route":
            name = q.get("name", "")
            return self.reply(200, {"systems": [s["name"] for s in route(name, all_systems)],
                                    "identified": identify(q.get("crc"), all_systems) if q.get("crc") else []})
        if p == "/api/upload":
            s = self.system(q, all_systems)
            target = resolve(s, q.get("path", "")) if s else None
            if not target:
                return self.reply(400, {"error": "Bad name"})
            part = target + PART
            return self.reply(200, {"received": os.path.getsize(part) if os.path.isfile(part) else 0,
                                    "exists": os.path.exists(target)})
        if p == "/api/transfers":
            return self.reply(200, transfers("status"))
        return self.reply(404, {"error": "Not found"})

    def do_PUT(self):
        # An answer before the body is read leaves it on the connection: the next request would start inside it.
        self.close_connection = True
        p = self.route_path()
        if p != "/api/upload":
            return self.reply(404, {"error": "Not found"})
        if not self.session():
            return self.reply(401, {"error": "Not paired"})
        q, all_systems = self.query(), systems()
        s = self.system(q, all_systems)
        target = resolve(s, q.get("path", "")) if s else None
        try:
            offset, total, n = int(q.get("offset", "-1")), int(q.get("total", "-1")), int(self.headers["Content-Length"])
        except (TypeError, ValueError):
            offset = total = n = -1
        if not target:
            return self.reply(400, {"error": "Bad name"})
        if offset < 0 or total < 0 or n < 0 or n > CHUNK_MAX or offset + n > total:
            return self.reply(400, {"error": "Bad chunk"})
        if os.path.exists(target) and q.get("replace") != "1":
            self.drain(n)
            return self.reply(409, {"error": "A game with this name is already there"})
        part = target + PART
        with self.svc.upload_lock(part):
            have = os.path.getsize(part) if os.path.isfile(part) else 0
            if offset != have:   # out of order, or a chunk that was already written: the browser resumes from here
                self.drain(n)
                return self.reply(409, {"error": "Resume from here", "received": have})
            if offset == 0 and total + MARGIN > free_bytes(os.path.dirname(target)):
                self.drain(n)
                return self.reply(507, {"error": f"Not enough space: {total >> 20} MB needs "
                                                 f"{(total + MARGIN) >> 20} MB free, the Thor has "
                                                 f"{free_bytes(os.path.dirname(target)) >> 20} MB"})
            transfers("hold", "library-upload", str(HOLD_SECS))
            os.makedirs(os.path.dirname(target), exist_ok=True)
            left = n
            with open(part, "ab") as f:
                while left:
                    chunk = self.rfile.read(min(left, 1 << 20))
                    if not chunk:
                        break
                    f.write(chunk)
                    left -= len(chunk)
            got = os.path.getsize(part)
            if left:
                return self.reply(400, {"error": "The chunk was cut short", "received": got})
            self.close_connection = False   # the body is read: the connection can carry the next chunk
            if got == total:
                with open(part, "rb+") as f:
                    os.fsync(f.fileno())
                os.replace(part, target)   # only now is it a game
                self.svc.rescan_soon()
                if q.get("scrape") == "1":
                    stem = os.path.splitext(os.path.relpath(target, os.path.realpath(s["path"])))[0]
                    transfers("add", "scrape", s["name"], target[len(ROOT):] if ROOT else target, stem)
                return self.reply(200, {"received": got, "done": True})
            return self.reply(200, {"received": got, "done": False})

    def drain(self, n):
        while n > 0:
            chunk = self.rfile.read(min(n, 1 << 20))
            if not chunk:
                break
            n -= len(chunk)

    def do_POST(self):
        p = self.route_path()
        try:
            body = self.body_json()
        except ValueError:
            return self.reply(413, {"error": "Too large"})
        if p == "/api/pair":
            code, out = self.svc.pairing.start(self.client())
            return self.reply(code, out)
        if p == "/api/pair/confirm":
            code, out = self.svc.pairing.confirm(body.get("pairing"), body.get("code"), self.client(), body.get("name"))
            return self.reply(code, out)
        if p == "/api/pair/cancel":
            self.svc.pairing.cancel(body.get("pairing"), self.client())
            return self.reply(200, {"ok": True})
        h = self.session()
        if not h:
            return self.reply(401, {"error": "Not paired"})
        if p == "/api/logout":
            sessions = load_sessions()
            sessions.pop(h, None)
            save_sessions(sessions)
            return self.reply(200, {"ok": True})
        all_systems = systems()
        s = all_systems.get(body.get("system", ""))
        if not s:
            return self.reply(404, {"error": "No such system"})
        if p == "/api/scrape":
            games_ = []
            for rel in body.get("paths", [])[:5000]:
                target = resolve(s, rel)
                if target and os.path.isfile(target):
                    games_ += [s["name"], target[len(ROOT):] if ROOT else target, os.path.splitext(safe_rel(rel))[0]]
            if not games_:
                return self.reply(400, {"error": "No games to scrape"})
            out = {}
            for i in range(0, len(games_), 300):   # 100 games a command line
                out = transfers("add", "scrape", *games_[i:i + 300])
            return self.reply(200 if "error" not in out else 503, out)
        if p == "/api/delete":
            target = resolve(s, body.get("path", ""))
            if not target or not (os.path.isfile(target) or os.path.isfile(target + PART)):
                return self.reply(404, {"error": "No such game"})
            for f in (target, target + PART):
                if os.path.isfile(f):
                    os.remove(f)
            folder = os.path.dirname(target)
            if folder != os.path.realpath(s["path"]) and not os.listdir(folder):
                os.rmdir(folder)   # a game's own folder, now empty
            self.svc.rescan_soon()
            return self.reply(200, {"ok": True})
        if p == "/api/rename":
            target = resolve(s, body.get("path", ""))
            to = body.get("to", "")
            if not target or not os.path.isfile(target):
                return self.reply(404, {"error": "No such game"})
            if not safe_rel(to) or "/" in to:
                return self.reply(400, {"error": "Bad name"})
            new = os.path.join(os.path.dirname(target), to)
            if os.path.exists(new):
                return self.reply(409, {"error": "A game with this name is already there"})
            os.rename(target, new)
            self.svc.rescan_soon()
            return self.reply(200, {"ok": True, "path": os.path.relpath(new, os.path.realpath(s["path"]))})
        return self.reply(404, {"error": "Not found"})

    def do_DELETE(self):
        p = self.route_path()
        if p != "/api/upload":
            return self.reply(404, {"error": "Not found"})
        if not self.session():
            return self.reply(401, {"error": "Not paired"})
        q = self.query()
        s = systems().get(q.get("system", ""))
        target = resolve(s, q.get("path", "")) if s else None
        if not target:
            return self.reply(400, {"error": "Bad name"})
        with self.svc.upload_lock(target + PART):
            if os.path.isfile(target + PART):
                os.remove(target + PART)
        return self.reply(200, {"ok": True})

    def static(self, p):
        rel = "index.html" if p in ("/", "") else urllib.parse.unquote(p.lstrip("/"))
        base = os.path.realpath(WEBAPP)
        f = os.path.realpath(os.path.join(base, rel))
        if os.path.commonpath([base, f]) != base or not os.path.isfile(f):
            if rel == "index.html":
                return self.reply(200, b"<!doctype html><title>Asgard Library Manager</title><p>The Library Manager web "
                                       b"app isn't installed on this Thor. Get it from github.com/AsgardOperationSystem/"
                                       b"asgard-library-manager.", "text/html; charset=utf-8")
            return self.reply(404, {"error": "Not found"})
        ctype = mimetypes.guess_type(f)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript",):
            ctype += "; charset=utf-8"
        return self.reply(200, open(f, "rb").read(), ctype,
                          {"Content-Security-Policy": "default-src 'self' 'unsafe-inline'; img-src 'self' blob: data:; "
                                                      "connect-src *", "X-Frame-Options": "DENY"})


class Server(http.server.ThreadingHTTPServer):
    daemon_threads = True
    address_family = socket.AF_INET6

    def server_bind(self):
        self.socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)   # IPv4 too
        super().server_bind()


def serve(port=PORT):
    Handler.svc = Service()
    for f in (PIN_SHOWN, PAIR_CANCEL):
        if os.path.exists(f):
            os.remove(f)
    srv = Server(("::", port), Handler)
    srv.serve_forever()


def main(argv):
    if argv[1:] == ["serve"]:
        serve()
        return 0
    if argv[1:] == ["sessions"]:
        print(json.dumps({"paired": len(load_sessions())}))
        return 0
    if argv[1:] == ["forget"]:
        save_sessions({})
        print(json.dumps({"paired": 0}))
        return 0
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
