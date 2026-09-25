"""Smoke test before sealing: run every cell once with replicate index 99999, outside the sealed replicate
range 0..199, and report only whether it ran (grades are not printed or stored)."""

import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import positive_controls as PC  # noqa: E402

if __name__ == "__main__":
    jobs = [(c[0], c[1], c[2], c[3], c[4], 99999) for c in PC.CELLS]
    ok = 0
    with ProcessPoolExecutor(len(jobs)) as ex:
        futs = [ex.submit(PC.run_one, j) for j in jobs]
        for j, f in zip(jobs, futs):
            try:
                f.result()
                ok += 1
            except Exception as e:  # noqa: BLE001
                print("ERROR", j[0], type(e).__name__, e)
    print("cells ran without error:", ok, "of", len(jobs))
