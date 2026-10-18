import loadMujoco from './mujoco.js';
import {createSimulation} from './simulation.mjs';

let sim, timer, paused = false, visible = true, previous = 0, debt = 0;
const sendState = () => {
  const state = sim.snapshot();
  postMessage({type: 'state', ...state, paused}, [state.positions.buffer, state.rotations.buffer, state.position.buffer]);
};
function fail(error) {
  clearTimeout(timer);
  paused = true;
  postMessage({type: 'error', message: error instanceof Error ? error.message : String(error)});
}
function tick() {
  try {
    const now = performance.now();
    // No catch-up burst after a background tab or a slow device. Simulation
    // time is shown explicitly and may progress slower than wall time.
    if (!paused && visible) {
      debt = Math.min(debt + (now - previous) / 1000, .05);
      const count = Math.floor(debt / sim.model.opt.timestep);
      if (count) { sim.step(count); debt -= count * sim.model.opt.timestep; }
      sendState();
    }
    previous = now;
    timer = setTimeout(tick, 16);
  } catch (error) { fail(error); }
}
async function initialize() {
  const get = async (name, json = false) => {
    const response = await fetch(new URL(name, import.meta.url));
    if (!response.ok) throw new Error(`加载 ${name} 失败 (${response.status})`);
    return json ? response.json() : new Uint8Array(await response.arrayBuffer());
  };
  const [mj, manifest, config] = await Promise.all([loadMujoco(), get('manifest.json', true), get('gait.json', true)]);
  const files = await Promise.all(manifest.files.map(async name => [name, await get(name)]));
  sim = createSimulation(mj, files, config);
  postMessage({type: 'ready', geometry: sim.geometry, version: manifest.version});
  sendState();
  previous = performance.now();
  tick();
}
onmessage = ({data}) => {
  try {
    if (!sim) return;
    if (data.type === 'mode') { sim.setMode(data.mode); paused = false; }
    if (data.type === 'pause') paused = data.value;
    if (data.type === 'visibility') visible = data.value;
    if (data.type === 'reset') { sim.reset(); paused = false; }
    debt = 0;
    previous = performance.now();
    sendState();
  } catch (error) { fail(error); }
};
initialize().catch(fail);
