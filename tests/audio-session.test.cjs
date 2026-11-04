const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

test('finish saves final metrics without downloading a local report', async () => {
  const calls=[];
  const window={crypto:{randomUUID:()=> 'session-test'},addEventListener(){}};
  const document={cookie:'csrftoken=test',getElementById(){return null;},
    createElement(){throw new Error('Unexpected download element');}};
  vm.runInNewContext(fs.readFileSync('usabilityTest/static/js/audio-monitoring-session.js','utf8'), {
    window,document,performance:{now:()=>10000},Intl,Date,console,
    setInterval(){return 1;},clearInterval(){},
    fetch:async (url,options)=>{calls.push({url,options});return {ok:true,json:async()=>({success:true})};}
  });
  window.CrowdAudioSession.start('1');
  const result=await window.CrowdAudioSession.finish({speechSeconds:4});
  assert.equal(result.success,true);
  assert.ok(calls.length>=2);
  assert.ok(calls.every(c=>c.url==='/audio-monitoring/' && c.options.method==='POST'));
  const final=JSON.parse(calls.at(-1).options.body);
  assert.equal(final.final,true);
  assert.equal(final.metrics.speechSeconds,4);
});
