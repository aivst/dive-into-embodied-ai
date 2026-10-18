// Generate same-origin assets for every build/dev invocation, including `npx
// docusaurus start`. No CDN dependency and no duplicated binary assets in Git.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');

module.exports = function quaddleAssets(context) {
  const root = context.siteDir;
  const source = path.join(root, 'codes/practices/quadruped/quaddle-mujoco');
  return {
    name: 'quaddle-browser-assets',
    getPathsToWatch() { return [path.join(source, 'web/*.mjs'), path.join(source, 'models/**/*'), path.join(source, 'gait.json')]; },
    async loadContent() {
      const output = path.join(root, 'static/quaddle');
      const engine = path.dirname(require.resolve('@mujoco/mujoco'));
      const version = JSON.parse(fs.readFileSync(path.join(engine, 'package.json'))).version;
      fs.mkdirSync(path.join(output, 'assets'), {recursive: true});
      const files = ['scene.xml'];
      const copy = (from, to) => fs.copyFileSync(from, path.join(output, to));
      const xml = fs.readFileSync(path.join(source, 'models/scene.xml'), 'utf8');
      copy(path.join(source, 'models/scene.xml'), 'scene.xml');
      for (const [, name] of xml.matchAll(/<mesh\s[^>]*file="([^"]+)"/g)) {
        const filename = path.join(source, 'models/assets', name);
        const bytes = fs.readFileSync(filename);
        if (bytes.subarray(0, 80).toString().startsWith('version https://git-lfs.github.com/')) {
          throw new Error(`Quaddle mesh ${name} is a Git LFS pointer. Run git lfs pull first.`);
        }
        copy(filename, `assets/${name}`);
        files.push(`assets/${name}`);
      }
      copy(path.join(source, 'gait.json'), 'gait.json');
      for (const file of ['controller.mjs', 'simulation.mjs', 'worker.mjs']) copy(path.join(source, 'web', file), file);
      for (const file of ['mujoco.js', 'mujoco.wasm']) copy(path.join(engine, file), file);
      copy(path.join(source, 'original/LICENSE'), 'Petoi-LICENSE');
      for (const file of ['MuJoCo-LICENSE', 'MuJoCo-THIRD-PARTY.md']) copy(path.join(source, 'web/licenses', file), file);
      const manifest = {version, files, modelSha256: crypto.createHash('sha256').update(xml).digest('hex')};
      fs.writeFileSync(path.join(output, 'manifest.json'), JSON.stringify(manifest, null, 2));
    },
  };
};
