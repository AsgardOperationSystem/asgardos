#!/usr/bin/env python3
# spec: DEV-22
# requires: cmd:bash cmd:openssl cmd:sha256sum
"""Run: python -I test_release.py: scripts/release with a throwaway key pair. --keygen makes a pair and won't replace
one; a release is signed only when its .tar matches its .sha256, that file names it, and the key is the one the image
ships; the signature it writes is one asgard-update.py's check (openssl pkeyutl -verify) accepts."""
import hashlib
import os
import subprocess
import tempfile

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../.."))
tmp = tempfile.mkdtemp()
KEY, PUB, OUT = f"{tmp}/keys/release.key", f"{tmp}/release-key.pem", f"{tmp}/target"
env = {**os.environ, "ASGARD_RELEASE_KEY": KEY, "ASGARD_RELEASE_PUB": PUB}
NAME = "AsgardOS-SM8550.aarch64-0.0.2.tar"


def release(*args, key=KEY):
    return subprocess.run([f"{REPO}/scripts/release", *args], capture_output=True, text=True,
                          env={**env, "ASGARD_RELEASE_KEY": key})


def files(tar=b"image", sums=None):
    subprocess.run(["rm", "-rf", OUT], check=True)
    os.makedirs(OUT)
    open(f"{OUT}/{NAME}", "wb").write(tar)
    open(f"{OUT}/{NAME}.sha256", "w").write(sums or f"{hashlib.sha256(tar).hexdigest()}  {NAME}\n")


def verifies():
    return subprocess.run(["openssl", "pkeyutl", "-verify", "-pubin", "-inkey", PUB, "-rawin", "-in",
                           f"{OUT}/{NAME}.sha256", "-sigfile", f"{OUT}/{NAME}.sig"],
                          capture_output=True).returncode == 0


r = release("--keygen")
assert r.returncode == 0 and os.path.exists(KEY) and os.path.exists(PUB), r.stderr
assert oct(os.stat(KEY).st_mode & 0o777) == "0o600" and oct(os.stat(os.path.dirname(KEY)).st_mode & 0o777) == "0o700"
before = open(KEY).read()
assert release("--keygen").returncode == 1 and open(KEY).read() == before      # never replaces a key

files()
r = release(OUT)
assert r.returncode == 0 and os.path.exists(f"{OUT}/{NAME}.sig") and verifies(), r.stderr

for sums, why in ((f"{'0' * 64}  {NAME}\n", "doesn't match"), (f"{hashlib.sha256(b'image').hexdigest()}  x.tar\n", "names")):
    files(sums=sums)
    r = release(OUT)
    assert r.returncode == 1 and why in r.stderr and not os.path.exists(f"{OUT}/{NAME}.sig"), r.stderr

files()
other = f"{tmp}/other.key"
subprocess.run(["openssl", "genpkey", "-algorithm", "ed25519", "-out", other], check=True)
r = release(OUT, key=other)
assert r.returncode == 1 and "isn't the key" in r.stderr and not os.path.exists(f"{OUT}/{NAME}.sig")
r = release(OUT, key=f"{tmp}/missing.key")
assert r.returncode == 1 and "no private key" in r.stderr
subprocess.run(["rm", "-rf", OUT])
os.makedirs(OUT)
assert release(OUT).returncode == 1

subprocess.run(["rm", "-rf", tmp])
print("ok")
