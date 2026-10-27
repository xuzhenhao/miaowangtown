// 验证门槛 2、3：动作层与外观层完全解耦。
// 门槛 2：动作文件不引用任何宠物（id / 宠物目录 / 颜色值），新增动作天然对所有宠物可用。
// 门槛 3：宠物目录只有 DNA JSON 和贴图，DNA 里不允许出现动作数据。
import { readdirSync, readFileSync } from 'node:fs';
import { extname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('..', import.meta.url));
const clipsDir = join(root, 'src/anim/clips');
const petsDir = join(root, 'public/pets');
const failures = [];

const petIds = JSON.parse(readFileSync(join(petsDir, 'index.json'), 'utf8')).pets;
const petNames = petIds.map((id) => JSON.parse(readFileSync(join(petsDir, `${id}.json`), 'utf8')).name);

const clipFiles = readdirSync(clipsDir).filter((f) => f.endsWith('.ts'));
for (const f of clipFiles) {
  const src = readFileSync(join(clipsDir, f), 'utf8');
  for (const word of [...petIds, ...petNames]) {
    if (new RegExp(`['"\`/]${word}['"\`/.]`).test(src)) failures.push(`动作文件 ${f} 引用了宠物 "${word}"`);
  }
  if (/pets\//.test(src)) failures.push(`动作文件 ${f} 引用了宠物目录`);
  if (/#[0-9a-fA-F]{6}\b/.test(src)) failures.push(`动作文件 ${f} 里出现了颜色值（外观数据不应进入动作层）`);
  if (/from ['"].*\/cat\/(dna|coatBaker)['"]/.test(src)) failures.push(`动作文件 ${f} 依赖了外观层模块`);
}

const ALLOWED_EXT = new Set(['.json', '.png', '.jpg', '.jpeg', '.webp']);
const ALLOWED_KEYS = new Set(['id', 'name', 'shape', 'coat', 'earInner', 'eyes', 'nose', 'personality']);
const clipIndex = readFileSync(join(clipsDir, 'index.ts'), 'utf8');
const clipNames = [...clipIndex.matchAll(/import \{ (\w+) \}/g)].map((m) => m[1]);

for (const f of readdirSync(petsDir)) {
  if (!ALLOWED_EXT.has(extname(f).toLowerCase())) failures.push(`宠物目录出现了非 DNA/贴图文件：${f}`);
}
for (const id of petIds) {
  const dna = JSON.parse(readFileSync(join(petsDir, `${id}.json`), 'utf8'));
  for (const k of Object.keys(dna)) {
    if (!ALLOWED_KEYS.has(k)) failures.push(`${id}.json 出现了不允许的字段 "${k}"（动作数据不能放进 DNA）`);
  }
  for (const k of Object.keys(dna.personality ?? {})) {
    if (!clipNames.includes(k)) failures.push(`${id}.json 的性格权重引用了不存在的动作 "${k}"`);
  }
  if (dna.coat?.texture && !readdirSync(petsDir).includes(dna.coat.texture)) {
    failures.push(`${id}.json 引用的贴图 ${dna.coat.texture} 不存在`);
  }
}

console.log(`动作库：${clipNames.join(', ')}（${clipNames.length} 个）`);
console.log(`宠物：${petIds.join(', ')}（${petIds.length} 只）`);
console.log(`组合：${clipNames.length * petIds.length} 种，全部由同一套骨骼与动作驱动`);
if (failures.length) {
  console.error('\n未通过：');
  for (const f of failures) console.error(`  - ${f}`);
  process.exit(1);
}
console.log('\n门槛 2 通过：动作文件不引用任何宠物资源，新增动作对所有宠物直接可用');
console.log('门槛 3 通过：宠物目录只有 DNA 与贴图，换猫不需要改任何动作');
