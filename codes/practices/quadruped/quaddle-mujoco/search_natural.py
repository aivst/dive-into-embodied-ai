"""Search phase-constrained gaits against the unchanged approximate model.

The evaluation uses the interactive controller, real ground contact velocities,
and no forces or floating-base state changes. Angles are physical joint targets.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor
import hashlib
import json
import math
from pathlib import Path
import time

import mujoco
import numpy as np

from gait_controller import JointController

ROOT = Path(__file__).resolve().parent
SIDES = ("left_front", "right_front", "right_back", "left_back")
MODEL = None
PATTERN = "trot"


def initialize(pattern="trot"):
    global MODEL, PATTERN
    PATTERN = pattern
    MODEL = mujoco.MjModel.from_xml_path(str(ROOT / "models/scene.xml"))


def configuration(p, pattern="trot"):
    amplitude, ratio, front_bias, back_bias, hz, sweep, kp = p
    phases = [0., np.pi, 0., np.pi] if pattern == "trot" else [0., np.pi, np.pi/2, 3*np.pi/2]
    return dict(name="coordinated_" + pattern, joint_order=list(SIDES),
                actuator_signs=[1, -1, -1, 1],
                amplitude_rad=[amplitude, amplitude, amplitude*ratio, amplitude*ratio],
                bias_rad=[front_bias, front_bias, back_bias, back_bias],
                phase_rad=phases, frequency_hz=hz, waveform="cosine_duty",
                sweep_fraction=sweep, harmonic=0., control_hz=100,
                settle_seconds=2., ramp_seconds=1.5, heading_kp=kp,
                heading_kd=.03, lateral_kp=2., steering_limit=.2,
                max_target_speed_rad_s=8.,
                note="Phase-constrained local gait; unchanged approximate mechanics; not hardware calibrated.")


def measure(config, seconds=10., friction=None, trace=False):
    if MODEL is None:
        initialize()
    m = MODEL
    saved_friction = m.geom_friction.copy()
    if friction is not None:
        m.geom_friction[:, 0] = friction
    d = mujoco.MjData(m)
    mujoco.mj_forward(m, d)
    controller = JointController("walk", config=config)
    ground = m.geom("ground").id
    belly = m.geom("body_contact").id
    shin = {m.geom(s+"_leg_contact").id for s in SIDES}
    foot_sets = [{i for i in range(m.ngeom) if m.geom(i).name.startswith(s+"_wheel") and "_contact_" in m.geom(i).name} for s in SIDES]
    foot_ids = set().union(*foot_sets)
    joint_ids = [m.jnt_dofadr[m.joint(s+"_thigh").id] for s in SIDES]
    foot_body_ids = [m.body(s+"_wheel_tip").id for s in SIDES]
    samples, slips, contacts, positions, velocities, heights, tilts = [], [], [], [], [], [], []
    max_speed, max_torque, max_side, max_yaw, body_hits, shin_hits, min_up = 0., 0., 0., 0., 0, 0, 1.
    start = None
    jac = np.zeros((3, m.nv))
    for k in range(round((config["settle_seconds"] + seconds)*100)):
        controller(d)
        mujoco.mj_step(m, d, nstep=10)
        max_speed = max(max_speed, float(np.abs(d.qvel[joint_ids]).max()))
        max_torque = max(max_torque, float(np.abs(d.actuator_force).max()))
        if d.time < config["settle_seconds"]:
            continue
        if start is None:
            start = d.qpos[:3].copy()
        rot = d.body("body").xmat.reshape(3,3)
        up = float(rot[2,2])
        yaw = math.atan2(rot[1,0], rot[0,0])
        min_up = min(min_up, up)
        max_side = max(max_side, abs(float(d.qpos[0]-start[0])))
        max_yaw = max(max_yaw, abs(yaw))
        ground_contacts = [(c, c.geom2 if c.geom1 == ground else c.geom1) for c in d.contact if ground in (c.geom1, c.geom2)]
        ground_ids = {g for c,g in ground_contacts}
        body_hits += int(belly in ground_ids)
        shin_hits += int(bool(shin & ground_ids))
        if min_up < .65 or d.warning.number.sum() or not np.isfinite(d.qpos).all():
            break
        if d.time < config["settle_seconds"] + config["ramp_seconds"] + .5:
            continue
        active = [bool(ids & ground_ids) for ids in foot_sets]
        contacts.append(active)
        positions.append(d.qpos[:3].copy())
        velocities.append(d.qvel[:3].copy())
        heights.append(d.xpos[foot_body_ids, 2].copy())
        tilts.append(math.acos(np.clip(up, -1., 1.)))
        if k % 5 == 0:
            # Tangential speed at the actual surface contact includes wheel
            # rotation, unlike foot-centre speed, which mislabels rolling as slip.
            for contact, geom in ground_contacts:
                if geom in foot_ids or geom in shin:
                    mujoco.mj_jac(m, d, jac, None, contact.pos, m.geom_bodyid[geom])
                    slips.append(float(np.linalg.norm((jac @ d.qvel)[:2])))
            if trace:
                samples.append(dict(t=round(float(d.time),3), forward=float(start[1]-d.qpos[1]),
                    height=float(d.qpos[2]), contact=active, tip_z=d.xpos[foot_body_ids,2].tolist()))
    m.geom_friction[:] = saved_friction
    forward = float(start[1] - d.qpos[1]) if start is not None else 0.
    complete = d.time >= config["settle_seconds"] + seconds - .01
    if len(contacts) < 5:
        return dict(score=-10., forward_m=forward, complete=False, min_up=min_up, config=config)
    c = np.asarray(contacts, dtype=float)
    pos = np.asarray(positions)
    vel = np.asarray(velocities)
    height = np.asarray(heights)
    contact_fraction = c.mean(axis=0)
    slip = float(np.mean(slips)) if slips else 1.
    z_std = float(np.std(pos[:,2]))
    vz_rms = float(np.sqrt(np.mean(vel[:,2]**2)))
    tilt_rms = float(np.sqrt(np.mean(np.square(tilts))))
    foot_range = np.ptp(height, axis=0)
    pair_error = float(np.mean(np.abs(c[:,0]-c[:,2]) + np.abs(c[:,1]-c[:,3]))/2)
    alternation = float(np.mean(np.abs(c[:,0]-c[:,1]) + np.abs(c[:,2]-c[:,3]))/2)
    # Stop rewarding speed beyond a modest walking speed. The remaining terms
    # prefer low slip, low bounce, an upright torso and actual alternating feet.
    score = (8*min(forward/seconds, .075) - 1.8*slip - 22*z_std - .8*vz_rms
             - .5*tilt_rms - .6*max_side - .08*max_yaw
             - 15*body_hits/(seconds*100) - .1*shin_hits/(seconds*100)
             - .3*float(np.maximum(.003-foot_range,0).sum()/.003)
             - .3*float(np.maximum(contact_fraction-.88,0).sum())
             - .3*float(np.maximum(.12-contact_fraction,0).sum())
             - .015*max(0, max_speed-10))
    if config["name"].endswith("trot"):
        score += .12*alternation - .12*pair_error
    if not complete or min_up < .85:
        score -= 3 + max(0, .85-min_up)*5
    result = dict(score=score, forward_m=forward, speed_m_s=forward/seconds,
                  complete=bool(complete), min_up=min_up, body_contacts=body_hits,
                  shin_contact_fraction=shin_hits/max(1, round(seconds*100)),
                  max_side_m=max_side, max_yaw_deg=math.degrees(max_yaw),
                  contact_slip_m_s=slip, torso_height_std_m=z_std,
                  torso_vertical_speed_rms_m_s=vz_rms, tilt_rms_deg=math.degrees(tilt_rms),
                  foot_height_range_m=foot_range.tolist(), foot_contact_fraction=contact_fraction.tolist(),
                  diagonal_contact_mismatch=pair_error, left_right_alternation=alternation,
                  max_joint_speed_rad_s=max_speed, max_torque_Nm=max_torque,
                  config=config)
    if trace:
        result["trace"] = samples
    return result


def objective(p):
    return -measure(configuration(p, PATTERN))["score"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--generations", type=int, default=20)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--compare", action="store_true")
    parser.add_argument("--pattern", choices=["trot", "crawl"], default="trot")
    parser.add_argument("--resume", type=Path)
    args = parser.parse_args()
    (ROOT/"outputs").mkdir(exist_ok=True)
    if args.compare:
        records = {}
        for name, file in [("previous", ROOT/"reference/previous-gait.json"), ("current", ROOT/"gait.json")]:
            records[name] = measure(json.loads(file.read_text()), seconds=20, trace=True)
        records["model_sha256"] = hashlib.sha256((ROOT/"models/scene.xml").read_bytes()).hexdigest()
        records["controller_sha256"] = hashlib.sha256((ROOT/"gait_controller.py").read_bytes()).hexdigest()
        (ROOT/"outputs/gait_comparison.json").write_text(json.dumps(records,indent=2)+"\n")
        print(json.dumps({k:{a:b for a,b in v.items() if a not in ("trace","config")} for k,v in records.items() if isinstance(v,dict)},indent=2))
        return
    from scipy.optimize import differential_evolution
    iteration = 0
    clock = time.monotonic()
    def progress(x, convergence):
        nonlocal iteration
        iteration += 1
        record = measure(configuration(x, args.pattern))
        record.update(params=x.tolist(), iteration=iteration)
        (ROOT/f"outputs/natural_{args.pattern}_best.json").write_text(json.dumps(record,indent=2)+"\n")
        print(json.dumps(dict(iteration=iteration, wall_s=round(time.monotonic()-clock),
            **{k:v for k,v in record.items() if k not in ("config","params","iteration")})), flush=True)
    bounds = [(.2,.7),(.8,1.2),(-.7,.35),(-.7,.35),(.7,2.),(.3,.7),(-1.,1.)]
    extra = {}
    if args.resume:
        center = np.array(json.loads(args.resume.read_text())["params"])
        rng = np.random.default_rng(431)
        lo, hi = np.array(bounds).T
        population = np.clip(center + rng.normal(size=(56,7))*(hi-lo)*.08, lo, hi)
        population[0] = center
        extra["init"] = population
    with ProcessPoolExecutor(args.workers, initializer=initialize, initargs=(args.pattern,)) as pool:
        result = differential_evolution(objective, bounds, popsize=8, maxiter=args.generations,
            seed=271, workers=pool.map, updating="deferred", polish=False, callback=progress, **extra)
    progress(result.x, 0)


if __name__ == "__main__":
    main()
