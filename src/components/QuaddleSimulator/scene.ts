import * as THREE from 'three';
import {OrbitControls} from 'three/addons/controls/OrbitControls.js';

export type Geometry = {id: number; mesh: number; vertices: Float32Array; faces: Int32Array; color: Float32Array};
export type Snapshot = {time: number; mode: 'walk' | 'stand'; paused: boolean; position: Float64Array; speed: number; upright: number; positions: Float64Array; rotations: Float64Array};

export function createScene(host: HTMLElement, onLost: () => void) {
  const renderer = new THREE.WebGLRenderer({antialias: true});
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.setClearColor('#e8edf3');
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.domElement.setAttribute('aria-label', 'Quaddle 实时物理仿真，拖动旋转视角，滚轮缩放');
  renderer.domElement.setAttribute('role', 'img');
  host.appendChild(renderer.domElement);
  renderer.domElement.addEventListener('webglcontextlost', onLost);
  const scene = new THREE.Scene();
  scene.fog = new THREE.Fog('#e8edf3', 1.8, 8);
  const camera = new THREE.PerspectiveCamera(42, 1, .001, 100);
  camera.up.set(0, 0, 1);
  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.enablePan = false;
  controls.minDistance = .15;
  controls.maxDistance = 1.5;
  controls.maxPolarAngle = Math.PI / 2 - .02;
  scene.add(new THREE.AmbientLight(0xffffff, .9));
  const key = new THREE.DirectionalLight(0xfff8ed, 2.2);
  key.position.set(.5, -.4, 1);
  scene.add(key);
  const fill = new THREE.DirectionalLight(0xd6e7ff, .6);
  fill.position.set(-.4, .5, .4);
  scene.add(fill);

  const tile = document.createElement('canvas');
  tile.width = tile.height = 2;
  const ctx = tile.getContext('2d')!;
  ctx.fillStyle = '#b6c4d1'; ctx.fillRect(0, 0, 2, 2);
  ctx.fillStyle = '#d2dce5'; ctx.fillRect(0, 0, 1, 1); ctx.fillRect(1, 1, 1, 1);
  const texture = new THREE.CanvasTexture(tile);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.wrapS = texture.wrapT = THREE.RepeatWrapping;
  texture.magFilter = THREE.NearestFilter;
  texture.repeat.set(2500, 2500);
  texture.anisotropy = Math.min(8, renderer.capabilities.getMaxAnisotropy());
  const floor = new THREE.Mesh(new THREE.PlaneGeometry(200, 200), new THREE.MeshStandardMaterial({map: texture, roughness: 1}));
  scene.add(floor);
  const robot = new Map<number, THREE.Mesh>();
  const geometries = new Map<number, THREE.BufferGeometry>();
  const materials: THREE.Material[] = [];
  let body = new THREE.Vector3(0, 0, .05);
  let active = true, frame = 0;
  const rotation = new THREE.Matrix4();
  function resetView() {
    controls.target.copy(body);
    camera.position.copy(body).add(new THREE.Vector3(.25, -.28, .20));
    controls.update();
  }
  resetView();
  const resize = new ResizeObserver(() => {
    const width = host.clientWidth, height = host.clientHeight;
    if (!width || !height) return;
    renderer.setSize(width, height, false);
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
  });
  resize.observe(host);
  function render() {
    frame = requestAnimationFrame(render);
    if (active && !document.hidden) { controls.update(); renderer.render(scene, camera); }
  }
  render();
  return {
    resetView,
    setVisible(value: boolean) { active = value; },
    load(meshes: Geometry[]) {
      for (const item of meshes) {
        let geo = geometries.get(item.mesh);
        if (!geo) {
          geo = new THREE.BufferGeometry();
          geo.setAttribute('position', new THREE.BufferAttribute(item.vertices, 3));
          geo.setIndex(new THREE.BufferAttribute(new Uint32Array(item.faces), 1));
          geo.computeVertexNormals();
          geometries.set(item.mesh, geo);
        }
        const material = new THREE.MeshStandardMaterial({color: new THREE.Color(item.color[0], item.color[1], item.color[2]), roughness: .65, metalness: .12});
        materials.push(material);
        const mesh = new THREE.Mesh(geo, material);
        scene.add(mesh);
        robot.set(item.id, mesh);
      }
    },
    update(state: Snapshot) {
      const next = new THREE.Vector3(...Array.from(state.position) as [number, number, number]);
      const delta = next.clone().sub(body);
      camera.position.add(delta);
      controls.target.add(delta);
      body = next;
      // Recenter by a whole 8 cm tile pair. This preserves checker phase while
      // retaining visible ground however far the robot travels.
      floor.position.set(Math.round(body.x / .08) * .08, Math.round(body.y / .08) * .08, -.0001);
      for (const [id, mesh] of robot) {
        const p = id * 3, r = id * 9, m = state.rotations;
        mesh.position.fromArray(state.positions, p);
        rotation.set(m[r], m[r+1], m[r+2], 0, m[r+3], m[r+4], m[r+5], 0, m[r+6], m[r+7], m[r+8], 0, 0, 0, 0, 1);
        mesh.quaternion.setFromRotationMatrix(rotation);
      }
    },
    dispose() {
      cancelAnimationFrame(frame);
      resize.disconnect(); controls.dispose();
      renderer.domElement.removeEventListener('webglcontextlost', onLost);
      for (const geo of geometries.values()) geo.dispose();
      for (const material of materials) material.dispose();
      floor.geometry.dispose(); floor.material.dispose(); texture.dispose();
      renderer.dispose(); renderer.forceContextLoss(); renderer.domElement.remove();
    },
  };
}
