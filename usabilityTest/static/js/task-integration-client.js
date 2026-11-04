/* data-parent-origin debe coincidir con el origen del framework. */
(function () {
  'use strict';
  const script = document.currentScript;
  const parentOrigin = script && script.dataset.parentOrigin;
  if (!parentOrigin || window.parent === window) return;
  let session = null, lastSent = -Infinity;
  window.addEventListener('message', function (event) {
    if (event.source !== window.parent || event.origin !== parentOrigin) return;
    const d = event.data;
    if (!d || d.type !== 'crowdta:init' || d.version !== 1 ||
        typeof d.token !== 'string' || typeof d.taskId !== 'string') return;
    session = {version: 1, taskId: d.taskId, token: d.token};
  });
  function send(type) {
    if (session) window.parent.postMessage(Object.assign({type}, session), parentOrigin);
  }
  ['pointermove', 'pointerdown', 'keydown', 'scroll'].forEach(function (name) {
    document.addEventListener(name, function (event) {
      if (!event.isTrusted || document.hidden) return;
      const now = performance.now();
      if (now - lastSent < 500) return;
      lastSent = now;
      send('crowdta:activity');
    }, {passive: true, capture: true});
  });
  window.CrowdTAClient = {finish: function () { send('crowdta:task_finished'); }};
})();
