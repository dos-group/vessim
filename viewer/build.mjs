// One static bundle for the CLI, exported reports and documentation, at any URL prefix.
import { build } from 'vite'
import react from '@vitejs/plugin-react'
import { cp, mkdir, readdir, mkdtemp, rm } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { tmpdir } from 'node:os'
import path from 'node:path'
const root = path.dirname(fileURLToPath(import.meta.url))
const output = path.join(root, '../vessim/_viewer_dist')
const publicDir = await mkdtemp(path.join(tmpdir(), 'vessim-viewer-'))
try {
  await mkdir(path.join(publicDir, 'vendor'))
  for (const [packageName, filename] of [
    ['echarts', 'dist/echarts.min.js'],
    ['papaparse', 'papaparse.min.js'],
  ]) {
    const directory = path.join(root, 'node_modules', packageName)
    await cp(
      path.join(directory, filename),
      path.join(publicDir, 'vendor', path.basename(filename)),
    )
    const license = (await readdir(directory)).find((name) =>
      /^LICENSE(\.txt)?$/i.test(name),
    )
    if (license)
      await cp(
        path.join(directory, license),
        path.join(publicDir, 'vendor', `${packageName}-LICENSE.txt`),
      )
  }
  for (const name of ['react', 'react-dom'])
    await cp(
      path.join(root, 'node_modules', name, 'LICENSE'),
      path.join(publicDir, 'vendor', `${name}-LICENSE.txt`),
    )
  await build({
    configFile: false,
    root: path.join(root, 'src'),
    base: './',
    publicDir,
    plugins: [react()],
    build: { outDir: output, emptyOutDir: true },
  })
} finally {
  await rm(publicDir, { recursive: true, force: true })
}
console.log(`Built Vessim Viewer → ${output}`)
