#!/usr/bin/env python3
# spec: UPD-9 UPD-10
# requires: cmd:curl cmd:openssl
"""Run: python -I test_asgard_update.py  (no Thor, no network): asgard-update.py against a local HTTP server standing in
for GitHub, on a fake root, with throwaway keys. UPD-9: which release it picks (pre-releases, date tags, drafts, a
missing file, the skipped version, numeric order), what the request carries, the check at boot turned off and with no
network. UPD-10: only a download whose sha256 and signature both match becomes a .tar; a bad sha256, a .sha256 for
another file, a signature from another key or no key leave nothing staged; a cut connection resumes; too little space
and cancel. Home's side (the prompt, Settings > Updates) is test_home_update.py."""
import hashlib
import http.server
import importlib.util
import json
import os
import subprocess
import tempfile
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = tempfile.mkdtemp()
os.environ["ASGARD_ROOT"] = ROOT
spec = importlib.util.spec_from_file_location("asgard_update", os.path.join(HERE, "asgard-update.py"))
up = importlib.util.module_from_spec(spec)
spec.loader.exec_module(up)
up.CURL_WAIT = up.BOOT_WAIT = 0

NAME = "AsgardOS-SM8550.aarch64-0.0.2.tar"
REL = {"OS_NAME": "AsgardOS", "DISTRO_DEVICE": "SM8550", "HW_ARCH": "aarch64"}


def write(path, data, mode="w"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, mode) as f:
        f.write(data)


def release(tag, prerelease=False, draft=False, files=("", ".sha256", ".sig"), name=None):
    name = name or f"AsgardOS-SM8550.aarch64-{tag.lstrip('v')}.tar"
    return {"tag_name": tag, "prerelease": prerelease, "draft": draft, "body": "## What's new\n\n- **A thing.** More.\n",
            "assets": [{"name": name + f, "size": 10, "browser_download_url": f"http://x/{name}{f}"} for f in files]}


# ---- picking (UPD-9) ----------------------------------------------------------------------------------------------
assert up.version("v0.0.10") > up.version("v0.0.9") and up.version("v20261120") is None and up.version("0.1") is None
assert up.tar_name(REL, "0.0.2") == NAME
lst = [release("v0.0.2", prerelease=True), release("v20261120"), release("v0.0.1"), release("v0.0.3", draft=True)]
assert up.pick(lst, "0.0.1", REL)["version"] == "0.0.2"
assert up.pick(lst, "0.0.1", REL, prerelease=False) is None            # pre-releases off
assert up.pick(lst, "0.0.2", REL) is None                               # same version, a date tag, an older one, a draft
assert up.pick(lst, "0.0.1", REL, skip="0.0.2") is None                 # the skipped version
assert up.pick(lst, "devel", REL) is None                               # no release number: nothing is "newer"
assert up.pick([release("v0.0.9"), release("v0.0.10")], "0.0.1", REL)["version"] == "0.0.10"
for missing in (("", ".sha256"), ("", ".sig"), (".sha256", ".sig")):
    assert up.pick([release("v0.0.2", files=missing)], "0.0.1", REL) is None
assert up.pick([release("v0.0.2", name="AsgardOS-SM8650.aarch64-0.0.2.tar")], "0.0.1", REL) is None   # another device
found = up.pick([release("v0.0.2")], "0.0.1", REL)
assert found["tar"].endswith(NAME) and found["sig"].endswith(".sig") and found["notes"] == "• A thing. More."


# ---- a server standing in for GitHub ---------------------------------------------------------------------------------
class Server(http.server.BaseHTTPRequestHandler):
    files, seen, cut, no_ranges = {}, [], {}, False

    def log_message(self, *_):
        pass

    def do_GET(self):
        Server.seen.append((self.path, dict(self.headers)))
        body = Server.files.get(self.path.split("?")[0])
        if body is None:
            self.send_error(404)
            return
        start = int(self.headers["Range"].split("=")[1].split("-")[0]) if self.headers.get("Range") else 0
        if start and Server.no_ranges:
            start = 0
        self.send_response(206 if start else 200)
        self.send_header("Content-Length", str(len(body) - start))
        if start:
            self.send_header("Content-Range", f"bytes {start}-{len(body) - 1}/{len(body)}")
        self.end_headers()
        limit = Server.cut.pop(self.path, None)   # cut the connection after this many bytes, once
        self.wfile.write(body[start:limit] if limit else body[start:])
        if limit:
            self.wfile.flush()
            self.connection.close()


srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Server)
threading.Thread(target=srv.serve_forever, daemon=True).start()
BASE = f"http://127.0.0.1:{srv.server_port}"
KEYS = tempfile.mkdtemp()


def key(name):
    subprocess.run(["openssl", "genpkey", "-algorithm", "ed25519", "-out", f"{KEYS}/{name}"], check=True)
    return f"{KEYS}/{name}"


GOOD, OTHER = key("good"), key("other")
os.makedirs(os.path.dirname(up.KEY), exist_ok=True)
subprocess.run(["openssl", "pkey", "-in", GOOD, "-pubout", "-out", up.KEY], check=True)


def sign(data, with_key):
    path = f"{KEYS}/msg"
    write(path, data, "wb")
    return subprocess.run(["openssl", "pkeyutl", "-sign", "-inkey", with_key, "-rawin", "-in", path],
                          check=True, capture_output=True).stdout


def publish(tar=b"x" * 300_000, sums=None, with_key=GOOD, version="0.0.2", prerelease=True):
    name = f"AsgardOS-SM8550.aarch64-{version}.tar"
    sums = sums if sums is not None else f"{hashlib.sha256(tar).hexdigest()}  {name}\n".encode()
    Server.files = {f"/dl/{name}": tar, f"/dl/{name}.sha256": sums, f"/dl/{name}.sig": sign(sums, with_key)}
    rel = {"tag_name": f"v{version}", "prerelease": prerelease, "draft": False, "body": "",
           "assets": [{"name": name + f, "size": len(tar) if not f else 1,
                       "browser_download_url": f"{BASE}/dl/{name}{f}"} for f in ("", ".sha256", ".sig")]}
    Server.files["/api"] = json.dumps([rel]).encode()


def fresh(cfg=""):
    """A Thor on 0.0.1 with nothing checked, downloaded or staged."""
    subprocess.run(["rm", "-rf", f"{ROOT}/run", f"{ROOT}/storage"], check=True)
    write(up.OS_RELEASE, 'OS_NAME="AsgardOS"\nOS_VERSION="0.0.1"\nHW_ARCH="aarch64"\nDISTRO_DEVICE="SM8550"\n')
    write(up.CFG, f"asgard.update.repo={BASE}/api\n{cfg}")
    os.makedirs(up.UPDATE_DIR, exist_ok=True)
    Server.seen.clear()


def staged():
    return sorted(f for f in os.listdir(up.UPDATE_DIR) if not f.startswith("."))


# ---- check (UPD-9) ---------------------------------------------------------------------------------------------------
publish()
fresh()
assert up.check() == 0 and up.read_json(up.CHECK)["version"] == "0.0.2"
path, headers = Server.seen[0]
assert headers["User-Agent"] == "AsgardOS-updater"                       # no version, no device
sent = path + json.dumps({k: v for k, v in headers.items() if k != "Host"})
assert not any(v in sent for v in ("0.0.1", "SM8550", "aarch64", "TEST")), sent
fresh("asgard.update.prerelease=0\n")
assert up.check() == 0 and "version" not in up.read_json(up.CHECK)
fresh("asgard.update.skip=0.0.2\n")
assert up.check() == 0 and "version" not in up.read_json(up.CHECK)
fresh("asgard.update.check_at_boot=0\n")
assert up.boot() == 0 and not os.path.exists(up.CHECK) and not Server.seen
fresh()
write(up.CFG, "asgard.update.repo=http://127.0.0.1:9/api\n")             # nothing listens on port 9: no network
up.BOOT_TRIES = 2
assert up.boot() == 0 and up.read_json(up.CHECK)["error"] == "No internet"

# ---- download (UPD-10) -----------------------------------------------------------------------------------------------
fresh()
up.check()
rc = up.download(); assert rc == 0 and staged() == [NAME], (rc, staged(), up.read_json(up.PROGRESS), Server.seen[-3:])
assert up.read_json(up.PROGRESS)["state"] == "ready"
assert open(f"{up.UPDATE_DIR}/{NAME}", "rb").read() == Server.files[f"/dl/{NAME}"]
assert up.download() == 0 and staged() == [NAME]                        # already there: nothing downloaded again

for broken, why in ((dict(sums=b"0" * 64 + b"  " + NAME.encode() + b"\n"), "checksum"),
                    (dict(sums=f"{hashlib.sha256(b'x' * 300_000).hexdigest()}  other.tar\n".encode()), "another file"),
                    (dict(with_key=OTHER), "signature")):
    publish(**broken)
    fresh()
    up.check()
    assert up.download() == 1 and staged() == [], broken                  # no .tar, and no .part to resume from
    assert why in up.read_json(up.PROGRESS)["error"]

publish()
fresh()
up.check()
os.rename(up.KEY, up.KEY + ".off")
assert up.download() == 1 and staged() == [] and "no release key" in up.read_json(up.PROGRESS)["error"]
os.rename(up.KEY + ".off", up.KEY)

# A cut connection: resumed from where it stopped, by Range, not started over.
fresh()
up.check()
Server.cut[f"/dl/{NAME}"] = 100_000
rc = up.download(); assert rc == 0 and staged() == [NAME], (rc, staged(), up.read_json(up.PROGRESS), Server.seen[-3:])
ranges = [h.get("Range") for p, h in Server.seen if p == f"/dl/{NAME}"]
assert ranges[0] is None and ranges[1] == "bytes=100000-", ranges

# A .part left by an interrupted run is resumed too; one of another version is removed.
fresh()
up.check()
write(f"{up.UPDATE_DIR}/{NAME}.part", Server.files[f"/dl/{NAME}"][:50_000], "wb")
write(f"{up.UPDATE_DIR}/AsgardOS-SM8550.aarch64-0.0.1.tar.part", "old")
rc = up.download(); assert rc == 0 and staged() == [NAME], (rc, staged(), up.read_json(up.PROGRESS), Server.seen[-3:])
assert [h.get("Range") for p, h in Server.seen if p == f"/dl/{NAME}"] == ["bytes=50000-"]

# A server that ignores Range: the .part can't be resumed, so it starts over instead of failing every retry.
fresh()
up.check()
write(f"{up.UPDATE_DIR}/{NAME}.part", "not the start of the file")
Server.no_ranges = True
assert up.download() == 0 and staged() == [NAME]
Server.no_ranges = False

# Too little space: refused before downloading anything.
fresh()
up.check()
real_free, up.free = up.free, lambda _: 1 << 20
assert up.download() == 1 and staged() == [] and "MB free" in up.read_json(up.PROGRESS)["error"]
up.free = real_free

# Nothing found: nothing to download.
fresh("asgard.update.skip=0.0.2\n")
up.check()
assert up.download() == 1 and staged() == []

# Cancel: the running download stops and its .part goes.
fresh()
up.check()
write(f"{up.UPDATE_DIR}/{NAME}.part", "partial")
sleeper = subprocess.Popen(["sleep", "30"])
up.write_json(up.PROGRESS, {"pid": sleeper.pid, "state": "downloading"})
assert up.cancel() == 0 and sleeper.wait(timeout=5) != 0 and staged() == []
assert up.read_json(up.PROGRESS)["state"] == "cancelled"

# Status: a download whose process is gone reads as stopped, so Home offers to resume it.
up.write_json(up.PROGRESS, {"pid": sleeper.pid, "state": "downloading"})
r = subprocess.run(["python3", "-I", os.path.join(HERE, "asgard-update.py"), "status"], capture_output=True, text=True,
                   env={**os.environ, "ASGARD_ROOT": ROOT})
assert json.loads(r.stdout)["download"]["state"] == "stopped" and json.loads(r.stdout)["version"] == "0.0.2"

srv.shutdown()
subprocess.run(["rm", "-rf", ROOT, KEYS])
print("ok")
