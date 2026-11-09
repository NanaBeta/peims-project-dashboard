// Zero-dependency logic smoke for the standalone browser preview.
// This does not validate visual rendering on a real browser.
const fs = require('fs');
const vm = require('vm');
const path = require('path');
const assert = require('assert');
const html = fs.readFileSync(path.join(__dirname, '..', 'index.html'), 'utf8');
const match = html.match(/<script>([\s\S]*?)<\/script>/);
assert(match, 'Missing self-contained preview script');
const ids = ['#projectName', '#projectDesc', '#desktopNav', '#mobileNav', '#projectSelect', '#content'];
const elements = Object.fromEntries(ids.map(id => [id, {
  innerHTML: '', textContent: '', value: '', children: [],
  append(el) { this.children.push(el); },
  addEventListener() {},
}]));
let downloadCount = 0;
const ctx = vm.createContext({
  document: {
    querySelector(selector) { assert(elements[selector], `Missing element ${selector}`); return elements[selector]; },
    createElement() { return { click() { downloadCount++; }, remove() {} }; },
    body: { append() {} },
  },
  window: { scrollTo() {} },
  URL: { createObjectURL() { return 'blob:demo'; }, revokeObjectURL() {} },
  Blob: class Blob { constructor(data) { this.data = data; } },
});
new vm.Script(match[1], { filename: 'PEIMS/index.html' }).runInContext(ctx);
const projects = vm.runInContext('Object.keys(PROJECTS)', ctx);
assert.equal(projects.length, 2);
let checked = 0;
for (const project of projects) {
  ctx.setProject(project);
  for (const name of ['overview', 'schedule', 'cost', 'procurement', 'risks', 'report']) {
    ctx.go(name);
    assert(elements['#content'].innerHTML.length > 200, `${project}: ${name} empty`);
    checked++;
  }
  ctx.downloadReport();
  assert(elements['#projectName'].textContent.length > 10);
}
assert.equal(downloadCount, 2);
console.log(`PASS ${checked} module/project combinations and ${downloadCount} report download handlers`);
