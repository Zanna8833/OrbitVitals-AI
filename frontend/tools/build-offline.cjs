/**
 * Builds the downloadable demo: ONE self-contained HTML file that opens with a
 * double click (file://), no server, no install, no network.
 *
 * It takes the real production build (frontend/dist, produced by `vite build`)
 * and inlines its stylesheet, script and favicon. Usage, from frontend/:
 *
 *   npm run demo
 *
 * Output: frontend/OrbitVitals_Demo.html
 */
const fs = require('fs')
const path = require('path')

const root = path.resolve(__dirname, '..') // frontend/
const dist = path.join(root, 'dist')
const out = path.join(root, 'OrbitVitals_Demo.html')

let html = fs.readFileSync(path.join(dist, 'index.html'), 'utf8')
const read = (href) => fs.readFileSync(path.join(dist, href.replace(/^\//, '')), 'utf8')

// Stylesheets → <style>
html = html.replace(/<link rel="stylesheet"[^>]*href="([^"]+)"[^>]*>/g, (_m, href) => `<style>\n${read(href)}\n</style>`)

// Module scripts → inline module (a single chunk with no imports works from file://)
html = html.replace(/<script type="module"[^>]*src="([^"]+)"[^>]*><\/script>/g, (_m, src) => {
  const code = read(src).replace(/<\/script/gi, '<\\/script')
  if (/^\s*import\s|\bimport\(/m.test(code)) throw new Error(`${src} still imports other chunks; inline them first.`)
  return `<script type="module">\n${code}\n</script>`
})

// Favicon → data URI
html = html.replace(/<link rel="icon"[^>]*href="([^"]+)"[^>]*>/, (_m, href) => {
  const svg = read(href)
  return `<link rel="icon" type="image/svg+xml" href="data:image/svg+xml;base64,${Buffer.from(svg).toString('base64')}" />`
})

if (/(src|href)="\/assets\//.test(html)) throw new Error('Some assets were not inlined.')
fs.writeFileSync(out, html)
console.log(`Built ${path.relative(process.cwd(), out)} (${(Buffer.byteLength(html) / 1024).toFixed(0)} KB)`)
