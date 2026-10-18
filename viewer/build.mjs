// One source tree and one distributable for the CLI, exports and documentation.
import { cp, mkdir, readFile, readdir, rm, writeFile } from 'node:fs/promises'
import { createHash } from 'node:crypto'
import { fileURLToPath } from 'node:url'
import path from 'node:path'
const root = path.dirname(fileURLToPath(import.meta.url))
const source = path.join(root, 'src'), output = path.join(root, '../vessim/_viewer_dist')
const files = (await readdir(source)).filter(file => /\.(js|css|html|svg)$/.test(file))
const digest = createHash('sha256')
digest.update(await readFile(path.join(root, 'package-lock.json')))
for (const file of files.sort()) digest.update(await readFile(path.join(source, file)))
const version = digest.digest('hex').slice(0, 12)
await rm(output, { recursive: true, force: true })
await mkdir(path.join(output, 'vendor'), { recursive: true })
for (const file of files) {
  let content = await readFile(path.join(source, file), 'utf8')
  content = content.replace(/(\.\/(?:[\w.-]+\/)*[\w.-]+\.js)(['"])/g, `$1?v=${version}$2`)
  if (file.endsWith('.html')) content = content.replace(/((?:src|href)="[^"]+\.(?:js|css))"/g, `$1?v=${version}"`)
  await writeFile(path.join(output, file), content)
}
for (const [packageName, filename] of [['echarts', 'dist/echarts.min.js'], ['papaparse', 'papaparse.min.js']]) {
  const directory = path.join(root, 'node_modules', packageName)
  await cp(path.join(directory, filename), path.join(output, 'vendor', path.basename(filename)))
  const license = (await readdir(directory)).find(name => /^LICENSE(\.txt)?$/i.test(name))
  if (license) await cp(path.join(directory, license), path.join(output, 'vendor', `${packageName}-LICENSE.txt`))
}
console.log(`Built Vessim Viewer (${version}) → ${output}`)
