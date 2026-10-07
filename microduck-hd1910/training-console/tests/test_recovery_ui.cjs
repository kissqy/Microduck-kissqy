// Focused DOM/HTTP fixture for the actual recovery UI script, without a browser.
// This verifies behavior, not CSS layout, WebGL, rendered images, or GPU inference.
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const staticDir = path.join(__dirname, '../training/static');
const html = fs.readFileSync(path.join(staticDir, 'index.html'), 'utf8');
const decode = value => String(value).replace(/&(amp|quot|#39|lt|gt);/g,
  (_, entity) => ({amp: '&', quot: '"', '#39': "'", lt: '<', gt: '>'}[entity]));
const nodes = new Map();
const documentEvents = new Map();
function makeNode(tagName, attributes = '') {
  const attrs = new Map();
  for (const item of attributes.matchAll(/([\w-]+)(?:="([^"]*)")?/g)) {
    attrs.set(item[1], decode(item[2] || ''));
  }
  let value = attrs.get('value') || '', innerHTML = '';
  const node = {
    tagName: tagName.toUpperCase(), disabled: attrs.has('disabled'),
    hidden: attrs.has('hidden'), checked: attrs.has('checked'), textContent: '',
    options: [], style: {}, dataset: {}, scrollHeight: 0, scrollTop: 0, clientHeight: 0,
    classList: {toggle() {}, add() {}, remove() {}},
    parentElement: {getBoundingClientRect: () => ({width: 0, height: 0})},
    addEventListener() {}, contains: () => false, closest: () => null,
    hasAttribute: name => attrs.has(name), getAttribute: name => attrs.get(name),
    setAttribute(name, val) {attrs.set(name, String(val));},
    removeAttribute(name) {attrs.delete(name);},
    click() {if (!node.disabled) return node.onclick?.({target: node});}
  };
  for (const [name, val] of attrs) {
    if (name.startsWith('data-')) node.dataset[name.slice(5).replace(/-([a-z])/g, (_, x) => x.toUpperCase())] = val;
  }
  Object.defineProperty(node, 'value', {
    get: () => value,
    set: next => {value = node.tagName !== 'SELECT' || node.options.some(o => o.value === String(next)) ? String(next) : '';}
  });
  Object.defineProperty(node, 'innerHTML', {
    get: () => innerHTML,
    set: next => {
      innerHTML = String(next);
      if (node.tagName === 'SELECT') {
        node.options = [...innerHTML.matchAll(/<option\b([^>]*)>([\s\S]*?)<\/option>/g)].map(match => ({
          value: decode(match[1].match(/\bvalue="([^"]*)"/)?.[1] || ''),
          selected: /\bselected\b/.test(match[1])
        }));
        value = (node.options.find(o => o.selected) || node.options[0])?.value || '';
      }
    }
  });
  return node;
}
for (const tag of html.matchAll(/<([a-z][\w-]*)\b([^>]*\bid="([^"]+)"[^>]*)>/gi)) {
  assert(!nodes.has(tag[3]), `duplicate HTML id: ${tag[3]}`);
  nodes.set(tag[3], makeNode(tag[1], tag[2]));
}
const el = id => {
  assert(nodes.has(id), `script refers to missing HTML id: ${id}`);
  return nodes.get(id);
};
assert.equal(el('recovery-eval-start').getAttribute('type'), 'button');
assert.equal(el('recovery-eval-start').disabled, true, 'recovery starts disabled in HTML');
assert.equal(el('recovery-eval-note').hidden, true, 'guidance starts hidden in HTML');
assert.match(html, /<script\b[^>]*src="\/training\.js"/);

const httpCalls = [], timers = [];
let serverState, deferredPost;
const context = vm.createContext({
  console, URLSearchParams, AbortSignal,
  document: {
    readyState: 'loading', hidden: false, activeElement: null,
    getElementById: el, querySelectorAll: () => [],
    addEventListener(name, callback) {documentEvents.set(name, callback);}
  },
  window: {addEventListener() {}},
  ResizeObserver: class {observe() {}},
  setTimeout(callback, delay) {timers.push({callback, delay}); return timers.length;},
  clearTimeout() {}, setInterval() {}, requestAnimationFrame() {},
  queueMicrotask,
  fetch: async (route, options = {}) => {
    const method = options.method || 'GET';
    const body = options.body ? JSON.parse(options.body) : undefined;
    httpCalls.push({route, method, body, headers: options.headers});
    if (method === 'POST') {
      assert(['/api/play', '/api/onnx'].includes(route), `unexpected mutation: ${route}`);
      assert.equal(options.headers['X-Training-Token'], 'ui-fixture-token');
      if (deferredPost) return new Promise(resolve => {deferredPost.release = resolve;});
      return {ok: true, json: async () => ({job_id: 'fixture-viewer'})};
    }
    if (route === '/api/config') return {ok: true, json: async () => ({token: 'ui-fixture-token', version: 'R1.5.17'})};
    assert(route.startsWith('/api/state?'), `unexpected read: ${route}`);
    return {ok: true, json: async () => structuredClone(serverState)};
  }
});
vm.runInContext(fs.readFileSync(path.join(staticDir, 'tasks.js'), 'utf8'), context, {filename: 'tasks.js'});
vm.runInContext(fs.readFileSync(path.join(staticDir, 'training.js'), 'utf8'), context, {filename: 'training.js'});
assert.equal(httpCalls.length, 0, 'loading the script must not submit a request');
const catalog = vm.runInContext('taskCatalog', context);
const standTasks = catalog.tasks.filter(t => t.role === 'stand');
const stand = standTasks[0].id, walk = catalog.tasks.find(t => t.role === 'walk').id;
el('task').innerHTML = catalog.tasks.map(t => `<option value="${t.id}">${t.name}</option>`).join('');
el('engine-mode').innerHTML = '<option value="native">Native fixture</option>';

// Keep real render(), modelRecords(), renderModels(), chosen(), recoverySelection(),
// startViewer(), action(), post(), loadState(), and every actual click handler.
// Unrelated panels and motion/WebGL presentation have no role in this fixture.
vm.runInContext(`
  renderTaskCatalog = () => {};
  renderTaskConfig = () => {};
  renderComparison = () => {};
  renderResources = () => {};
  renderActionFilter = () => {};
  renderSimulation = () => {};
  renderCurriculum = () => {};
  draw = () => {};
  clearMotion = () => {};
`, context);
function trainJob(id, task, resolved_task) {
  return {id, op: 'train', status: 'completed', created: 1700000000,
    target_compatible: true, resume_compatible: true, resolved_task,
    request: {task, label: id}, checkpoints: [{path: `/fixture/${id}/model_11000.pt`, iteration: 11000}]};
}
function exportJob(id, source, task, resolved_task) {
  return {id, op: 'export', status: 'completed', created: 1700000001,
    target_compatible: true, artifact: `/fixture/${id}.onnx`, artifact_sha256: 'a'.repeat(64), resolved_task,
    request: {source_job: source, source_iteration: 11000, task, source_label: source}};
}
const jobs = [trainJob('walk-pt', walk), exportJob('walk-onnx', 'walk-pt', walk),
  trainJob('resolved-stand', walk, stand), trainJob('resolved-walk', stand, walk),
  exportJob('resolved-stand-onnx', 'resolved-stand', walk, stand),
  exportJob('resolved-walk-onnx', 'resolved-walk', stand, walk)];
for (const [i, task] of standTasks.entries()) {
  jobs.push(trainJob(`stand-${i}`, task.id), exportJob(`stand-onnx-${i}`, `stand-${i}`, task.id));
}
serverState = {profile: {mode: 'native', distro: '', repo: '/fixture/repo'},
  environment: {ready: true, message: 'fixture', configs: {}}, jobs};
const clone = value => structuredClone(value);
function syncState() {
  context.fixtureState = clone(serverState);
  vm.runInContext('state = fixtureState; render();', context);
}
function pick(id) {
  const job = jobs.find(j => j.id === id);
  return job.op === 'export' ? {export_job: id} : {source_job: id, checkpoint: job.checkpoints[0].path};
}
function select(value, trainingTask = walk) {
  el('task').value = trainingTask;
  vm.runInContext('render();', context);
  el('checkpoint').value = value ? JSON.stringify(value) : '';
  el('checkpoint').onchange();
}
function enabled(expected, label) {
  assert.equal(el('recovery-eval-start').disabled, !expected, label);
  assert.equal(el('recovery-eval-note').hidden, !expected, `${label}: guidance`);
}
const settle = async () => {for (let i = 0; i < 6; ++i) await new Promise(resolve => setImmediate(resolve));};
const posts = () => httpCalls.filter(call => call.method === 'POST');

(async () => {
  await documentEvents.get('DOMContentLoaded')();
  await settle();
  assert.equal(posts().length, 0, 'UI startup and initial state render do not start training or evaluation');
  select(null, stand); enabled(false, 'no model despite a stand training action');
  for (const [i] of standTasks.entries()) {
    select(pick(`stand-${i}`), walk); enabled(true, `stand PT ${i} with walk training selected`);
    select(pick(`stand-onnx-${i}`), walk); enabled(true, `stand ONNX ${i} with walk training selected`);
  }
  for (const id of ['walk-pt', 'walk-onnx', 'resolved-walk', 'resolved-walk-onnx']) {
    select(pick(id), stand); enabled(false, `${id} despite stand training selection`);
    const before = posts().length; el('recovery-eval-start').click();
    assert.equal(posts().length, before, 'disabled DOM click sends no request');
  }
  for (const id of ['resolved-stand', 'resolved-stand-onnx']) {
    select(pick(id), walk); enabled(true, `${id} honors resolved_task`);
  }
  assert.equal(posts().length, 0, 'model/role selection and render do not start any operation');

  for (const id of ['stand-0', 'stand-onnx-0']) {
    const value = pick(id), route = value.export_job ? '/api/onnx' : '/api/play';
    select(value, walk); el('eval-pushes').checked = true; el('follow-latest').checked = true;
    const before = posts().length;
    el('recovery-eval-start').click(); await settle();
    assert.equal(posts().length, before + 1, `${id}: one recovery POST`);
    assert.deepEqual(posts().at(-1).body, {...value, recovery_evaluation: true, eval_pushes: false});
    assert.equal(posts().at(-1).route, route);
    assert.equal(el('follow-latest').checked, false, 'manual check clears periodic viewer following');
    assert.equal(el('task').value, walk, 'evaluating a stand model does not rewrite the training action');
    for (const pushes of [false, true]) {
      el('eval-pushes').checked = pushes;
      el('play-start').click(); await settle();
      assert.equal(posts().at(-1).route, route, `${id}: normal play uses the same route`);
      assert.deepEqual(posts().at(-1).body, {...value, eval_pushes: pushes});
      assert(!Object.hasOwn(posts().at(-1).body, 'recovery_evaluation'), 'normal play has no recovery flag');
    }
  }

  select(pick('stand-0'), walk);
  vm.runInContext('online = false; render();', context);
  assert.equal(el('recovery-eval-start').disabled, true, 'offline guard');
  vm.runInContext('online = true; render();', context);
  serverState.jobs.push({id: 'pending-viewer', op: 'play', status: 'starting', wait_for_viewers: true, request: {task: stand}});
  syncState();
  assert.equal(el('recovery-eval-start').disabled, true, 'pending viewer guard');
  serverState.jobs.pop(); syncState();
  deferredPost = {};
  const before = posts().length;
  el('recovery-eval-start').click();
  assert.equal(el('recovery-eval-start').disabled, true, 'in-flight request guard');
  el('recovery-eval-start').onclick(); // Even an immediate direct duplicate is guarded.
  assert.equal(posts().length, before + 1, 'no duplicate POST during viewer launch');
  deferredPost.release({ok: true, json: async () => ({job_id: 'fixture-viewer'})});
  deferredPost = null; await settle();
  assert.equal(el('recovery-eval-start').disabled, false, 'button recovers after submission');
  assert(httpCalls.every(call => call.method !== 'POST' || ['/api/play', '/api/onnx'].includes(call.route)));
  console.log(`RECOVERY_UI_OK: ${standTasks.length} official stand variants × PT/ONNX; selected-model role and resolved_task; normal/recovery payloads; no automatic POST/train; offline/pending/in-flight guards.`);
  console.log('SCOPE: Node DOM/HTTP fixture only; no real browser rendering, 4K screenshots, WebGL, training, or policy inference.');
})().catch(error => {console.error(error); process.exitCode = 1;});
