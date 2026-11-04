const test = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const source = fs.readFileSync('usabilityTest/static/js/task-integration.js', 'utf8');
function setup(minimum = 0, enabled = true) {
  let clock = 0;
  const handlers = {}, docHandlers = {}, sent = [];
  const frame = {contentWindow: {postMessage: (...args) => sent.push(args)}, addEventListener: (name, fn) => handlers['frame:' + name] = fn};
  const button = {setAttribute() {}, classList: {toggle() {}}, addEventListener: (name, fn) => handlers['button:' + name] = fn};
  const elements = {'task-integration-config': {dataset: {enabled: String(enabled), url: 'https://app.example/task', minimum: String(minimum)}}, 'task-application': frame, TaskDone: button, 'task-integration-status': {}, taskid: {value: '1'}};
  const document = {hidden: false, getElementById: id => elements[id], addEventListener: (name, fn) => docHandlers[name] = fn};
  const window = {addEventListener: (name, fn) => handlers[name] = fn};
  vm.runInNewContext(source, {document, window, URL, crypto: {randomUUID: () => 'session-token'}, performance: {now: () => clock}});
  return {window, handlers, document, sent, docHandlers,
    tick: ms => clock += ms,
    message(type, overrides = {}, envelope = {}) {
      handlers.message({source: frame.contentWindow, origin: 'https://app.example', data: {type, version: 1, taskId: '1', token: 'session-token', ...overrides}, ...envelope});
    }};
}
test('disabled integration keeps the original flow', () => assert.equal(setup(0, false).window.CrowdTaskGate, undefined));
test('completion requires a started session and exact sender, task and token', () => {
  const s = setup();
  s.message('crowdta:task_finished'); assert.equal(s.window.CrowdTaskGate.canContinue(), false);
  s.window.CrowdTaskGate.start();
  s.message('crowdta:task_finished', {}, {origin: 'https://other.example'});
  s.message('crowdta:task_finished', {}, {source: {}});
  s.message('crowdta:task_finished', {token: 'old'});
  s.message('crowdta:task_finished', {taskId: '2'});
  s.message('other');
  assert.equal(s.window.CrowdTaskGate.canContinue(), false);
  s.message('crowdta:task_finished'); assert.equal(s.window.CrowdTaskGate.canContinue(), true);
});
test('time alone does not unlock; interaction intervals reach the threshold', () => {
  const s = setup(2); s.window.CrowdTaskGate.start();
  s.tick(600000); assert.equal(s.window.CrowdTaskGate.canContinue(), false);
  s.message('crowdta:activity');
  for (let i = 0; i < 4; i++) {s.tick(500); s.message('crowdta:activity');}
  assert.equal(s.window.CrowdTaskGate.canContinue(), true);
});
test('idle and hidden intervals are excluded', () => {
  const s = setup(2); s.window.CrowdTaskGate.start();
  s.message('crowdta:activity'); s.tick(5000); s.message('crowdta:activity');
  s.document.hidden = true; s.docHandlers.visibilitychange();
  s.tick(500); s.message('crowdta:activity');
  s.document.hidden = false; s.docHandlers.visibilitychange();
  s.message('crowdta:activity');
  assert.equal(s.window.CrowdTaskGate.canContinue(), false);
});
test('iframe reload receives the session init and blocked clicks are intercepted', () => {
  const s = setup(); s.window.CrowdTaskGate.start(); s.handlers['frame:load']();
  assert.equal(s.sent.length, 2); let stopped = false;
  s.handlers['button:click']({preventDefault() {}, stopImmediatePropagation() {stopped = true;}});
  assert.equal(stopped, true);
});
test('zero threshold never unlocks on activity alone', () => {
  const s=setup();s.window.CrowdTaskGate.start();s.message('crowdta:activity');
  for(let i=0;i<10;i++){s.tick(1000);s.message('crowdta:activity');}
  assert.equal(s.window.CrowdTaskGate.canContinue(),false);
});
test('the client sends finish only after a valid parent handshake', () => {
  const clientSource=fs.readFileSync('usabilityTest/static/js/task-integration-client.js','utf8');
  const handlers={},sent=[];
  const parent={postMessage:(data,origin)=>sent.push({data,origin})};
  const window={parent,addEventListener:(name,fn)=>handlers[name]=fn};
  const document={currentScript:{dataset:{parentOrigin:'https://framework.example'}},hidden:false,addEventListener(){}};
  vm.runInNewContext(clientSource,{window,document,performance:{now:()=>0}});
  window.CrowdTAClient.finish();assert.equal(sent.length,0);
  const data={type:'crowdta:init',version:1,taskId:'1',token:'token'};
  handlers.message({source:parent,origin:'https://other.example',data});
  window.CrowdTAClient.finish();assert.equal(sent.length,0);
  handlers.message({source:parent,origin:'https://framework.example',data});
  window.CrowdTAClient.finish();assert.equal(sent.length,1);
  assert.equal(sent[0].data.type,'crowdta:task_finished');
  assert.equal(sent[0].origin,'https://framework.example');
});
