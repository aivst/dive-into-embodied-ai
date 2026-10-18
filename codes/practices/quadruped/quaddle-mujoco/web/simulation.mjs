import {JointController} from './controller.mjs';

// Shared by the browser Worker and the real-WASM Node regression check.
export function createSimulation(mj, files, config) {
  const vfs = new mj.MjVFS();
  let model;
  try {
    for (const [name, bytes] of files) vfs.addBuffer(name, bytes);
    model = mj.MjModel.from_xml_path('scene.xml', vfs);
  } finally { vfs.delete(); }
  const data = new mj.MjData(model);
  const bodyId = mj.mj_name2id(model, 1, 'body');
  let controller = new JointController(config, bodyId);
  mj.mj_forward(model, data);
  const geometry = [];
  // Render the visual meshes only. Ground is drawn by the frontend; collision
  // proxies remain active in MuJoCo but invisible, just like the Python viewer.
  for (let id = 0; id < model.ngeom; id++) {
    if (model.geom_type[id] !== 7 || model.geom_group[id] === 3) continue;
    const mesh = model.geom_dataid[id];
    const va = 3 * model.mesh_vertadr[mesh], fa = 3 * model.mesh_faceadr[mesh];
    geometry.push({id, mesh,
      vertices: model.mesh_vert.slice(va, va + 3 * model.mesh_vertnum[mesh]),
      faces: model.mesh_face.slice(fa, fa + 3 * model.mesh_facenum[mesh]),
      color: model.geom_rgba.slice(id * 4, id * 4 + 4)});
  }
  return {
    model, data, geometry,
    get mode() { return controller.mode; },
    setMode(mode) {
      if (!['walk', 'stand'].includes(mode)) throw new Error('Unknown control mode');
      controller.mode = mode;
    },
    reset() {
      mj.mj_resetData(model, data);
      mj.mj_forward(model, data);
      controller = new JointController(config, bodyId);
    },
    step(count = 1) {
      for (let i = 0; i < count; i++) {
        const before = data.time;
        controller.update(data);
        mj.mj_step(model, data);
        if (data.time <= before || !data.qpos.every(Number.isFinite)) throw new Error('仿真状态异常，请重置后重试。');
      }
      // Publish transforms for the final qpos, not the previous physics substep.
      mj.mj_forward(model, data);
    },
    snapshot() {
      return {time: data.time, mode: controller.mode, position: data.qpos.slice(0, 3),
        speed: Math.hypot(data.qvel[0], data.qvel[1]),
        upright: data.xmat[bodyId * 9 + 8],
        positions: data.geom_xpos.slice(), rotations: data.geom_xmat.slice()};
    },
    dispose() { data.delete(); model.delete(); },
  };
}
