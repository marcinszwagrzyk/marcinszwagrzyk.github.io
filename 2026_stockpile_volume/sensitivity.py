# -*- coding: utf-8 -*-
"""Sensitivity test of the radargrammetry: a known height step injected into real S1 images.

The stockpile content is shifted towards the satellite by Δh · cot θ from one
quarter onwards (cubic sub-pixel resampling), the network is solved again and
the recovered step compared with the injected one. Run after analysis.py
(needs the footprint); analysis.py then uses the result as calibration.
"""
import json

import numpy as np
from scipy import ndimage

import analysis as A
import config as C


def run(step_m, q0):
    labels = [q[0] for q in C.quarters()]
    I = A.s1_stack(labels)
    m = np.load(C.DATA / "results.npz")["m10"]
    win = A.measurement_window(m)
    base, _ = A.network(I, win)
    d = step_m * A.COT / C.RES_S1                    # px towards the satellite
    sh = (d * A.U_S, d * A.U_E)                      # (rows towards south, cols towards east)
    moving = ndimage.binary_dilation(m, iterations=3)
    J = I.copy()
    for q in range(q0, len(J)):
        moved = ndimage.shift(np.nan_to_num(J[q], nan=-15), sh, order=3, mode="nearest")
        J[q] = np.where(moving, moved, J[q])
    test, _ = A.network(J, win)
    rec = test - base
    out = dict(injected_m=step_m, from_quarter=labels[q0],
               recovered_after_m=float(np.nanmedian(rec[q0:])), recovered_before_m=float(np.nanmedian(rec[:q0])))
    print(out)
    return out


if __name__ == "__main__":
    q0 = len(C.quarters()) // 2
    res = [run(3.0, q0), run(-3.0, q0), run(6.0, q0)]
    json.dump(res, open(C.OUT / "sensitivity_test.json", "w"), indent=2)
