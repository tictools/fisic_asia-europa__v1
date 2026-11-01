/* Physical maps · Europe and Asia — drag-and-drop activity.
   Vanilla JavaScript. Dragging uses Pointer Events, which behave the same with mouse,
   pen and touchscreen (unlike the HTML5 drag & drop API, which doesn't work with a finger). */
(() => {
  'use strict';

  const SVG_NS = 'http://www.w3.org/2000/svg';
  const SNAP_PX = 30; // max distance (screen px) between finger/mouse and a dot for it to count as the drop target

  const GROUP_COLORS = {
    rius: '#1E6FE0', serralades: '#C62828', mars: '#00A5B5', peninsules: '#7B1FA2', illes: '#2E7D32',
    planes: '#D9A300', llacs: '#1A237E', deserts: '#EF6C00', estrets: '#111111', golfs: '#E8558A',
    arxipelegs: '#795548',
  };
  // Drawing order of highlighted areas (large ones below, lines on top)
  const LAYER_ORDER = { peninsules: 0, planes: 1, deserts: 1, mars: 2, golfs: 2, serralades: 3, illes: 3,
    arxipelegs: 3, llacs: 4, rius: 5, estrets: 6 };

  const $ = (s) => document.querySelector(s);
  const slug = (s) => s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
  const el = (tag, attrs = {}, parent) => {
    const n = document.createElementNS(SVG_NS, tag);
    for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
    if (parent) parent.appendChild(n);
    return n;
  };
  const shuffle = (a) => {
    for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [a[i], a[j]] = [a[j], a[i]]; }
    return a;
  };

  // ------------------------------------------------------------------ state
  const state = { map: null, svg: null, dots: new Map(), solved: new Set(), errors: 0, drag: null };

  // ------------------------------------------------------------------ mobile warning
  function isPhone() {
    const coarse = window.matchMedia('(pointer: coarse)').matches;
    const minSide = Math.min(window.screen.width, window.screen.height);
    return (coarse && minSide < 600) || /iPhone|iPod|Android.+Mobile|Windows Phone/i.test(navigator.userAgent);
  }
  function setupMobileWarning() {
    let dismissed = false;
    try { dismissed = sessionStorage.getItem('mobile-ok') === '1'; } catch (_) { /* no storage */ }
    if (isPhone() && !dismissed) $('#mobile-warning').hidden = false;
    $('#mobile-continue').addEventListener('click', () => {
      $('#mobile-warning').hidden = true;
      try { sessionStorage.setItem('mobile-ok', '1'); } catch (_) { /* ignore */ }
    });
  }

  // ------------------------------------------------------------------ routing (#europa / #asia)
  function route() {
    const id = location.hash.replace(/^#\/?/, '');
    if (id === 'europa' || id === 'asia') openMap(id);
    else showLanding();
  }
  function showLanding() {
    $('#game').hidden = true; $('#done').hidden = true; $('#landing').hidden = false;
    document.title = 'Mapes físics · Europa i Àsia';
  }

  function loadData(id) {
    window.MAP_DATA = window.MAP_DATA || {};
    if (window.MAP_DATA[id]) return Promise.resolve(window.MAP_DATA[id]);
    return new Promise((resolve, reject) => {
      const s = document.createElement('script');
      s.src = `data/${id}.js`;
      s.onload = () => (window.MAP_DATA[id] ? resolve(window.MAP_DATA[id]) : reject(new Error('dades buides')));
      s.onerror = () => reject(new Error(`No s'ha pogut carregar data/${id}.js`));
      document.head.appendChild(s);
    });
  }

  async function openMap(id) {
    $('#landing').hidden = true; $('#game').hidden = false; $('#done').hidden = true;
    const wrap = $('#map-wrap');
    wrap.innerHTML = '<div class="map-loading">Carregant el mapa…</div>';
    $('#tray-groups').innerHTML = '';
    try {
      const data = await loadData(id);
      if (location.hash.replace(/^#\/?/, '') !== id) return; // the user has already navigated away
      startGame(data);
    } catch (err) {
      wrap.innerHTML = `<div class="map-loading">${err.message}</div>`;
    }
  }

  // ------------------------------------------------------------------ game
  function startGame(data) {
    state.map = data; state.solved = new Set(); state.errors = 0; state.dots = new Map();
    $('#map-title').textContent = data.title;
    document.title = `${data.title} · Mapa físic`;
    $('#stat-total').textContent = data.features.length;
    updateStats();
    document.querySelector('.tray').classList.remove('is-complete');
    buildMap(data);
    buildTray(data);
  }

  function updateStats() {
    $('#stat-ok').textContent = state.solved.size;
    $('#stat-err').textContent = state.errors;
  }

  function buildMap(data) {
    const wrap = $('#map-wrap');
    wrap.innerHTML = '';
    const [x, y, w, h] = data.viewBox;
    const svg = el('svg', { viewBox: `${x} ${y} ${w} ${h}`, role: 'img', 'aria-label': `Mapa mut de ${data.title}` });
    state.svg = svg;

    // Triangle pattern for mountain ranges
    const defs = el('defs', {}, svg);
    const pat = el('pattern', { id: 'pat-serralades', width: 14, height: 12, patternUnits: 'userSpaceOnUse' }, defs);
    el('rect', { width: 14, height: 12, fill: GROUP_COLORS.serralades, 'fill-opacity': .22 }, pat);
    el('path', { d: 'M2 10.5L7 2.5L12 10.5Z', fill: GROUP_COLORS.serralades, 'fill-opacity': .75 }, pat);

    // Blank map base
    const b = data.base;
    const base = el('g', { class: 'base' }, svg);
    el('path', { class: 'b-grat', d: b.graticule }, base);
    el('path', { class: 'b-land', d: b.land, 'fill-rule': 'evenodd' }, base);
    el('path', { class: 'b-plat', d: b.plateaus }, base);
    el('path', { class: 'b-mtn', d: b.mountains }, base);
    el('path', { class: 'b-lake', d: b.lakes }, base);
    el('path', { class: 'b-riv', d: b.rivers }, base);

    // Highlighted areas (hidden until answered correctly)
    const hlLayer = el('g', { class: 'highlights' }, svg);
    const ordered = [...data.features].sort((a, c) => LAYER_ORDER[slug(a.group)] - LAYER_ORDER[slug(c.group)]);
    for (const f of ordered) {
      const g = slug(f.group);
      const hl = el('g', { class: `hl hl--${g}`, 'data-id': f.id, style: `--gc:${GROUP_COLORS[g]}` }, hlLayer);
      if (f.kind === 'area') {
        el('path', { class: 'fill', d: f.d, 'fill-rule': 'evenodd' }, hl);
        el('path', { class: 'halo', d: f.d }, hl);
        el('path', { class: 'edge', d: f.d }, hl);
      } else if (f.kind === 'river' || f.kind === 'line') {
        el('path', { class: 'halo', d: f.d }, hl);
        el('path', { class: 'edge', d: f.d }, hl);
      } else if (f.kind === 'peak') {
        const [px, py] = f.dot;
        el('path', { class: 'peak', d: `M${px} ${py - 15}L${px + 12} ${py + 7}L${px - 12} ${py + 7}Z` }, hl);
      }
    }

    // Dots
    const dotLayer = el('g', { class: 'dots' }, svg);
    for (const f of data.features) {
      const g = el('g', { class: 'dot', 'data-id': f.id, style: `--gc:${GROUP_COLORS[slug(f.group)]}` }, dotLayer);
      el('circle', { class: 'ring', cx: f.dot[0], cy: f.dot[1], r: 7 }, g);
      state.dots.set(f.id, { f, node: g });
    }

    // Labels (hidden until answered correctly)
    const lblLayer = el('g', { class: 'labels' }, svg);
    for (const f of data.features) {
      const g = el('g', { class: 'lbl', 'data-id': f.id, style: `--gc:${GROUP_COLORS[slug(f.group)]}` }, lblLayer);
      const [dx, dy] = f.dot, [lx, ly] = f.label;
      if (Math.hypot(lx - dx, ly - dy) > 30) el('line', { x1: dx, y1: dy, x2: lx, y2: ly }, g);
      const lines = splitLabel(f.name);
      const t = el('text', { x: lx, y: ly - (lines.length - 1) * 13, 'text-anchor': 'middle', 'dominant-baseline': 'middle' }, g);
      lines.forEach((ln, i) => {
        const ts = el('tspan', { x: lx, dy: i ? 27 : 0 }, t);
        ts.textContent = ln;
      });
    }

    wrap.appendChild(svg);
  }

  // Split long names over two lines
  function splitLabel(name) {
    if (name.length <= 17) return [name];
    const mid = name.length / 2;
    let best = -1;
    for (let i = 0; i < name.length; i++) if (name[i] === ' ' && (best < 0 || Math.abs(i - mid) < Math.abs(best - mid))) best = i;
    return best < 0 ? [name] : [name.slice(0, best), name.slice(best + 1)];
  }

  function buildTray(data) {
    const root = $('#tray-groups');
    root.innerHTML = '';
    const groups = [];
    for (const f of data.features) if (!groups.includes(f.group)) groups.push(f.group);
    for (const name of groups) {
      const g = slug(name);
      const sec = document.createElement('section');
      sec.className = 'group'; sec.style.setProperty('--gc', GROUP_COLORS[g]);
      sec.innerHTML = `<h3 class="group__title"><span class="group__swatch group__swatch--${g}"></span>${name}</h3>`;
      const box = document.createElement('div');
      box.className = 'group__pills';
      for (const f of shuffle(data.features.filter((x) => x.group === name))) {
        const p = document.createElement('button');
        p.type = 'button';
        p.className = `pill pill--${g}`;
        p.textContent = f.name;
        p.dataset.id = f.id;
        p.style.setProperty('--gc', GROUP_COLORS[g]);
        p.addEventListener('pointerdown', onPointerDown);
        box.appendChild(p);
      }
      sec.appendChild(box);
      root.appendChild(sec);
    }
  }

  // ------------------------------------------------------------------ drag and drop
  function onPointerDown(e) {
    if (state.drag || (e.pointerType === 'mouse' && e.button !== 0)) return;
    e.preventDefault();
    const pill = e.currentTarget;
    const r = pill.getBoundingClientRect();
    const ghost = pill.cloneNode(true);
    ghost.classList.add('pill-ghost');
    ghost.style.width = `${r.width}px`;
    document.body.appendChild(ghost);
    pill.classList.add('is-source');
    document.body.classList.add('is-dragging');
    state.drag = { pill, ghost, id: pill.dataset.id, offX: e.clientX - r.left, offY: e.clientY - r.top, pointerId: e.pointerId, target: null };
    moveGhost(e.clientX, e.clientY);
    pill.setPointerCapture(e.pointerId);
    pill.addEventListener('pointermove', onPointerMove);
    pill.addEventListener('pointerup', onPointerUp);
    pill.addEventListener('pointercancel', onPointerCancel);
  }

  function moveGhost(x, y) {
    const d = state.drag;
    d.ghost.style.transform = `translate(${x - d.offX}px, ${y - d.offY}px)`;
  }

  // Nearest unsolved dot to the pointer (within SNAP_PX screen pixels)
  function nearestDot(clientX, clientY) {
    const svg = state.svg;
    if (!svg) return null;
    const ctm = svg.getScreenCTM();
    if (!ctm) return null;
    const p = new DOMPoint(clientX, clientY).matrixTransform(ctm.inverse());
    const limit = SNAP_PX / ctm.a;
    let best = null, bd = Infinity;
    for (const [id, { f }] of state.dots) {
      if (state.solved.has(id)) continue;
      const dd = Math.hypot(f.dot[0] - p.x, f.dot[1] - p.y);
      if (dd < bd) { bd = dd; best = id; }
    }
    return bd <= limit ? best : null;
  }

  function setTarget(id) {
    const d = state.drag;
    if (d.target === id) return;
    if (d.target) state.dots.get(d.target).node.classList.remove('is-target');
    d.target = id;
    if (id) state.dots.get(id).node.classList.add('is-target');
  }

  function onPointerMove(e) {
    if (!state.drag || e.pointerId !== state.drag.pointerId) return;
    moveGhost(e.clientX, e.clientY);
    setTarget(nearestDot(e.clientX, e.clientY));
  }

  function endListeners() {
    const { pill, pointerId } = state.drag;
    pill.removeEventListener('pointermove', onPointerMove);
    pill.removeEventListener('pointerup', onPointerUp);
    pill.removeEventListener('pointercancel', onPointerCancel);
    try { pill.releasePointerCapture(pointerId); } catch (_) { /* already released */ }
    document.body.classList.remove('is-dragging');
  }

  function onPointerUp(e) {
    if (!state.drag || e.pointerId !== state.drag.pointerId) return;
    const d = state.drag;
    const target = nearestDot(e.clientX, e.clientY);
    setTarget(null);
    endListeners();
    if (target && target === d.id) {
      solve(d);
    } else {
      if (target) wrongDrop(target, d);
      returnPill(d, Boolean(target));
    }
  }

  function onPointerCancel(e) {
    if (!state.drag || e.pointerId !== state.drag.pointerId) return;
    const d = state.drag;
    setTarget(null);
    endListeners();
    returnPill(d, false);
  }

  function solve(d) {
    const id = d.id;
    state.solved.add(id);
    d.ghost.remove();
    d.pill.classList.remove('is-source');
    d.pill.classList.add('is-gone');
    const group = d.pill.closest('.group');
    setTimeout(() => {
      d.pill.remove();
      if (group && !group.querySelector('.pill')) group.classList.add('is-empty');
    }, 180);
    state.svg.querySelector(`.hl[data-id="${id}"]`).classList.add('is-on');
    state.svg.querySelector(`.lbl[data-id="${id}"]`).classList.add('is-on');
    state.dots.get(id).node.classList.add('is-done');
    state.drag = null;
    updateStats();
    if (state.solved.size === state.map.features.length) {
      document.querySelector('.tray').classList.add('is-complete');
      setTimeout(showDone, 900);
    }
  }

  function wrongDrop(targetId, d) {
    state.errors += 1;
    updateStats();
    const node = state.dots.get(targetId).node;
    node.classList.add('is-wrong');
    setTimeout(() => node.classList.remove('is-wrong'), 600);
    d.ghost.classList.add('is-wrong');
  }

  // The pill returns to its place in the tray
  function returnPill(d, wasWrong) {
    const r = d.pill.getBoundingClientRect();
    const go = () => {
      d.ghost.classList.add('is-returning');
      d.ghost.style.transform = `translate(${r.left}px, ${r.top}px)`;
      const done = () => {
        d.ghost.remove();
        d.pill.classList.remove('is-source');
      };
      d.ghost.addEventListener('transitionend', done, { once: true });
      setTimeout(done, 450); // fallback in case transitionend doesn't fire
    };
    state.drag = null;
    if (wasWrong) setTimeout(go, 280); else requestAnimationFrame(go);
  }

  function showDone() {
    const n = state.map.features.length, e = state.errors;
    const err = e === 0 ? 'sense cap error' : e === 1 ? 'amb 1 error' : `amb ${e} errors`;
    $('#done-text').textContent = `Has situat els ${n} accidents geogràfics d'${state.map.title} ${err}.`;
    $('#done').hidden = false;
  }

  // ------------------------------------------------------------------ init
  function init() {
    setupMobileWarning();
    document.querySelectorAll('.map-btn').forEach((b) =>
      b.addEventListener('click', () => { location.hash = `#/${b.dataset.map}`; }));
    $('#btn-home').addEventListener('click', () => { location.hash = ''; });
    $('#btn-reset').addEventListener('click', () => state.map && startGame(state.map));
    $('#done-close').addEventListener('click', () => { $('#done').hidden = true; });
    $('#done-reset').addEventListener('click', () => { $('#done').hidden = true; startGame(state.map); });
    $('#done-home').addEventListener('click', () => { location.hash = ''; });
    window.addEventListener('hashchange', route);
    route();
  }

  init();
})();
