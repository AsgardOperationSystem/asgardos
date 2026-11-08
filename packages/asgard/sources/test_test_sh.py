#!/usr/bin/env python3
# spec: DEV-11
# requires: cmd:bash cmd:timeout
"""test.sh itself, a copy in a temp repo with its own small tests: how many run at once, results in file order whoever finishes
first, each test's own TMPDIR and output.log under the prefix (DEV-11: build/ by default), and a failure's folder kept."""
import glob
import os
import shutil
import stat
import subprocess
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TEST_SH = os.path.join(HERE, "../../../test.sh")


def write(path, text, mode=0o644):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(text)
    os.chmod(path, mode)


def repo(d, tests):
    """A tree test.sh can run in: one rule, the self-check it always runs, and these tests {name: body}."""
    shutil.rmtree(d, ignore_errors=True)
    write(f"{d}/test.sh", open(TEST_SH).read(), stat.S_IRWXU)
    write(f"{d}/SPEC.md", "- **DEV-1** a rule\n- **CFG-1** a rule\n- **CFG-3** a rule\n")
    write(f"{d}/packages/asgard/sources/asgard_config.py", "")
    for name, body in tests.items():
        write(f"{d}/packages/asgard/sources/{name}", "# spec: DEV-1\n" + body)


def run(d, *args, prefix=None):
    env = {k: v for k, v in os.environ.items() if k not in ("TEST_JOBS", "TEST_PREFIX")}
    env["MARK"] = f"{d}/mark"
    if prefix:
        env["TEST_PREFIX"] = prefix
    return subprocess.run([f"{d}/test.sh", *args], capture_output=True, text=True, timeout=60, env=env, cwd=d)


def order(out):
    return [line.split()[1] for line in out.splitlines() if line[:4] in ("PASS", "FAIL", "SKIP", "GAP ")]


with tempfile.TemporaryDirectory() as t:
    d = f"{t}/repo"
    # The first needs the second running, and is still first in the results. One at a time it can't pass.
    needs = 'i=0; while [ ! -e "$MARK" ] && [ $i -lt 40 ]; do sleep 0.05; i=$((i + 1)); done; [ -e "$MARK" ]\n'
    TOGETHER = {"test_a_waits.sh": needs, "test_b_marks.sh": ': > "$MARK"\n'}
    repo(d, TOGETHER)
    both = run(d, "-j", "2")
    assert both.returncode == 0, both.stdout + both.stderr
    assert order(both.stdout)[:2] == ["test_a_waits.sh", "test_b_marks.sh"], both.stdout
    assert os.listdir(f"{d}/build/test/runs") == [], "a clean run left its folder"   # DEV-11: under build/ by default
    os.remove(f"{d}/mark")
    alone = run(d, "-j1")
    assert alone.returncode == 1 and "FAIL  test_a_waits.sh" in alone.stdout, alone.stdout
    # A failure keeps its folder and says where, and the prefix is where it all goes.
    prefix = f"{t}/prefix"
    repo(d, {"test_c_fails.sh": 'echo "$TMPDIR"; echo boom; exit 3\n', "test_d_passes.sh": 'echo "$TMPDIR"; : > "$TMPDIR/mine"\n',
             "test_e_gap.sh": "# gap: a known gap\nexit 1\n", "test_f_skips.sh": "# requires: cmd:no-such-program\n",
             "test_g.txt": "# not a test\n"})
    res = run(d, prefix=prefix)
    assert res.returncode == 1, res.stdout
    assert order(res.stdout) == ["test_c_fails.sh", "test_d_passes.sh", "test_e_gap.sh", "test_f_skips.sh", "test_g.txt:",
                                 "asgard_config.py"], res.stdout
    assert "(exit 3)" in res.stdout and "      boom" in res.stdout, res.stdout
    assert "2 failed, 1 known gaps, 1 skipped" in res.stdout, res.stdout
    kept = glob.glob(f"{prefix}/run.*")
    assert len(kept) == 1 and f"output and temp files: {kept[0]}" in res.stdout, (kept, res.stdout)
    logs = {name: open(f"{kept[0]}/{name}/output.log").read().splitlines()[0] for name in ("test_c_fails.sh", "test_d_passes.sh")}
    assert logs == {name: f"{kept[0]}/{name}/tmp" for name in logs}, logs                    # its own TMPDIR
    assert os.path.exists(f"{kept[0]}/test_d_passes.sh/tmp/mine")
    assert not os.path.exists(f"{d}/build"), "wrote outside the prefix"
    # An old failure's folder goes; the last one stays; and the filter and a bad -j still work.
    os.utime(kept[0], (1, 1))
    repo(d, TOGETHER)
    res = run(d, "-j", "2", "test_b", prefix=prefix)
    assert res.returncode == 0 and order(res.stdout) == ["test_b_marks.sh"], res.stdout
    assert not glob.glob(f"{prefix}/run.*"), "an old run's folder stayed"
    for bad in (["-j", "0"], ["-j", "x"], ["-j"]):
        assert run(d, *bad).returncode == 2, bad
print("ok")
