"""Run every test_*.py against the scratch ComfyUI and summarise.

    python tests/run_all.py            # all
    python tests/run_all.py mask yaw   # only tests whose name contains a word

Exit code is the number of failures. Each test prints its own JSON report; the
last line of each is kept here so a failure shows its VERDICT block.
"""
import glob
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from _common import BASE, INPUT_DIR, PANO, server_up  # noqa: E402

if not server_up():
    print(f"no ComfyUI answering on {BASE} -- see tests/README.md")
    sys.exit(1)
if not os.path.isfile(os.path.join(INPUT_DIR, PANO)):
    print(f"{PANO} missing from {INPUT_DIR}; writing the marker panoramas first")
    subprocess.call([sys.executable, os.path.join(HERE, "make_testpano.py")])

words = [w.lower() for w in sys.argv[1:]]
tests = sorted(glob.glob(os.path.join(HERE, "test_*.py")))
if words:
    tests = [t for t in tests if any(w in os.path.basename(t).lower() for w in words)]

results = []
for t in tests:
    name = os.path.basename(t)
    t0 = time.time()
    proc = subprocess.run([sys.executable, t], capture_output=True, text=True,
                          env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    secs = time.time() - t0
    out = (proc.stdout or "").strip().splitlines()
    status = {0: "PASS", 2: "SKIP"}.get(proc.returncode, "FAIL")
    results.append((name, status, secs))
    print(f"{status:4}  {name:34} {secs:5.1f}s")
    if status == "FAIL":
        tail = "\n".join(out[-25:]) if out else (proc.stderr or "").strip()[-1500:]
        print("      " + tail.replace("\n", "\n      "))

fails = sum(1 for _, s, _ in results if s == "FAIL")
print(f"\n{len(results) - fails}/{len(results)} passed")
sys.exit(fails)
