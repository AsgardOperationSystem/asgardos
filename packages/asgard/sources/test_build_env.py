#!/usr/bin/env python3
# spec: DEV-9 DEV-10
# requires: cmd:bash cmd:make cmd:env
# Runs the real `./build.sh`, Makefile and scripts/get_env from a temp copy with a fake docker on PATH, from a caller's
# environment full of secrets: none reach the container, the tree is mounted at /work, and the build image is pinned by
# digest. The other half of DEV-10, no personal paths in binaries, is test_image_contents.py. DEV-9's "a clean checkout
# builds" is a human check; its known gaps are test_tree_deviations.py and the test_gap_* files.
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
SECRET_VALUE = "s3cret-value-from-the-caller"
SECRETS = ["LOCAL_WIFI_SSID", "LOCAL_WIFI_KEY", "LOCAL_SSH_KEYS_FILE", "GITLAB_TOKEN", "SSH_AUTH_SOCK"]
# What the container's environment may hold from the caller. The build's own make variables come on top.
ALLOWED_FROM_CALLER = {"TERM", "LANG", "HOME", "DOCKER_WORK_DIR", "CUSTOM_GIT_HASH"}


def main():
    with tempfile.TemporaryDirectory() as tmp:
        tree, fakes, home = [os.path.join(tmp, d) for d in ("tree", "fakes", "home")]
        os.makedirs(os.path.join(tree, "scripts"))
        os.mkdir(fakes)
        os.makedirs(os.path.join(home, ".asgardos"))
        shutil.copy(os.path.join(ROOT, "build.sh"), tree)
        shutil.copy(os.path.join(ROOT, "Makefile"), tree)
        shutil.copy(os.path.join(ROOT, "scripts", "get_env"), os.path.join(tree, "scripts"))
        # The caller's global options file is one more way in: build.sh's HOME=/tmp must leave it out.
        with open(os.path.join(home, ".asgardos", "options"), "w") as f:
            f.write(f"LOCAL_WIFI_SSID={SECRET_VALUE}\n")
        argv_log = os.path.join(tmp, "docker.argv")
        with open(os.path.join(fakes, "docker"), "w") as f:
            f.write(f'#!/bin/sh\n[ "$1" = --version ] && exit 0\nprintf \'%s\\n\' "$@" >> "{argv_log}"\n')
        os.chmod(os.path.join(fakes, "docker"), 0o755)

        env = dict(os.environ, PATH=fakes + os.pathsep + os.environ["PATH"], HOME=home)
        for key in SECRETS:
            env[key] = SECRET_VALUE
        proc = subprocess.run(["bash", os.path.join(tree, "build.sh")], env=env, capture_output=True, text=True,
                              timeout=60)
        out = proc.stdout + proc.stderr
        if not os.path.exists(argv_log):
            sys.exit(f"FAIL: the build never reached docker\n{out}")
        with open(argv_log) as f:
            argv = f.read().split("\n")
        with open(os.path.join(tree, "build", ".env")) as f:
            dotenv = f.read()

        problems = []
        names = {line.split("=", 1)[0] for line in dotenv.splitlines() if "=" in line}
        for key in SECRETS:
            if key in names:
                problems.append(f"{key} reaches the container's environment (SPEC DEV-10)")
        if SECRET_VALUE in dotenv or SECRET_VALUE in "\n".join(argv):
            problems.append("a value from the caller's environment reaches the container (SPEC DEV-10)")
        if os.path.join(home, ".asgardos", "options") in "\n".join(argv):
            problems.append("the caller's ~/.asgardos/options is mounted into the container (SPEC DEV-10)")
        leaked = names - ALLOWED_FROM_CALLER - {"PWD", "SHLVL", "_", "MAKEFLAGS", "MAKELEVEL", "MFLAGS", "OLDPWD"}
        if leaked:
            problems.append(f"more than the allowed variables reach the container (SPEC DEV-10): {sorted(leaked)}")
        if not re.search(r"^HOME=/tmp$", dotenv, re.M):
            problems.append("HOME isn't /tmp in the container: binaries could carry the caller's home (SPEC DEV-10)")
        if f"{tree}:/work" not in argv or "/work" not in argv:
            problems.append(f"the tree isn't mounted at /work (SPEC DEV-10): {argv}")
        if not any(re.search(r"@sha256:[0-9a-f]{64}$", a) for a in argv):
            problems.append(f"the build image isn't pinned by digest (SPEC DEV-9): {argv}")
        if problems:
            sys.exit("FAIL: " + "\n".join(problems))
    print("OK")


if __name__ == "__main__":
    main()
