"""Residual-control Gymnasium environment; the webpage still uses the baseline.

Policy action order: left_front, right_front, right_back, left_back.
An all-zero action reproduces the reference gait under this environment's
100 Hz zero-order-hold interface. No policy is loaded implicitly.
"""
from pathlib import Path
import math

import gymnasium as gym
from gymnasium import spaces
import mujoco
import numpy as np

from gait_controller import CONFIG, JointController

ROOT = Path(__file__).resolve().parent
SIDES = ("left_front", "right_front", "right_back", "left_back")


class QuaddleResidualEnv(gym.Env):
    metadata = {"render_modes": []}

    def __init__(self, episode_seconds=20., randomize=False):
        super().__init__()
        self.model = mujoco.MjModel.from_xml_path(str(ROOT / "models/scene.xml"))
        self.data = mujoco.MjData(self.model)
        self.frame_skip = 10
        self.dt = self.model.opt.timestep * self.frame_skip
        self.max_steps = round(episode_seconds / self.dt)
        self.randomize = randomize
        self.body_id = self.model.body("body").id
        self.body_geom = self.model.geom("body_contact").id
        self.ground_geom = self.model.geom("ground").id
        self.qids = np.array([self.model.jnt_qposadr[self.model.joint(s + "_thigh").id] for s in SIDES])
        self.vids = np.array([self.model.jnt_dofadr[self.model.joint(s + "_thigh").id] for s in SIDES])
        self.original_friction = self.model.geom_friction.copy()
        self.friction_ids = [self.ground_geom] + [i for i in range(self.model.ngeom) if "_wheel" in self.model.geom(i).name and "_contact_" in self.model.geom(i).name]
        self.action_space = spaces.Box(-1., 1., shape=(4,), dtype=np.float32)
        self.observation_space = spaces.Box(-np.inf, np.inf, shape=(32,), dtype=np.float32)
        self.command_speed = .075
        self.residual_scale = .12
        self.reference = np.zeros(4)
        self.previous_action = np.zeros(4)
        self.controller = None

    def _observation(self):
        rot = self.data.xmat[self.body_id].reshape(3, 3)
        velocity = np.zeros(6)
        mujoco.mj_objectVelocity(self.model, self.data, mujoco.mjtObj.mjOBJ_BODY, self.body_id, velocity, 1)
        elapsed = self.steps * self.dt
        phase = 2 * math.pi * CONFIG["frequency_hz"] * elapsed
        yaw = math.atan2(rot[1, 0], rot[0, 0])
        return np.concatenate((
            rot.T @ np.array([0., 0., -1.]),     # 3: projected gravity
            velocity[3:] / .1, velocity[:3] / 5.,  # 3 + 3: local linear/angular velocity
            self.data.qpos[self.qids], self.data.qvel[self.vids] / 10.,  # 4 + 4
            self.previous_action,                # 4
            [math.sin(phase), math.cos(phase), self.command_speed / .1],  # 2 + 1
            self.reference,                       # 4: reference joint targets
            [min(1., elapsed / CONFIG["ramp_seconds"]),  # 1
             (self.data.qpos[0] - self.start_position[0]) / .1, math.sin(yaw), math.cos(yaw)],  # 1 + 2
        )).astype(np.float32)

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        mujoco.mj_resetData(self.model, self.data)
        self.model.geom_friction[:] = self.original_friction
        if self.randomize:
            # Initial pose changes are reset-only. Do not disturb closed-loop joint geometry.
            yaw = self.np_random.uniform(-.03, .03)
            self.data.qpos[3:7] = [math.cos(yaw / 2), 0., 0., math.sin(yaw / 2)]
            self.model.geom_friction[self.friction_ids, 0] = self.np_random.uniform(.7, .9)
        mujoco.mj_forward(self.model, self.data)
        # Establish contact before collecting any policy transitions.
        for _ in range(round(2. / self.model.opt.timestep)):
            mujoco.mj_step(self.model, self.data)
        mujoco.mj_forward(self.model, self.data)
        self.controller = JointController("walk", config={**CONFIG, "settle_seconds": 0.})
        self.steps = 0
        self.previous_action.fill(0.)
        self.reference.fill(0.)
        self.last_target = self.data.ctrl.copy()
        self.start_position = self.data.qpos[:3].copy()
        self._done = False
        return self._observation(), {}

    def step(self, action):
        if self.controller is None or self._done:
            raise RuntimeError("Call reset before stepping a new episode")
        action = np.asarray(action, dtype=float)
        if action.shape != (4,) or not np.isfinite(action).all():
            raise ValueError("Expected four finite residual actions")
        action = np.clip(action, -1., 1.)
        self.controller(self.data)
        self.reference = self.data.ctrl.copy()
        desired = np.clip(self.reference + self.residual_scale * action, -1.2, 1.2)
        self.last_target += np.clip(desired - self.last_target, -8. * self.dt, 8. * self.dt)
        self.data.ctrl[:] = self.last_target
        fallen = False
        for _ in range(self.frame_skip):
            before = self.data.time
            mujoco.mj_step(self.model, self.data)
            if self.data.time <= before or not np.isfinite(self.data.qpos).all():
                self._done = True
                return np.zeros(32, dtype=np.float32), -2., True, False, {"failure": "nonfinite_or_reset"}
            fallen |= any(self.body_geom in (c.geom1, c.geom2) for c in self.data.contact)
        mujoco.mj_forward(self.model, self.data)
        self.steps += 1
        upright = float(self.data.xmat[self.body_id, 8])
        fallen |= upright < .7 or self.data.qpos[2] < .025
        vf = -float(self.data.qvel[1])  # Forward is world -Y in the official model.
        side = float(self.data.qvel[0])
        lateral = float(self.data.qpos[0] - self.start_position[0])
        terms = {
            "tracking": math.exp(-((vf - self.command_speed) / .05) ** 2),
            "upright": .3 * upright,
            "lateral": -.1 * (side / .1) ** 2 - .05 * (lateral / .1) ** 2,
            "bounce": -.05 * (float(self.data.qvel[2]) / .1) ** 2,
            "yaw": -.02 * (float(self.data.qvel[5]) / 2.) ** 2,
            "effort": -.01 * float(np.mean((self.data.actuator_force / .245) ** 2)),
            "smoothness": -.02 * float(np.mean((action - self.previous_action) ** 2)),
            "residual": -.01 * float(np.mean(action ** 2)),
        }
        reward = self.dt * sum(terms.values()) - (2. if fallen else 0.)
        self.previous_action = action.copy()
        terminated = bool(fallen)
        truncated = bool(self.steps >= self.max_steps and not terminated)
        self._done = terminated or truncated
        info = {"reward_terms": terms, "forward_m": float(self.start_position[1] - self.data.qpos[1]),
                "forward_speed": vf, "lateral_m": lateral, "upright": upright, "fallen": terminated,
                "episode_seconds": self.steps * self.dt}
        return self._observation(), float(reward), terminated, truncated, info
