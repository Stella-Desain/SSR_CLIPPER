const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {parseHTML} = require('linkedom');
const root = path.resolve(__dirname, '..');

test('Editor is reachable through keyboard navigation and uses the same shell', () => {
  const {window} = parseHTML('<html><body></body></html>');
  window.Components = {};
  const context = vm.createContext({window,document:window.document});
  vm.runInContext(fs.readFileSync(path.join(root,'web/components/header.js'),'utf8'),context);
  const shell = window.Components.Shell();
  const entry = shell.navItems.find(item=>item.dataset.view==='editor');
  assert.ok(entry);assert.equal(entry.textContent.trim(),'Editor');
  assert.equal(entry.getAttribute('role'),'button');assert.equal(entry.getAttribute('tabindex'),'0');
  let clicks = 0;entry.addEventListener('click',()=>clicks++);
  for (const key of ['Enter',' ']) {
    const event = new window.Event('keydown',{cancelable:true});event.key=key;entry.dispatchEvent(event);
    assert.equal(event.defaultPrevented,true);
  }
  assert.equal(clicks,2);
});

test('Editor dependency is local, licensed, and loaded before the component', () => {
  const html = fs.readFileSync(path.join(root,'web/index.html'),'utf8');
  const scripts = [...html.matchAll(/<script src="([^"]+)"/g)].map(match=>match[1]);
  const vendor = scripts.indexOf('vendor/konva.min.js');
  const model = scripts.indexOf('editor-model.js');
  const editor = scripts.indexOf('components/template-editor.js');
  assert.ok(vendor>=0 && model>vendor && editor>model && scripts.indexOf('app.js')>editor);
  assert.match(fs.readFileSync(path.join(root,'web/vendor/KONVA-LICENSE.txt'),'utf8'),/MIT License/);
  assert.match(html,/css\/template-editor.css/);
});
