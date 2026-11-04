/* Comunicación con la aplicación evaluada. */
(function () {
  'use strict';
  const config = document.getElementById('task-integration-config');
  if (!config || config.dataset.enabled !== 'true') return;
  const frame = document.getElementById('task-application');
  const button = document.getElementById('TaskDone');
  const status = document.getElementById('task-integration-status');
  const taskId = document.getElementById('taskid').value;
  const minimum = Math.max(0, Number(config.dataset.minimum) || 0);
  const token = crypto.randomUUID();
  let origin, started = false, completed = false, active = 0, lastActivity = null;
  try {
    const url = new URL(config.dataset.url);
    if (!['http:', 'https:'].includes(url.protocol)) throw new Error('Invalid protocol');
    origin = url.origin;
    frame.src = url.href;
  } catch (_) {
    status.textContent = 'Integration configuration error: check the application URL.';
  }
  function allowed() {
    return !!origin && started && (completed || (minimum > 0 && active >= minimum * 1000));
  }
  function render() {
    const ok = allowed();
    button.setAttribute('aria-disabled', String(!ok));
    button.classList.toggle('disabled', !ok);
    if (!origin) return;
    status.textContent = ok ? 'You may continue.' :
      `Waiting for application completion${minimum ? ` or active time: ${Math.floor(active / 1000)}/${minimum} s` : ''}.`;
  }
  function initialize() {
    if (!origin || !started) return;
    frame.contentWindow.postMessage({type: 'crowdta:init', version: 1, taskId, token}, origin);
  }
  frame.addEventListener('load', initialize);
  // Capture before Bootstrap's delegated collapse listener.
  button.addEventListener('click', function (event) {
    if (!allowed()) { event.preventDefault(); event.stopImmediatePropagation(); }
  }, true);
  window.addEventListener('message', function (event) {
    if (!started || event.origin !== origin || event.source !== frame.contentWindow) return;
    const data = event.data;
    if (!data || data.version !== 1 || data.taskId !== taskId || data.token !== token) return;
    if (data.type === 'crowdta:task_finished') {
      completed = true;
    } else if (data.type === 'crowdta:activity') {
      const now = performance.now();
      // Only intervals between frequent interaction signals count. No idle tail.
      if (!document.hidden && lastActivity !== null && now - lastActivity <= 2000) {
        active += Math.max(0, now - lastActivity);
      }
      lastActivity = document.hidden ? null : now;
    }
    render();
  });
  document.addEventListener('visibilitychange', function () { lastActivity = null; });
  window.CrowdTaskGate = {
    canContinue: allowed,
    start: function () {
      if (started) return;
      started = true;
      initialize();
      render();
    }
  };
  render();
})();
