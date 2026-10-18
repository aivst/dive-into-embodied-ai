"""Search periodic joint commands using actual MuJoCo dynamics; no base forcing."""
from concurrent.futures import ProcessPoolExecutor
from itertools import product
from pathlib import Path
import argparse
import json
import math
import time

import mujoco
import numpy as np

ROOT = Path(__file__).resolve().parent
SIGNS = np.array([1., -1., -1., 1.])
MODEL = None


def initialize():
    global MODEL, DATA, HOME
    MODEL = mujoco.MjModel.from_xml_path(str(ROOT / "models" / "scene.xml"))
    DATA = mujoco.MjData(MODEL)
    mujoco.mj_step(MODEL, DATA, nstep=2000)
    HOME = DATA.qpos.copy()


def command(t, p):
    # front/back amplitudes, front/back biases, Hz, RF/RB/LB phase, harmonic
    af, ab, bf, bb, hz, rf, rb, lb, harmonic = p
    phase = 2 * np.pi * hz * t + np.array([0, rf, rb, lb])
    waveform = (np.sin(phase) + harmonic * np.sin(2 * phase)) / (1 + abs(harmonic))
    ramp = min(1., t / 1.0)
    return SIGNS * ramp * (np.array([bf, bf, bb, bb]) + np.array([af, af, ab, ab]) * waveform)


def evaluate(p, seconds=8.0, details=False):
    if MODEL is None:
        initialize()
    m, d = MODEL, DATA
    mujoco.mj_resetData(m, d)
    d.qpos[:] = HOME
    mujoco.mj_forward(m, d)
    start = d.qpos[:3].copy()
    worst_z, upright, lateral, heading, body_hits = 1., 1., 0., 0., 0
    invalid = False
    distances = []
    for frame in range(round(seconds * 100)):
        d.ctrl[:] = command(frame / 100, p)
        mujoco.mj_step(m, d, nstep=10)
        mat = d.body("body").xmat.reshape(3, 3)
        up = mat[2, 2]
        yaw = abs(math.atan2(mat[1, 0], mat[0, 0]))
        worst_z = min(worst_z, d.qpos[2])
        upright = min(upright, up)
        heading = max(heading, yaw)
        lateral = max(lateral, abs(d.qpos[0] - start[0]))
        if frame % 20 == 0:
            body_id = m.geom("body_contact").id
            body_hits += int(any(body_id in (c.geom1, c.geom2) for c in d.contact))
        if not np.isfinite(d.qpos).all() or up < .6 or d.qpos[2] < .018 or d.warning.number.sum():
            invalid = True
            break
        if frame % 100 == 99:
            distances.append(float(start[1] - d.qpos[1]))
    forward = float(start[1] - d.qpos[1])
    # Reward travel, with penalties for sideways drift, yaw and belly contact.
    score = forward - 1.2 * lateral - .2 * heading - .08 * body_hits - max(0., .9 - upright)
    if invalid:
        score = -1 - max(0, .6 - upright)
    result = dict(params=list(map(float, p)), score=score, forward_m=forward,
                  lateral_m=lateral, max_heading_rad=heading, min_upright=upright,
                  min_height_m=worst_z, body_contact_samples=body_hits,
                  simulated_seconds=float(d.time), invalid=invalid, distances_m=distances)
    return result if details else score


def trial(p):
    return evaluate(p, details=True)


def loss(p):
    return -evaluate(p)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--optimize", action="store_true")
    args = parser.parse_args()
    (ROOT / 'outputs').mkdir(exist_ok=True)
    if args.optimize:
        from scipy.optimize import differential_evolution
        generation = 0
        def progress(x, convergence):
            nonlocal generation
            generation += 1
            record=evaluate(x, details=True)
            print(json.dumps(dict(generation=generation, best=record)),flush=True)
            (ROOT/'outputs'/'gait_search_best.json').write_text(json.dumps(record,indent=2)+'\n')
        bounds=[(.15,.85),(.15,.85),(-.6,.35),(-.6,.35),(1,4.5),(0,2*np.pi),(0,2*np.pi),(0,2*np.pi),(-.6,.6)]
        with ProcessPoolExecutor(args.workers, initializer=initialize) as pool:
            result=differential_evolution(loss,bounds,maxiter=28,popsize=9,seed=17,
                workers=pool.map,updating='deferred',polish=False,callback=progress)
        print(json.dumps(evaluate(result.x,30,True),indent=2),flush=True)
        return
    patterns = [[0, 0, 0], [np.pi, 0, np.pi], [np.pi, np.pi, 0], [0, np.pi, np.pi], [np.pi, np.pi/2, 3*np.pi/2]]
    samples = [[a, a, b, b, hz, *phase, h] for phase, a, hz, b, h in product(patterns, [.3, .55, .8], [1., 2., 3.], [-.25, .15], [0.])]
    results = []
    t0 = time.monotonic()
    with ProcessPoolExecutor(args.workers, initializer=initialize) as pool:
        for r in pool.map(trial, samples):
            results.append(r)
            if len(results) % 15 == 0:
                best = max(results, key=lambda r:r['score'])
                print(json.dumps(dict(done=len(results), total=len(samples), seconds=time.monotonic()-t0, best=best)), flush=True)
    results.sort(key=lambda r:r['score'], reverse=True)
    (ROOT/'outputs'/'gait_search_grid.json').write_text(json.dumps(results, indent=2)+'\n')
    print(json.dumps(results[:5], indent=2), flush=True)


if __name__ == '__main__':
    main()
