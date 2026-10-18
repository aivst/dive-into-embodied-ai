// JavaScript port of gait_controller.py; targets only, never floating-base forces.
const clip = (x, lo, hi) => Math.max(lo, Math.min(hi, x));
export class JointController {
  constructor(config, bodyId, mode = 'stand') {
    this.config = config;
    this.bodyId = bodyId;
    this.mode = mode;
    this.lastMode = null;
    this.lastTime = -1;
    this.target = new Float64Array(4);
  }
  update(data) {
    const c = this.config;
    if (this.mode !== this.lastMode || data.time < this.lastTime) {
      this.start = data.time;
      this.from = data.ctrl.slice();
      this.lastMode = this.mode;
      this.tick = -1;
      this.target.fill(0);
      this.startX = data.qpos[0];
    }
    this.lastTime = data.time;
    const elapsed = data.time - this.start;
    if (this.mode === 'walk') {
      const tick = Math.floor(Math.max(0, elapsed - c.settle_seconds) * c.control_hz + 1e-8);
      if (tick !== this.tick) {
        this.tick = tick;
        const t = tick / c.control_hz;
        const ramp = Math.min(1, t / c.ramp_seconds);
        const r = this.bodyId * 9;
        const yaw = Math.atan2(data.xmat[r + 3], data.xmat[r]);
        const error = yaw + c.lateral_kp * (data.qpos[0] - this.startX);
        const steer = clip(c.heading_kp * error + c.heading_kd * data.qvel[5], -c.steering_limit, c.steering_limit);
        for (let i = 0; i < 4; i++) {
          let phase = 2 * Math.PI * c.frequency_hz * t + c.phase_rad[i];
          let wave;
          if (c.waveform === 'cosine_duty') {
            const cycle = ((phase / (2 * Math.PI)) % 1 + 1) % 1;
            const duty = c.sweep_fraction;
            phase = cycle < duty ? Math.PI * cycle / duty : Math.PI + Math.PI * (cycle - duty) / (1 - duty);
            wave = Math.cos(phase);
          } else {
            wave = (Math.sin(phase) + c.harmonic * Math.sin(2 * phase)) / (1 + Math.abs(c.harmonic));
          }
          const sign = c.actuator_signs[i];
          const target = clip(sign * ramp * (c.bias_rad[i] + c.amplitude_rad[i] * (1 + steer * sign) * wave), -1.2, 1.2);
          const delta = c.max_target_speed_rad_s / c.control_hz;
          this.target[i] += clip(target - this.target[i], -delta, delta);
        }
      }
    } else {
      this.target.fill(0);
    }
    let blend = clip(elapsed / .35, 0, 1);
    blend = blend * blend * (3 - 2 * blend);
    for (let i = 0; i < 4; i++) data.ctrl[i] = (1 - blend) * this.from[i] + blend * this.target[i];
  }
}
