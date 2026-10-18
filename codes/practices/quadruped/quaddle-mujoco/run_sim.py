"""Interactive MuJoCo viewer with a locally searched walking gait."""
import argparse
import json
from pathlib import Path
from queue import SimpleQueue
import time

import mujoco
import mujoco.viewer
import numpy as np

from gait_controller import JointController

ROOT = Path(__file__).resolve().parent
SIDES = ("left_front", "right_front", "right_back", "left_back")


def load():
    model = mujoco.MjModel.from_xml_path(str(ROOT / "models" / "scene.xml"))
    return model, mujoco.MjData(model)


def camera_and_options(data):
    cam = mujoco.MjvCamera()
    cam.lookat[:] = data.body("body").xpos
    cam.distance, cam.azimuth, cam.elevation = 0.34, 135, -23
    opt = mujoco.MjvOption()
    opt.geomgroup[3] = 0  # Collision proxies can be enabled through the viewer UI.
    opt.sitegroup[:] = 0
    return cam, opt


def closure_error(data):
    return max(float(np.linalg.norm(
        data.site(f"closing_{side}_leg_1_anchor").xpos
        - data.site(f"closing_{side}_leg_2_anchor").xpos
    )) for side in SIDES)


def validate(duration=30.0, mode="stand"):
    m, d = load()
    mujoco.mj_forward(m, d)
    max_closure, max_force = 0.0, 0.0
    min_z, max_z, min_upright = float("inf"), -float("inf"), 1.0
    max_body_contacts, max_contacts = 0, 0
    qmin, qmax = np.full(4, np.inf), np.full(4, -np.inf)
    finite, monotonic = True, True
    previous_time = -1.0
    t0 = time.perf_counter()
    body_geom = m.geom("body_contact").id
    controller = JointController(mode)
    for _ in range(round(duration / m.opt.timestep)):
        controller(d)
        mujoco.mj_step(m, d)
        finite &= bool(np.isfinite(d.qpos).all() and np.isfinite(d.qvel).all())
        monotonic &= bool(d.time > previous_time)
        previous_time = d.time
        # Recompute kinematics for exact final-state diagnostics.
        mujoco.mj_forward(m, d)
        max_closure = max(max_closure, closure_error(d))
        max_force = max(max_force, float(np.max(np.abs(d.actuator_force))))
        if d.time > 2.0:
            min_z, max_z = min(min_z, d.qpos[2]), max(max_z, d.qpos[2])
            min_upright = min(min_upright, float(d.body("body").xmat[8]))
            max_contacts = max(max_contacts, d.ncon)
            max_body_contacts = max(max_body_contacts, sum(body_geom in (c.geom1, c.geom2) for c in d.contact))
            q = np.array([d.joint(s + "_thigh").qpos[0] for s in SIDES])
            qmin, qmax = np.minimum(qmin, q), np.maximum(qmax, q)
    warning_count = int(d.warning.number.sum())
    passed = finite and monotonic and warning_count == 0 and max_closure < 0.001 and min_z > 0.025 and min_upright > 0.8 and max_body_contacts == 0 and max_contacts > 0
    if mode == "motion":
        passed &= bool(np.all(qmax - qmin > 0.1))
    return dict(mode=mode, simulation_seconds=float(d.time), wall_seconds=time.perf_counter() - t0,
                finite=finite, monotonic_time=monotonic, warning_count=warning_count,
                max_closure_error_m=max_closure, max_actuator_force_Nm=max_force,
                settled_root_z_range_m=[float(min_z), float(max_z)], minimum_upright_cosine=min_upright,
                max_body_ground_contacts=max_body_contacts, max_ground_contacts=max_contacts,
                driven_joint_range_rad=(qmax - qmin).tolist(), passed=bool(passed))


def interactive(mode, duration):
    m, d = load()
    mujoco.mj_forward(m, d)
    events = SimpleQueue()
    paused = False
    controller = JointController(mode)
    print("Quaddle / MuJoCo - local approximate model", flush=True)
    print("W: walk, S: stand, M: cycle modes, R: reset, Space: pause. Mouse: orbit/zoom.", flush=True)
    print("Walking uses joint targets only. Dynamics remain approximate and uncalibrated.", flush=True)
    with mujoco.viewer.launch_passive(m, d, key_callback=events.put,
                                     show_left_ui=False, show_right_ui=False) as viewer:
        cam, opt = camera_and_options(d)
        viewer.cam.lookat[:], viewer.cam.distance = cam.lookat, cam.distance
        viewer.cam.azimuth, viewer.cam.elevation = cam.azimuth, cam.elevation
        viewer.opt.geomgroup[:] = opt.geomgroup
        viewer.opt.sitegroup[:] = opt.sitegroup
        start = time.monotonic()
        while viewer.is_running() and (duration <= 0 or time.monotonic() - start < duration):
            frame_start = time.monotonic()
            while not events.empty():
                key = events.get()
                if key == ord(" "):
                    paused = not paused
                elif key == ord("R"):
                    mujoco.mj_resetData(m, d)
                    mujoco.mj_forward(m, d)
                elif key == ord("M"):
                    modes = ["stand", "motion", "walk"]
                    controller.mode = modes[(modes.index(controller.mode) + 1) % len(modes)]
                    print("mode:", controller.mode, flush=True)
                elif key == ord("W"):
                    controller.mode = "walk"
                    print("mode: walk", flush=True)
                elif key == ord("S"):
                    controller.mode = "stand"
                    print("mode: stand", flush=True)
                elif key in (ord("+"), ord("=")):
                    controller.amplitude = min(controller.amplitude + 0.025, 0.25)
                elif key == ord("-"):
                    controller.amplitude = max(controller.amplitude - 0.025, 0.0)
            if not paused:
                for _ in range(16):
                    controller(d)
                    mujoco.mj_step(m, d)
            viewer.cam.lookat[:] = d.body("body").xpos
            viewer.sync()
            time.sleep(max(0.0, 0.016 - (time.monotonic() - frame_start)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["stand", "motion", "walk"], default="walk")
    parser.add_argument("--duration", type=float, default=0, help="Viewer wall seconds; 0 keeps it open")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()
    if args.validate:
        results = [validate(args.duration or 30, mode) for mode in ("stand", "motion")]
        out = ROOT / "outputs"
        out.mkdir(exist_ok=True)
        (out / "validation.json").write_text(json.dumps(results, indent=2) + "\n")
        print(json.dumps(results, indent=2))
        raise SystemExit(0 if all(r["passed"] for r in results) else 1)
    interactive(args.mode, args.duration)


if __name__ == "__main__":
    main()
