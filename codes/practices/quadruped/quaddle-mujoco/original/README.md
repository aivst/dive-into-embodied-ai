---
license: mit
tags:
  - robotics
  - urdf
  - ros
  - quadruped
  - robot-dog
  - open-source-robotics
  - physical-ai
  - embodied-robotics
  - stem-education
  - physical-ai-education
  - robotics-education
  - ai-education
---

# Quaddle URDF

A URDF (Unified Robot Description Format) model of Petoi's Quaddle — a 4-servo,
omnidirectional quadruped robot kit for physical AI learning & experiments.

**Try it now, no setup required: [Quaddle robot simulator](https://www.petoi.com/pages/quaddle-robot-simulator).**

**Watch it in action: [Teach Quaddle How to Walk, Race with Pose-Controlled Teleoperation](https://www.youtube.com/watch?v=8U3mROh88vQ).**

## About Quaddle

- Runs on [OpenCat](https://github.com/PetoiCamp/OpenCatEsp32-Quadruped-Robot/).
- Starting at $99. [Reserve yours on Kickstarter](https://www.kickstarter.com/projects/petoi/quaddle-open-source-desktop-robot-kit) — delivery is early December 2026.

## Contents

```
robot.urdf     — the robot description (single file, no ROS package.xml/CMakeLists)
assets/        — STL meshes referenced by robot.urdf via package://assets/*.stl
```

All visual geometry is defined with `package://assets/...` mesh URIs. This is a bare
URDF, not a full ROS package — a viewer/tool that doesn't already resolve `package://`
paths (e.g. a generic URDF viewer, or Python tooling like `yourdfpy`/`urdfpy`) may need
either a `ROS_PACKAGE_PATH` entry that maps `assets` to this directory, or the mesh
paths rewritten to plain relative paths (`assets/...`).

## Structure

The robot is modeled as a central `body` link with four identical leg assemblies —
`left_front`, `right_front`, `right_back`, `left_back` — each built from the same
per-leg joint pattern:

- **`<side>_thigh`** (revolute) — the driven hip joint, connecting the leg assembly to
  the body. One per leg; this is the actuated servo joint.
- **`<side>_motor_arm`**, **`<side>_leg`**, **`<side>_spring`** (revolute) — the
  passive four-bar linkage that converts the single hip servo's rotation into
  Quaddle's knee-lift walking gait (Petoi's "retro-mechanical" leg design — one motor
  drives the full leg motion instead of a separate knee actuator).
- **`<side>_wheel`**, **`<side>_wheel_tip`** (continuous) — the rolling foot tip at
  the end of each leg, enabling Quaddle's omnidirectional movement (walk, strafe,
  spin in place) without extra actuators.
- **`<side>_knee`**, **`<side>_foot`**, `body_collision`, and the `closing_*` links —
  fixed, zero-mass dummy frames used for collision geometry and linkage closure, not
  physical parts.

Totals: 46 links, 45 joints (16 revolute, 8 continuous, 21 fixed).

- The longer spring in the legs is a stainless steel tension spring: 0.5 × 4 × 35 mm (wire diameter × outer diameter × length).

- The smaller spring inside the legs is a spring-steel compression spring with 5 coils: 0.3 × 5 × 10 mm (wire diameter × outer diameter × length).

- The servos provide approximately 2.5 kg·cm of torque.

- The body is made of PETG or POM, which should have little impact on the overall mechanics.

## Viewing the model

Any URDF-compatible viewer should work once mesh paths resolve correctly, for example:

```bash
# ROS 2 (if available)
ros2 launch urdf_tutorial display.launch.py model:=robot.urdf

# Or a standalone Python viewer
pip install yourdfpy
python3 -c "import yourdfpy; yourdfpy.URDF.load('robot.urdf').show()"
```

## License

MIT — see [LICENSE](LICENSE).
