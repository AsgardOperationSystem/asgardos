#!/usr/bin/env python3
# spec: CFG-8
# requires: cmd:bash cmd:awk cmd:flock
"""The default root password in the options, system.cfg and the README, and that the boot step hands root.password to the
root login, Samba and Syncthing: 007-rootpw and setrootpass with their paths rewritten into a temp dir and stubs for the
three tools. That the login really works is the device check."""
import os
import re
import stat
import subprocess
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "../../.."))
ROOTED = re.compile(r'(?<![\w.$/}-])/(sys|run|storage|usr|etc|var|tmp)(?=[/\s"\':]|$)', re.M)
read = lambda name: open(os.path.join(REPO, name)).read()

assert re.search(r'^\s*ROOT_PASSWORD="asgardos"$', read("distribution/options"), re.M), "options: ROOT_PASSWORD"
SHIPPED = read("packages/asgardos/config/system/configs/system.cfg")
assert re.search(r"^root\.password=asgardos$", SHIPPED, re.M), "system.cfg: root.password"
assert re.search(r"root password is \*\*`asgardos`\*\*", read("README.md")), "the README doesn't document it"

with tempfile.TemporaryDirectory() as t:
    def write(name, text, mode=0o644):
        path = f"{t}/{name}"
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(text)
        os.chmod(path, mode)

    def install(source, dest):
        text = ROOTED.sub(lambda m: f"{t}/{m.group(1)}", read(source))
        # The image's bash is 5.3, where BASH_REMATCH can be local. An older host bash leaves that local empty.
        write(dest, text.replace("local -a keys=() BASH_REMATCH", "local -a keys=()"), stat.S_IRWXU)

    install("packages/asgardos/profile.d/001-functions", "etc/profile.d/001-functions")
    install("packages/asgardos/autostart/007-rootpw", "usr/lib/autostart/common/007-rootpw")
    install("packages/asgardos/sources/scripts/setrootpass", "usr/bin/setrootpass")
    write("etc/os-release", "")
    write("etc/profile", f". {t}/etc/profile.d/001-functions\n")
    write("storage/.cache/shadow", "root:OLDHASH:19000::::::\nnobody:*:19000::::::\n")
    write("storage/.config/system/configs/system.cfg", "root.password=chosen one\n")
    for tool, body in (("cryptpw", 'printf "HASH(%s)" "$3"'),
                       ("smbpasswd", f'cat > {t}/smb.in; echo "$*" > {t}/smb.args'),
                       ("syncthing", f'echo "$*" > {t}/syncthing.args'),
                       ("systemctl", "exit 0"),
                       ("tocon", "exit 0")):
        write(f"usr/bin/{tool}", f"#!/bin/sh\n{body}\n", stat.S_IRWXU)

    # The boot step reads the setting, whatever it is, not the default. /bin/sh on the image is bash.
    run = subprocess.run(["bash", f"{t}/usr/lib/autostart/common/007-rootpw"], capture_output=True, text=True, timeout=60)
    assert run.returncode == 0, run.stderr
    shadow = open(f"{t}/storage/.cache/shadow").read()
    assert shadow.startswith("root:HASH(chosen one):19000::::::\n"), shadow
    assert "nobody:*:19000" in shadow, shadow
    assert open(f"{t}/smb.in").read() == "chosen one\nchosen one\n", "Samba didn't get it"
    assert open(f"{t}/smb.args").read().split() == ["-sa", "root"]
    args = open(f"{t}/syncthing.args").read()
    assert "--gui-user root" in args and "--gui-password chosen one" in args, args
    assert "root.password=chosen one" in open(f"{t}/storage/.config/system/configs/system.cfg").read()
print("root password: ok")
