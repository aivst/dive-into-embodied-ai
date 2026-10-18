import assert from 'node:assert/strict';
import fs from 'node:fs';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import loadMujoco from '@mujoco/mujoco';
import {createSimulation} from '../codes/practices/quadruped/quaddle-mujoco/web/simulation.mjs';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const source = path.join(root, 'codes/practices/quadruped/quaddle-mujoco');
const files = [['scene.xml', new Uint8Array(fs.readFileSync(path.join(source, 'models/scene.xml')))]];
for (const file of fs.readdirSync(path.join(source, 'models/assets'))) files.push([`assets/${file}`, new Uint8Array(fs.readFileSync(path.join(source, 'models/assets', file)))]);
const sim = createSimulation(await loadMujoco(), files, JSON.parse(fs.readFileSync(path.join(source, 'gait.json'))));
const report = {engine: 'MuJoCo WASM 3.16.0', passed: false};
try {
  assert.equal(sim.model.nu, 4);
  assert.equal(sim.model.neq, 4);
  assert(sim.geometry.length > 30, 'Real visual meshes must be present');
  for (const mesh of sim.geometry) assert(Math.max(...mesh.faces) < mesh.vertices.length / 3, 'Local mesh indices must be valid');
  sim.step(2000);
  assert(sim.snapshot().upright > .95);
  sim.setMode('walk');
  let minUpright = 1;
  const initialY = sim.data.qpos[1];
  for (let i = 0; i < 600; i++) {
    sim.step(100);
    minUpright = Math.min(minUpright, sim.snapshot().upright);
    assert(sim.data.qpos[2] > .025, 'Robot must stay above ground');
    assert(sim.data.xfrc_applied.every(x => x === 0), 'No artificial base forces');
    assert(sim.data.qfrc_applied.every(x => x === 0), 'No artificial joint forces');
  }
  report.walkSeconds = 60;
  report.forwardMeters = initialY - sim.data.qpos[1];
  report.minUpright = minUpright;
  assert(report.forwardMeters > 3.5, 'Joint-driven gait must make real forward progress');
  assert(minUpright > .90, 'Gait must remain upright');
  sim.setMode('stand');
  sim.step(4000);
  report.stopSpeed = sim.snapshot().speed;
  assert(report.stopSpeed < .001, 'Stand must settle, not freeze a moving body');
  assert(sim.data.ctrl.every(x => x === 0));
  sim.reset();
  assert.equal(sim.data.time, 0);
  assert.equal(sim.mode, 'stand');
  assert.deepEqual(Array.from(sim.data.qpos.slice(0, 3)), [0, 0, .065]);
  report.passed = true;
  console.log(JSON.stringify(report, null, 2));
} finally { sim.dispose(); }
