/* Homelib -- Deus, in adjutorium meum intende
 *
 * The whole catalogue is loaded once and filtered here.  That is not laziness:
 * the server is a Pi Zero, and a query per keystroke over wifi would feel
 * broken, while 3500 books in memory is nothing for a phone.  Writes still go
 * to the server, and the catalogue is re-fetched after each one.
 */
(function () {
'use strict';

/* ------------------------------------------------------------------ helpers */

const $ = (sel, root) => (root || document).querySelector(sel);
const $$ = (sel, root) => Array.from((root || document).querySelectorAll(sel));

function el(tag, attrs) {
  const node = document.createElement(tag);
  if (attrs) for (const [k, v] of Object.entries(attrs)) {
    if (v === null || v === undefined || v === false) continue;
    if (k === 'class') node.className = v;
    else if (k === 'text') node.textContent = v;
    else if (k === 'html') node.innerHTML = v;
    else if (k === 'dataset') Object.assign(node.dataset, v);
    else if (k.startsWith('on')) node.addEventListener(k.slice(2), v);
    else if (v === true) node.setAttribute(k, '');
    else node.setAttribute(k, v);
  }
  for (let i = 2; i < arguments.length; i++) {
    const kid = arguments[i];
    if (kid === null || kid === undefined || kid === false) continue;
    if (Array.isArray(kid)) kid.forEach(k => k && node.appendChild(
      typeof k === 'string' ? document.createTextNode(k) : k));
    else node.appendChild(typeof kid === 'string'
      ? document.createTextNode(kid) : kid);
  }
  return node;
}

/* Accent- and case-insensitive comparison.  Searching "etagere" has to find
 * "étagère": half the catalogue is accented and nobody types accents in a
 * hurry. */
function norm(s) {
  return (s || '').toLowerCase()
    .normalize('NFD').replace(/[\u0300-\u036f]/g, '');
}

const collator = new Intl.Collator('fr', { sensitivity: 'base', numeric: true });

function debounce(fn, ms) {
  let timer;
  return function () {
    const args = arguments;
    clearTimeout(timer);
    timer = setTimeout(() => fn.apply(null, args), ms);
  };
}

/* ------------------------------------------------------------------- i18n */

let LANG = localStorage.getItem('homelib.lang')
        || ((navigator.language || 'fr').startsWith('en') ? 'en' : 'fr');

function t(key) {
  const table = window.I18N[LANG] || window.I18N.fr;
  let s = table[key];
  if (s === undefined) s = window.I18N.fr[key];
  if (s === undefined) return key;
  for (let i = 1; i < arguments.length; i++) {
    s = s.split('{' + (i - 1) + '}').join(arguments[i]);
  }
  return s;
}

/* French, like English, takes the singular for 0 and 1. */
function plural(n, singular, many) {
  return n + ' ' + t(Math.abs(n) < 2 ? singular : many);
}

function applyStaticI18n() {
  document.documentElement.lang = LANG;
  $$('[data-i18n]').forEach(n => { n.textContent = t(n.dataset.i18n); });
  $$('[data-i18n-title]').forEach(n => { n.title = t(n.dataset.i18nTitle); });
  $('#lang-label').textContent = LANG === 'fr' ? 'EN' : 'FR';
}

/* ------------------------------------------------------------------ theme */

function applyTheme(theme) {
  if (theme) document.documentElement.setAttribute('data-theme', theme);
  else document.documentElement.removeAttribute('data-theme');
  const meta = $('meta[name=theme-color]');
  if (meta) meta.content = getComputedStyle(document.body)
    .getPropertyValue('--paper').trim() || '#7a5c3e';
}

function currentTheme() { return localStorage.getItem('homelib.theme') || ''; }

/* ----------------------------------------------------------------- toasts */

function toast(message, kind, action) {
  const node = el('div', { class: 'toast' + (kind === 'error' ? ' error' : '') },
    el('span', { text: message }));
  if (action) {
    node.appendChild(el('button', { text: action.label, onclick: () => {
      node.remove(); action.run();
    } }));
  }
  $('#toasts').appendChild(node);
  setTimeout(() => node.remove(), action ? 9000 : 4000);
  return node;
}

/* -------------------------------------------------------------------- api */

async function api(path, options) {
  const opts = Object.assign({ headers: {} }, options || {});
  if (opts.body !== undefined && typeof opts.body !== 'string') {
    opts.body = JSON.stringify(opts.body);
    opts.headers['Content-Type'] = 'application/json';
  }
  const response = await fetch(path, opts);
  const text = await response.text();
  let data = null;
  try { data = text ? JSON.parse(text) : null; } catch (e) { data = null; }
  if (!response.ok) {
    throw new Error((data && data.error) || response.statusText || 'HTTP ' + response.status);
  }
  return data;
}

/* ------------------------------------------------------------------ state */

const S = {
  data: null,          // catalogue as served
  usage: null,         // reference counts, for spotting orphans
  byId: {},            // book id -> book
  offline: false,
  filters: { all: '', title: '', authors: '', publisher: '', box: '', library: '' },
  showFilters: false,
  showDeleted: false,
  sort: { key: 'title', dir: 1 },
  limit: 200,
  selection: new Set(),   // book ids picked for a mass move
  route: null
};

const CACHE_KEY = 'homelib.catalog';

function indexCatalog(data) {
  S.data = data;
  S.usage = data.usage || { authors: {}, publishers: {}, boxes: {}, libraries: {} };
  S.byId = {};
  data.books.forEach(b => {
    S.byId[b.id] = b;
    b._authors = b.author_kind === 'anonymous' ? t('book.anonymous')
               : b.author_kind === 'collective' ? t('book.collective')
               : b.authors.join(', ');
    // Pre-normalised haystacks: filtering runs on every keystroke and must not
    // redo this work 3500 times a frame.
    b._nt = norm(b.title);
    b._na = norm(b._authors);
    b._np = norm(b.publisher);
    b._nb = norm(b.box + ' ' + b.box_ref);
    b._nl = norm(b.library);
    b._nm = norm(b.more);
    b._all = [b._nt, b._na, b._np, b._nb, b._nl, b._nm].join(' ');
  });
  S.libById = {}; data.libraries.forEach(l => { S.libById[l.id] = l; });
  S.boxById = {}; data.boxes.forEach(b => { S.boxById[b.id] = b; });
  S.authorById = {}; data.authors.forEach(a => { S.authorById[a.id] = a; });
  S.pubById = {}; data.publishers.forEach(p => { S.pubById[p.id] = p; });
}

async function loadCatalog(showSpinner) {
  if (showSpinner && S.route) render();
  try {
    const data = await api('/api/catalog');
    S.offline = false;
    indexCatalog(data);
    try { localStorage.setItem(CACHE_KEY, JSON.stringify(data)); }
    catch (e) { /* quota: offline browsing is a bonus, not a promise */ }
    return true;
  } catch (err) {
    const cached = localStorage.getItem(CACHE_KEY);
    if (cached) {
      S.offline = true;
      indexCatalog(JSON.parse(cached));
      return true;
    }
    throw err;
  }
}

/* -------------------------------------------------------------- git status */

let syncTimer = null;

async function refreshSync() {
  const dot = $('#sync-dot'), label = $('#sync-label');
  try {
    const info = await api('/api/sync');
    if (!info.enabled) {
      dot.className = 'sync-dot'; dot.style.background = 'var(--ink-faint)';
      label.textContent = t('sync.off');
      $('#sync-chip').title = t('sync.off');
      return;
    }
    const bits = [t('sync.now')];
    if (info.head) bits.push(t('sync.head') + ' : ' + info.head);
    if (info.unpushed) bits.push(info.unpushed + ' ' + t('sync.unpushed'));
    bits.push(t('sync.lastpush') + ' : ' + (info.last_push || t('sync.never')));
    if (info.error) bits.push(info.error);
    $('#sync-chip').title = bits.join('\n');

    if (info.error || info.diverged) {
      dot.className = 'sync-dot error';
      label.textContent = info.diverged ? t('sync.diverged') : t('sync.error');
    } else if (info.pending || info.unpushed) {
      dot.className = 'sync-dot pending';
      label.textContent = t('sync.pending');
    } else {
      dot.className = 'sync-dot';
      label.textContent = t('sync.idle');
    }
  } catch (e) {
    dot.className = 'sync-dot error';
    label.textContent = t('sync.error');
  }
}

async function syncNow() {
  const dot = $('#sync-dot'), label = $('#sync-label');
  dot.className = 'sync-dot busy';
  label.textContent = t('sync.busy');
  try {
    const info = await api('/api/sync', { method: 'POST' });
    if (info.diverged) toast(t('sync.diverged'), 'error');
    else if (info.pushed) toast(t('sync.pushed'));
    else if (info.error) toast(info.error, 'error');
    else toast(t('sync.uptodate'));
  } catch (err) {
    toast(err.message, 'error');
  }
  refreshSync();
}

/* ------------------------------------------------------------ shelf drawing */

/* The Qt application draws the library as a grid with the book's shelf picked
 * out in red (gui/libpattern.py).  Same idea, as SVG, and here the cells are
 * clickable -- which turns the drawing from an illustration into a way to
 * browse. */
function shelfSvg(lib, options) {
  const opts = options || {};
  const lines = Math.max(1, lib.lines || 1);
  const columns = Math.max(1, lib.columns || 1);
  const cell = 100, gap = 6, left = 22, top = 18, caption = opts.caption ? 30 : 6;
  const width = left + columns * (cell + gap);
  const height = top + lines * (cell + gap) + caption;

  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('class', 'shelf-svg');
  svg.setAttribute('viewBox', '0 0 ' + width + ' ' + height);
  svg.setAttribute('role', 'img');
  // Cap the drawing by its own size rather than letting it fill the column:
  // several libraries are a single shelf wide, and stretched to the full width
  // one cell would fill the screen.  One viewBox unit ends up roughly one
  // pixel, so a cell is about 100px whatever the grid.
  svg.style.maxWidth = Math.min(width, 560) + 'px';
  const mk = (name, attrs, text) => {
    const n = document.createElementNS('http://www.w3.org/2000/svg', name);
    for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
    if (text !== undefined) n.textContent = text;
    svg.appendChild(n);
    return n;
  };

  const boxes = (S.data ? S.data.boxes : []).filter(b => b.library === lib.id);
  const at = {};
  boxes.forEach(b => { at[b.line + ':' + b.column] = b; });

  for (let c = 0; c < columns; c++) {
    const letter = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'[c];
    const hot = opts.selectedBox && opts.selectedBox.column === letter;
    mk('text', { x: left + c * (cell + gap) + cell / 2, y: 12,
                 'text-anchor': 'middle',
                 class: 'axis' + (hot ? ' hot' : '') }, letter);
  }

  for (let r = 1; r <= lines; r++) {
    const hot = opts.selectedBox && opts.selectedBox.line === r;
    mk('text', { x: 11, y: top + (r - 1) * (cell + gap) + cell / 2 + 4,
                 'text-anchor': 'middle',
                 class: 'axis' + (hot ? ' hot' : '') }, String(r));

    for (let c = 0; c < columns; c++) {
      const letter = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'[c];
      const box = at[r + ':' + letter];
      const x = left + c * (cell + gap), y = top + (r - 1) * (cell + gap);
      const count = box ? (S.usage.boxes[box.id] || 0) : 0;
      const selected = box && opts.selectedBox && box.id === opts.selectedBox.id;

      let cls = 'cell';
      if (selected) cls += ' selected';
      else if (count) cls += ' filled';
      if (box && opts.onPick) cls += ' clickable';

      const rect = mk('rect', { x: x, y: y, width: cell, height: cell,
                                rx: 5, class: cls });
      if (box && opts.onPick) {
        rect.addEventListener('click', () => opts.onPick(box));
        rect.style.cursor = 'pointer';
        mk('title', {}, box.name);
      }
      if (!box) continue;

      // Wrap the shelf name by hand: SVG has no text flow.
      const words = String(box.name).split(/\s+/);
      const rows = [];
      let current = '';
      words.forEach(w => {
        if ((current + ' ' + w).trim().length > 14 && current) {
          rows.push(current); current = w;
        } else current = (current + ' ' + w).trim();
      });
      if (current) rows.push(current);
      const shown = rows.slice(0, 5);
      if (rows.length > 5) shown[4] = shown[4].slice(0, 11) + '…';

      const startY = y + cell / 2 - (shown.length - 1) * 5 - 3;
      shown.forEach((row, i) => {
        const node = mk('text', {
          x: x + cell / 2, y: startY + i * 10, 'text-anchor': 'middle',
          class: 'name' + (selected ? ' on-selected' : '')
        }, row);
        if (selected) node.style.fill = 'var(--accent-ink)';
      });
      if (count) {
        const node = mk('text', { x: x + cell / 2, y: y + cell - 7,
                                  'text-anchor': 'middle', class: 'count' },
                        plural(count, 'app.book', 'app.books'));
        if (selected) node.style.fill = 'var(--accent-ink)';
      }
    }
  }

  if (opts.caption) {
    mk('text', { x: 2, y: height - 16, class: 'name' }, lib.name);
    mk('text', { x: 2, y: height - 5, class: 'count' },
       String(lib.place || '').split('\n')[0]);
  }
  return svg;
}

/* ------------------------------------------------------- combo box widget */

/* The Qt Selector (gui/newbook.py) is an editable combo whose completer
 * matches anywhere in the string, not just the start.  Same behaviour here,
 * with an extra line that creates the missing entry on the spot -- the Qt
 * version needed a separate button and a second dialog for that. */
function combo(config) {
  let items = config.items || [];
  let selected = config.value === undefined ? null : config.value;
  let highlighted = -1;

  const input = el('input', {
    type: 'text', placeholder: config.placeholder || '',
    autocomplete: 'off', autocorrect: 'off', autocapitalize: 'off',
    spellcheck: 'false'
  });
  const list = el('div', { class: 'combo-list', hidden: true });
  const node = el('div', { class: 'combo' }, input, list);

  function labelOf(id) {
    const item = items.find(i => i.id === id);
    return item ? item.label : '';
  }
  function matches() {
    const needle = norm(input.value);
    const exact = items.find(i => norm(i.label) === needle);
    let out = needle ? items.filter(i => norm(i.label).includes(needle)) : items.slice();
    out = out.slice(0, 60);
    return { list: out, exact: exact };
  }
  function draw() {
    const { list: found, exact } = matches();
    list.textContent = '';
    found.forEach((item, i) => {
      const row = el('div', {
        class: i === highlighted ? 'on' : '',
        onmousedown: ev => { ev.preventDefault(); pick(item); }
      }, el('span', { text: item.label }));
      if (item.sub) row.appendChild(el('span', { class: 'sub', text: ' · ' + item.sub }));
      list.appendChild(row);
    });
    // Creating goes last, the way the command line offers "New author" after
    // the existing ones.  First in the list, a hurried click on a partial name
    // would add a second Bainville instead of picking the one already there.
    if (config.onCreate && input.value.trim() && !exact) {
      list.appendChild(el('div', {
        class: 'create',
        onmousedown: ev => { ev.preventDefault(); create(); }
      }, '+ ' + t('app.create') + ' « ' + input.value.trim() + ' »'));
    }
    if (!list.childNodes.length) list.hidden = true;
  }
  function open() { list.hidden = false; highlighted = -1; draw(); }
  function close() { list.hidden = true; }
  function pick(item) {
    selected = item.id;
    input.value = item.label;
    close();
    if (config.onChange) config.onChange(selected);
  }
  async function create() {
    const value = input.value.trim();
    close();
    const made = await config.onCreate(value);
    // onCreate resolves null when the user cancelled the sub-dialog.
    if (!made) { input.focus(); return; }
    if (!items.some(i => i.id === made.id)) items = items.concat([made]);
    config.items = items;
    pick(made);
  }

  input.addEventListener('focus', open);
  input.addEventListener('input', () => {
    selected = null;
    if (config.onChange) config.onChange(null);
    open();
  });
  input.addEventListener('blur', () => setTimeout(close, 120));
  input.addEventListener('keydown', ev => {
    const rows = $$('div', list).filter(n => !n.classList.contains('create'));
    if (ev.key === 'ArrowDown' || ev.key === 'ArrowUp') {
      ev.preventDefault();
      if (list.hidden) open();
      highlighted += (ev.key === 'ArrowDown' ? 1 : -1);
      highlighted = Math.max(0, Math.min(rows.length - 1, highlighted));
      draw();
      const on = $('.on', list);
      if (on) on.scrollIntoView({ block: 'nearest' });
    } else if (ev.key === 'Enter') {
      const { list: found, exact } = matches();
      if (!list.hidden && highlighted >= 0 && found[highlighted]) {
        ev.preventDefault(); pick(found[highlighted]);
      } else if (exact) {
        ev.preventDefault(); pick(exact);
      } else if (found.length === 1) {
        ev.preventDefault(); pick(found[0]);
      }
    } else if (ev.key === 'Escape') { close(); }
  });

  const handle = {
    node: node,
    input: input,
    get value() { return selected; },
    set value(id) {
      selected = id === undefined ? null : id;
      input.value = selected === null ? '' : labelOf(selected);
    },
    get text() { return input.value; },
    setItems(next) { items = next; config.items = next; },
    get invalid() { return selected === null; },
    focus() { input.focus(); }
  };
  if (selected !== null) input.value = labelOf(selected);
  return handle;
}

/* ------------------------------------------------------------------ modals */

/* A stack, not a single slot.  Adding a book you can create its author on the
 * spot, exactly as the Qt dialogs did: the author window opens over the book
 * window and the book window is still there underneath when it closes. */
const modalStack = [];

function openModal(config) {
  const root = $('#modal-root');
  const body = el('div', { class: 'modal-body' });
  if (config.body) body.appendChild(config.body);

  const foot = el('div', { class: 'modal-foot' });
  (config.actions || []).forEach(a => {
    if (a === 'spacer') { foot.appendChild(el('span', { class: 'left' })); return; }
    foot.appendChild(el('button', {
      class: 'btn ' + (a.kind || '') + (a.left ? ' left' : ''),
      text: a.label, onclick: a.run, disabled: a.disabled
    }));
  });

  const modal = el('div', { class: 'modal', role: 'dialog', 'aria-modal': 'true' },
    el('div', { class: 'modal-head' },
      el('h2', { text: config.title }),
      el('button', { class: 'icon-btn', 'aria-label': t('app.close'),
                     text: '✕', onclick: () => closeModal() })),
    body,
    (config.actions || []).length ? foot : null);

  // Hide whatever is underneath instead of discarding it.
  if (modalStack.length) modalStack[modalStack.length - 1].node.hidden = true;
  root.appendChild(modal);
  root.hidden = false;
  modalStack.push({ config: config, node: modal });
  const first = $('input, textarea, select, button.primary', modal);
  if (first && window.innerWidth > 820) setTimeout(() => first.focus(), 40);
  if (config.onOpen) config.onOpen(modal);
  return modal;
}

function closeModal() {
  const top = modalStack.pop();
  if (top) top.node.remove();
  const below = modalStack[modalStack.length - 1];
  if (below) {
    below.node.hidden = false;
  } else {
    $('#modal-root').hidden = true;
    $('#modal-root').textContent = '';
  }
  if (top && top.config.onClose) top.config.onClose();
}

/* Dismiss without running onClose.  Used when the route itself changes -- the
 * Back button, or a tap on the navigation while a book is open.  Running
 * onClose there would call history.back() and fight the navigation that is
 * already under way. */
function closeModalSilently() {
  modalStack.length = 0;
  const root = $('#modal-root');
  root.hidden = true;
  root.textContent = '';
}

function confirmDialog(title, message, confirmLabel, run) {
  openModal({
    title: title,
    body: el('p', { text: message }),
    actions: [
      { label: t('app.cancel'), run: () => closeModal() },
      { label: confirmLabel, kind: 'primary danger', run: () => { closeModal(); run(); } }
    ]
  });
}

/* --------------------------------------------------------- write operations */

/* Every write goes through here so that a failure is reported the same way
 * everywhere, and the catalogue is always re-read afterwards -- the server is
 * the authority on what is now in the database, not our optimistic guess. */
async function mutate(request, successMessage, options) {
  if (S.offline) { toast(t('app.offline'), 'error'); return null; }
  options = options || {};
  try {
    const result = await api(request.path, {
      method: request.method || 'POST', body: request.body
    });
    await loadCatalog();
    // keepView is for a creation made from inside another dialog: re-rendering
    // the route would tear down the form the user is still filling in.
    if (!options.keepView) render();
    refreshSync();
    if (successMessage) {
      toast(successMessage, null, options.undo && {
        label: t('app.undo'), run: () => mutate(options.undo, t('app.saved'))
      });
    }
    return result;
  } catch (err) {
    toast(err.message, 'error');
    return null;
  }
}

/* ------------------------------------------------------------ author dialog */

/* `existing` may be a row being edited, or merely a prefill for a new entry --
 * the combo boxes pass the half-typed name through.  An id is what separates
 * the two; without this, "create" posted to /api/authors/null. */
function authorDialog(existing, afterwards) {
  const isEdit = !!(existing && existing.id);
  const nested = !!afterwards;   // opened from another dialog still on screen
  // save() closes the window itself, and onClose must not then report a
  // cancellation -- the promise the combo is waiting on settles on first call.
  let saving = false;
  const first = el('input', { type: 'text', value: existing ? existing.christian_name || '' : '' });
  const last = el('input', { type: 'text', value: existing ? existing.last_name || '' : '' });
  const body = el('div', {}, el('div', { class: 'grid-2' },
    el('label', { class: 'field' }, el('span', { class: 'label', text: t('author.first') }), first),
    el('label', { class: 'field' }, el('span', { class: 'label', text: t('author.last') }), last)));

  const save = async () => {
    const payload = { christian_name: first.value.trim(), last_name: last.value.trim() };
    if (!payload.christian_name && !payload.last_name) { first.focus(); return; }
    saving = true;
    closeModal();
    const result = await mutate(isEdit
      ? { path: '/api/authors/' + existing.id, method: 'PUT', body: payload }
      : { path: '/api/authors', body: payload }, t('app.saved'), { keepView: nested });
    if (afterwards) {
      afterwards(result && (result.id || existing.id),
                 [payload.christian_name, payload.last_name].filter(Boolean).join(' '));
    }
  };
  openModal({
    title: isEdit ? t('author.edit') : t('author.new'), body: body,
    onClose: () => { if (!saving && afterwards) afterwards(null); },
    actions: [{ label: t('app.cancel'), run: () => closeModal() },
              { label: t('app.save'), kind: 'primary', run: save }]
  });
}

function publisherDialog(existing, afterwards) {
  const isEdit = !!(existing && existing.id);
  const nested = !!afterwards;
  let saving = false;
  const name = el('input', { type: 'text', value: existing ? existing.name || '' : '' });
  const body = el('label', { class: 'field' },
    el('span', { class: 'label', text: t('publisher.name') }), name);
  const save = async () => {
    if (!name.value.trim()) { name.focus(); return; }
    const value = name.value.trim();
    saving = true;
    closeModal();
    const result = await mutate(isEdit
      ? { path: '/api/publishers/' + existing.id, method: 'PUT', body: { name: value } }
      : { path: '/api/publishers', body: { name: value } }, t('app.saved'),
      { keepView: nested });
    if (afterwards) afterwards(result && (result.id || existing.id), value);
  };
  openModal({
    title: isEdit ? t('publisher.edit') : t('publisher.new'), body: body,
    onClose: () => { if (!saving && afterwards) afterwards(null); },
    actions: [{ label: t('app.cancel'), run: () => closeModal() },
              { label: t('app.save'), kind: 'primary', run: save }]
  });
}

function libraryDialog(existing, afterwards) {
  const isEdit = !!(existing && existing.id);
  const nested = !!afterwards;
  let saving = false;
  const name = el('input', { type: 'text', value: existing ? existing.name || '' : '' });
  const place = el('textarea', {}, existing ? existing.place || '' : '');
  const lines = el('input', { type: 'number', min: '1', max: '99',
                              value: existing ? existing.lines : 3 });
  const columns = el('input', { type: 'number', min: '1', max: '26',
                                value: existing ? existing.columns : 1 });
  const preview = el('div', { style: 'margin-top:10px' });
  const drawPreview = () => {
    preview.textContent = '';
    preview.appendChild(shelfSvg({
      id: existing ? existing.id : -1, name: name.value || '…',
      place: place.value, lines: +lines.value || 1, columns: +columns.value || 1
    }, { caption: true }));
  };
  lines.addEventListener('input', drawPreview);
  columns.addEventListener('input', drawPreview);
  name.addEventListener('input', drawPreview);

  const body = el('div', {},
    el('label', { class: 'field' }, el('span', { class: 'label', text: t('lib.name') }), name),
    el('label', { class: 'field' }, el('span', { class: 'label', text: t('lib.place') }), place),
    el('div', { class: 'grid-2' },
      el('label', { class: 'field' }, el('span', { class: 'label', text: t('lib.lines') }), lines),
      el('label', { class: 'field' }, el('span', { class: 'label', text: t('lib.columns') }), columns)),
    preview);
  drawPreview();

  const save = async () => {
    const payload = { name: name.value.trim(), place: place.value.trim(),
                      lines: +lines.value, columns: +columns.value };
    if (!payload.name || !payload.place) { name.focus(); return; }
    saving = true;
    closeModal();
    const result = await mutate(isEdit
      ? { path: '/api/libraries/' + existing.id, method: 'PUT', body: payload }
      : { path: '/api/libraries', body: payload }, t('app.saved'), { keepView: nested });
    if (afterwards) afterwards(result && (result.id || existing.id), payload.name);
  };
  openModal({
    title: isEdit ? t('lib.edit') : t('lib.new'), body: body,
    onClose: () => { if (!saving && afterwards) afterwards(null); },
    actions: [{ label: t('app.cancel'), run: () => closeModal() },
              { label: t('app.save'), kind: 'primary', run: save }]
  });
}

function boxDialog(existing, afterwards) {
  const isEdit = !!(existing && existing.id);
  const nested = !!afterwards;
  let saving = false;
  const name = el('input', { type: 'text', value: existing ? existing.name || '' : '' });
  const line = el('input', { type: 'number', min: '1',
                             value: existing ? existing.line : 1 });
  const column = el('select', {});
  const preview = el('div', { style: 'margin-top:10px' });

  const libCombo = combo({
    items: S.data.libraries.map(l => ({ id: l.id, label: l.name, sub: (l.place || '').split('\n')[0] })),
    value: existing ? existing.library : null,
    placeholder: t('box.library'),
    onCreate: value => new Promise(resolve => {
      libraryDialog({ name: value, place: '', lines: 3, columns: 1 },
        (id, label) => resolve(id ? { id: id, label: label } : null));
    }),
    onChange: () => { fillColumns(); drawPreview(); }
  });

  function currentLibrary() { return S.libById[libCombo.value]; }
  function fillColumns() {
    const lib = currentLibrary();
    // Keep what is on screen once the select has been built; using the stored
    // letter every time meant picking column C and then correcting the library
    // silently put the shelf back in its original column.
    const wanted = column.value || (existing ? existing.column : '') || 'A';
    column.textContent = '';
    const n = lib ? lib.columns || 1 : 1;
    for (let i = 0; i < n; i++) {
      const letter = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'[i];
      column.appendChild(el('option', { value: letter, text: letter,
                                        selected: letter === wanted }));
    }
    if (lib) line.max = lib.lines;
  }
  function drawPreview() {
    const lib = currentLibrary();
    preview.textContent = '';
    if (!lib) return;
    preview.appendChild(shelfSvg(lib, {
      caption: true,
      selectedBox: { id: existing ? existing.id : -1,
                     line: +line.value, column: column.value }
    }));
  }
  line.addEventListener('input', drawPreview);
  column.addEventListener('change', drawPreview);

  const body = el('div', {},
    el('label', { class: 'field' }, el('span', { class: 'label', text: t('box.name') }), name),
    el('label', { class: 'field' }, el('span', { class: 'label', text: t('box.library') }), libCombo.node),
    el('div', { class: 'grid-2' },
      el('label', { class: 'field' }, el('span', { class: 'label', text: t('box.line') }), line),
      el('label', { class: 'field' }, el('span', { class: 'label', text: t('box.column') }), column)),
    preview);
  fillColumns(); drawPreview();

  const save = async () => {
    if (!name.value.trim()) { name.focus(); return; }
    if (libCombo.invalid) { libCombo.focus(); return; }
    const payload = { name: name.value.trim(), library_id: libCombo.value,
                      line: +line.value, column: column.value };
    saving = true;
    closeModal();
    const result = await mutate(isEdit
      ? { path: '/api/boxes/' + existing.id, method: 'PUT', body: payload }
      : { path: '/api/boxes', body: payload }, t('app.saved'), { keepView: nested });
    if (afterwards) {
      const id = result && (result.id || existing.id);
      afterwards(id, id ? boxLabel(S.boxById[id] || { name: payload.name,
        library: payload.library_id, column: payload.column, line: payload.line })
        : payload.name);
    }
  };
  openModal({
    title: isEdit ? t('box.edit') : t('box.new'), body: body,
    onClose: () => { if (!saving && afterwards) afterwards(null); },
    actions: [{ label: t('app.cancel'), run: () => closeModal() },
              { label: t('app.save'), kind: 'primary', run: save }]
  });
}

/* -------------------------------------------------------------- book dialog */

function boxLabel(box) {
  const lib = S.libById[box.library];
  return box.name + ' — ' + (lib ? lib.name : '?') + ' ' + box.column + box.line;
}

function bookDialog(book) {
  const isEdit = !!book;
  const title = el('input', { type: 'text', value: isEdit ? book.title : '' });
  const details = el('textarea', {}, isEdit ? book.more : '');
  const volumes = el('input', { type: 'number', min: '1', inputmode: 'numeric',
    placeholder: t('book.volumes_auto'),
    value: isEdit && book.volumes != null ? book.volumes : '' });

  /* --- ISBN pre-fill ------------------------------------------------- */
  const isbnInput = el('input', { type: 'text', placeholder: '978…',
                                  inputmode: 'numeric', autocomplete: 'off' });
  const isbnNote = el('p', { class: 'hint', text: t('book.isbn_hint') });
  const isbnButton = el('button', { class: 'btn small', text: t('book.isbn_lookup'),
                                    onclick: lookupIsbn });
  async function lookupIsbn() {
    const code = isbnInput.value.trim();
    if (!code) return;
    isbnButton.disabled = true;
    isbnNote.textContent = '…';
    try {
      const found = await api('/api/isbn/' + encodeURIComponent(code));
      if (found.title && !title.value.trim()) {
        title.value = found.subtitle ? found.title + '. ' + found.subtitle : found.title;
      }
      // Only names we already know can be selected; the rest are offered as
      // text so the "create" line in the combo picks them up.
      if (found.authors.length) {
        setAuthorsFromNames(found.authors);
      }
      if (found.publishers.length) {
        publisherCombo.input.value = found.publishers[0];
        const match = S.data.publishers.find(
          p => norm(p.name) === norm(found.publishers[0]));
        publisherCombo.value = match ? match.id : null;
      }
      if (found.date && !details.value.trim()) details.value = found.date;
      isbnNote.textContent = t('book.isbn_found', found.title);
    } catch (err) {
      isbnNote.textContent = err.message;
    }
    isbnButton.disabled = false;
  }
  isbnInput.addEventListener('keydown', ev => {
    if (ev.key === 'Enter') { ev.preventDefault(); lookupIsbn(); }
  });

  /* --- authors -------------------------------------------------------- */
  const authorRows = el('div', {});
  const rows = [];
  const anonymous = el('input', { type: 'checkbox' });
  const collective = el('input', { type: 'checkbox' });

  function authorItems() {
    return S.data.authors.map(a => ({
      id: a.id, label: a.label,
      sub: S.usage.authors[a.id] ? undefined : t('author.orphan')
    }));
  }
  function addAuthorRow(value) {
    const box = combo({
      items: authorItems(), value: value === undefined ? null : value,
      placeholder: t('book.authors'),
      onCreate: name => new Promise(resolve => {
        // Split "Prénom Nom" on the last space, the usual case.
        const parts = name.trim().split(/\s+/);
        const last = parts.length > 1 ? parts.pop() : parts[0];
        authorDialog({ id: null, christian_name: parts.join(' '), last_name: last },
          (id, label) => resolve(id ? { id: id, label: label } : null));
      })
    });
    const row = el('div', { class: 'author-row' }, box.node);
    const remove = el('button', {
      class: 'btn', text: '−', title: t('app.delete'),
      onclick: () => {
        if (rows.length === 1) return;
        const i = rows.indexOf(box); rows.splice(i, 1); row.remove();
      }
    });
    const add = el('button', {
      class: 'btn', text: '+', title: t('book.add_author'),
      onclick: () => addAuthorRow()
    });
    row.appendChild(remove); row.appendChild(add);
    authorRows.appendChild(row);
    rows.push(box);
    return box;
  }
  function setAuthorsFromNames(names) {
    authorRows.textContent = ''; rows.length = 0;
    names.forEach(name => {
      // Match the whole name, or a surname that is genuinely the last word of
    // it.  A plain substring test made "Jean Leroy" select the existing author
    // "Roy", and the book would be saved credited to them.
    const words = norm(name).split(/\s+/).filter(Boolean);
    const surname = words[words.length - 1];
    const match = S.data.authors.find(a => norm(a.label) === norm(name))
        || S.data.authors.find(a => norm(a.last_name) && norm(a.last_name) === surname);
      const box = addAuthorRow(match ? match.id : null);
      if (!match) box.input.value = name;
    });
    if (!rows.length) addAuthorRow();
  }
  function toggleAuthors() {
    const off = anonymous.checked || collective.checked;
    authorRows.style.display = off ? 'none' : '';
  }
  anonymous.addEventListener('change', () => {
    if (anonymous.checked) collective.checked = false; toggleAuthors();
  });
  collective.addEventListener('change', () => {
    if (collective.checked) anonymous.checked = false; toggleAuthors();
  });

  /* --- publisher and box ---------------------------------------------- */
  const publisherCombo = combo({
    items: S.data.publishers.map(p => ({ id: p.id, label: p.name })),
    value: isEdit ? book.publisher_id : null,
    placeholder: t('book.publisher'),
    onCreate: name => new Promise(resolve => {
      publisherDialog({ id: null, name: name },
                      (id, label) => resolve(id ? { id: id, label: label } : null));
    })
  });

  const boxPreview = el('div', { style: 'margin-top:8px' });
  const boxCombo = combo({
    items: S.data.boxes.map(b => ({ id: b.id, label: boxLabel(b) })),
    value: isEdit ? book.box_id : null,
    placeholder: t('book.box'),
    onCreate: name => new Promise(resolve => {
      boxDialog({ id: null, name: name, library: null, line: 1, column: 'A' },
        (id, label) => resolve(id ? { id: id, label: label } : null));
    }),
    onChange: drawBoxPreview
  });
  function drawBoxPreview() {
    boxPreview.textContent = '';
    const box = S.boxById[boxCombo.value];
    if (!box) return;
    const lib = S.libById[box.library];
    if (lib) boxPreview.appendChild(shelfSvg(lib, { selectedBox: box, caption: true }));
  }

  /* --- assemble ------------------------------------------------------- */
  if (isEdit) {
    if (book.author_kind === 'anonymous') anonymous.checked = true;
    else if (book.author_kind === 'collective') collective.checked = true;
    else book.author_ids.forEach(id => addAuthorRow(id));
  }
  if (!rows.length) addAuthorRow();
  toggleAuthors();
  drawBoxPreview();

  const body = el('div', {},
    el('label', { class: 'field' },
      el('span', { class: 'label', text: t('book.title') }), title),
    !isEdit ? el('div', { class: 'field' },
      el('span', { class: 'label', text: t('book.isbn') }),
      el('div', { class: 'btn-row' },
        el('div', { style: 'flex:1;min-width:150px' }, isbnInput), isbnButton),
      isbnNote) : null,
    el('div', { class: 'field' },
      el('span', { class: 'label', text: t('book.authors') }),
      el('div', { class: 'checkrow' },
        el('label', {}, anonymous, t('book.anonymous')),
        el('label', {}, collective, t('book.collective'))),
      authorRows),
    el('label', { class: 'field' },
      el('span', { class: 'label', text: t('book.publisher') }), publisherCombo.node),
    el('div', { class: 'field' },
      el('span', { class: 'label', text: t('book.box') }), boxCombo.node, boxPreview),
    el('div', { class: 'grid-2' },
      el('label', { class: 'field' },
        el('span', { class: 'label', text: t('book.volumes') }), volumes,
        el('p', { class: 'hint', text: t('book.volumes_hint') }))),
    el('label', { class: 'field' },
      el('span', { class: 'label', text: t('book.details') }), details));

  const save = async () => {
    if (!title.value.trim()) { title.focus(); toast(t('book.title'), 'error'); return; }
    let kind = 'named', ids = [];
    if (anonymous.checked) kind = 'anonymous';
    else if (collective.checked) kind = 'collective';
    else {
      const bad = rows.find(r => r.invalid && r.text.trim() !== '');
      ids = rows.filter(r => !r.invalid).map(r => r.value);
      if (bad || !ids.length) {
        (bad || rows[0]).focus();
        toast(t('book.authors') + ' — ' + t('app.error'), 'error');
        return;
      }
    }
    if (publisherCombo.invalid) { publisherCombo.focus(); toast(t('book.publisher') + ' — ' + t('app.error'), 'error'); return; }
    if (boxCombo.invalid) { boxCombo.focus(); toast(t('book.box') + ' — ' + t('app.error'), 'error'); return; }

    const payload = {
      title: title.value.trim(), author_kind: kind, author_ids: ids,
      publisher_id: publisherCombo.value, box_id: boxCombo.value,
      more: details.value,
      // Empty means "work it out from the description".
      volumes: volumes.value.trim() === '' ? null : +volumes.value
    };
    const cameFromNew = location.hash === '#/new';
    closeModalSilently();
    if (cameFromNew) leaveRoute('#/search');
    // On an edit the hash is still #/book/<id>, so mutate's render reopens the
    // detail with the new values -- you see what you just saved.
    await mutate(isEdit
      ? { path: '/api/books/' + book.id, method: 'PUT', body: payload }
      : { path: '/api/books', body: payload },
      isEdit ? t('book.updated') : t('book.added'));
  };

  openModal({
    title: isEdit ? t('book.edit') : t('book.new'), body: body,
    actions: [{ label: t('app.cancel'), run: () => closeModal() },
              { label: t('app.save'), kind: 'primary', run: save }],
    onClose: () => {
      if (location.hash === '#/new') leaveRoute('#/search');
      // Cancelling an edit returns to the book it was opened from.
      else if (location.hash.startsWith('#/book/')) render();
    }
  });
}

/* -------------------------------------------------------- book detail view */

async function bookDetail(book) {
  const box = S.boxById[book.box_id];
  const lib = box ? S.libById[box.library] : null;

  const line = (key, value) => el('div', { class: 'detail-line' },
    el('div', { class: 'k', text: key }), el('div', { class: 'v', text: value }));

  const body = el('div', {},
    book.deleted ? el('p', {}, el('span', { class: 'badge danger', text: t('book.deleted_note') })) : null,
    line(t('book.authors'), book._authors),
    line(t('book.publisher'), book.publisher),
    line(t('book.volumes'), book.volumes == null ? '—' : String(book.volumes)),
    line(t('book.box'), box ? box.name + ' · ' + box.column + box.line : '—'),
    line(t('search.library'), lib ? lib.name + (lib.place ? ' — ' + lib.place : '') : '—'),
    book.more ? line(t('book.details'), book.more) : null,
    lib ? el('div', { style: 'margin-top:14px' }, shelfSvg(lib, { selectedBox: box, caption: true })) : null,
    el('div', { class: 'history-slot', style: 'margin-top:14px' }));

  /* Handing over to another dialog uses the silent close: closeModal() would
   * run onClose, which navigates back, and the resulting hashchange would tear
   * down the dialog we just opened.  Only the ✕ and Escape should navigate. */
  const actions = [
    { label: t('app.close'), run: () => closeModal(), left: true },
    book.deleted
      ? { label: t('app.restore'), run: () => { closeModalSilently(); mutate(
          { path: '/api/books/' + book.id + '/restore' }, t('book.restored')); } }
      : { label: t('app.delete'), kind: 'danger', run: () => {
          closeModalSilently();
          confirmDialog(t('app.delete'), t('book.confirm_delete', book.title),
            t('app.delete'), () => mutate(
              { path: '/api/books/' + book.id, method: 'DELETE' },
              t('book.deleted'),
              { undo: { path: '/api/books/' + book.id + '/restore' } }));
        } },
    { label: t('app.edit'), kind: 'primary',
      run: () => { closeModalSilently(); bookDialog(book); } }
  ];

  openModal({
    title: book.title, body: body, actions: actions,
    onClose: () => { if (location.hash.startsWith('#/book/')) leaveRoute('#/search'); }
  });

  // The history is a second request; the dialog should not wait on it.
  try {
    const found = await api('/api/history/books/' + book.id);
    const slot = $('.history-slot', $('#modal-root'));
    if (!slot) return;
    slot.appendChild(el('h3', { text: t('book.history') }));
    if (!found.revisions.length) {
      slot.appendChild(el('p', { class: 'hint', text: t('book.no_history') }));
      return;
    }
    const rows = el('div', { class: 'rows' });
    const total = found.revisions.length;
    found.revisions.slice().reverse().forEach((rev, i) => {
      const revBox = S.boxById[rev.box];
      rows.appendChild(el('div', { class: 'row' },
        el('span', { class: 'badge', text: t('book.revision', total - i) }),
        el('div', { class: 'grow' },
          el('div', { class: 'name', text: rev.name || '—' }),
          el('div', { class: 'sub', text: [
            (S.pubById[rev.publisher] || {}).name,
            revBox ? revBox.name : null, rev.more
          ].filter(Boolean).join(' · ') }))));
    });
    slot.appendChild(rows);
  } catch (e) { /* history is a nicety, not worth an error banner */ }
}

/* ------------------------------------------------------------------ router */

const ROUTES = [
  [/^#\/search$/, () => viewSearch()],
  [/^#\/shelves$/, () => viewShelves()],
  [/^#\/library\/(\d+)$/, m => viewLibrary(+m[1])],
  [/^#\/box\/(\d+)$/, m => viewBox(+m[1])],
  [/^#\/book\/(\d+)$/, m => { viewSearch(); const b = S.byId[+m[1]]; if (b) bookDetail(b); }],
  [/^#\/new$/, () => { viewSearch(); bookDialog(null); }],
  [/^#\/authors$/, () => viewPeople('authors')],
  [/^#\/publishers$/, () => viewPeople('publishers')],
  [/^#\/boxes$/, () => viewBoxes()],
  [/^#\/libraries$/, () => viewLibraries()],
  [/^#\/tools$/, () => viewTools()],
  [/^#\/trash$/, () => viewTrash()],
  [/^#\/history$/, () => viewHistory()],
  [/^#\/stats$/, () => viewStats()],
  [/^#\/export$/, () => viewExport()]
];

function render() {
  const hash = location.hash || '#/search';
  S.route = hash;
  // A modal belongs to the route that opened it; #/book/12 and #/new reopen
  // their own below.
  closeModalSilently();
  const view = $('#view');
  view.textContent = '';
  if (S.offline) {
    view.appendChild(el('div', { class: 'offline-note' }, '⚠ ' + t('app.offline')));
  }
  const match = ROUTES.find(([re]) => re.test(hash));
  if (match) match[1](hash.match(match[0]));
  else { location.hash = '#/search'; return; }

  const base = '#/' + (hash.split('/')[1] || 'search');
  $$('[data-nav]').forEach(a => a.classList.toggle(
    'active', a.getAttribute('href') === base));
  closeNav();
}

function go(hash) { location.hash = hash; }

/* Leaving a route-backed dialog.  The manifest offers a "Nouveau livre"
 * shortcut, so the application can start on #/new with nothing behind it; there
 * history.back() does nothing and the form would reopen itself immediately. */
function leaveRoute(fallback) {
  if (history.length > 1) history.back();
  else location.hash = fallback || '#/search';
}

/* ------------------------------------------------------------ search view */

function filteredBooks() {
  const f = S.filters;
  const n = {
    all: norm(f.all), title: norm(f.title), authors: norm(f.authors),
    publisher: norm(f.publisher), box: norm(f.box), library: norm(f.library)
  };
  let out = S.data.books.filter(b =>
    (S.showDeleted || !b.deleted) &&
    (!n.title || b._nt.includes(n.title)) &&
    (!n.authors || b._na.includes(n.authors)) &&
    (!n.publisher || b._np.includes(n.publisher)) &&
    (!n.box || b._nb.includes(n.box)) &&
    (!n.library || b._nl.includes(n.library)) &&
    (!n.all || b._all.includes(n.all)));

  const key = S.sort.key, dir = S.sort.dir;
  const value = b => key === 'title' ? b.title
                   : key === 'authors' ? b._authors
                   : key === 'publisher' ? b.publisher
                   : key === 'box' ? b.box + ' ' + b.box_ref
                   : key === 'library' ? b.library : b.more;
  out.sort((a, b) => dir * collator.compare(value(a), value(b)));
  return out;
}

function viewSearch() {
  const view = $('#view');
  const f = S.filters;

  const allInput = el('input', {
    type: 'search', value: f.all, placeholder: t('search.placeholder'),
    'aria-label': t('app.search'), autocomplete: 'off'
  });
  const bar = el('div', { class: 'searchbar' },
    el('span', { class: 'glass' },
      elSvg('M11 4a7 7 0 105.2 11.7L21 20.5 M11 4a7 7 0 010 14')),
    allInput);

  const fields = ['title', 'authors', 'publisher', 'box', 'library'];
  const filters = el('div', { class: 'filters' + (S.showFilters ? '' : ' collapsed') });
  fields.forEach(name => {
    const input = el('input', {
      type: 'search', value: f[name], placeholder: t('search.' + name),
      'aria-label': t('search.' + name), autocomplete: 'off'
    });
    input.addEventListener('input', debounce(() => {
      f[name] = input.value; S.limit = 200; drawResults();
    }, 90));
    filters.appendChild(input);
  });

  allInput.addEventListener('input', debounce(() => {
    f.all = allInput.value; S.limit = 200; drawResults();
  }, 90));

  const toggleFilters = el('button', {
    class: 'btn small ghost', text: (S.showFilters ? '▾ ' : '▸ ') + t('search.detailed'),
    onclick: () => {
      S.showFilters = !S.showFilters;
      filters.classList.toggle('collapsed', !S.showFilters);
      toggleFilters.textContent = (S.showFilters ? '▾ ' : '▸ ') + t('search.detailed');
    }
  });
  const deletedToggle = el('label', { style: 'display:flex;gap:6px;align-items:center;cursor:pointer' },
    el('input', { type: 'checkbox', checked: S.showDeleted, onchange: ev => {
      S.showDeleted = ev.target.checked; S.limit = 200; drawResults();
    } }), t('search.showdeleted'));
  const reset = el('button', {
    class: 'btn small ghost', text: t('search.reset'), onclick: () => {
      Object.keys(f).forEach(k => { f[k] = ''; });
      S.limit = 200; render();
    }
  });

  const count = el('span', {});
  const tools = el('div', { class: 'result-tools' }, toggleFilters, deletedToggle,
                   reset, el('span', { style: 'flex:1' }), count);
  const results = el('div', {});

  view.appendChild(el('div', { class: 'page-head' },
    el('h1', { text: t('nav.search') }),
    el('button', { class: 'btn small primary', text: '＋ ' + t('book.new'),
                   onclick: () => go('#/new') })));
  view.appendChild(bar);
  view.appendChild(filters);
  view.appendChild(tools);
  view.appendChild(results);

  function drawResults() {
    const books = filteredBooks();
    count.textContent = books.length + ' ' + t('search.results');
    results.textContent = '';
    if (!books.length) {
      results.appendChild(el('div', { class: 'empty', text: t('search.none') }));
      return;
    }
    const shown = books.slice(0, S.limit);
    results.appendChild(resultsTable(shown));
    results.appendChild(resultsCards(shown));
    if (books.length > S.limit) {
      results.appendChild(el('div', { style: 'text-align:center;margin-top:14px' },
        el('button', { class: 'btn', text: t('app.showmore'), onclick: () => {
          S.limit += 200; drawResults();
        } })));
    }
  }
  drawResults();
  if (window.innerWidth > 820) allInput.focus();
}

function elSvg(path) {
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('viewBox', '0 0 24 24');
  const p = document.createElementNS('http://www.w3.org/2000/svg', 'path');
  p.setAttribute('d', path);
  svg.appendChild(p);
  return svg;
}

function sortHeader(key, label) {
  const active = S.sort.key === key;
  return el('th', {
    onclick: () => {
      if (active) S.sort.dir *= -1; else { S.sort.key = key; S.sort.dir = 1; }
      render();
    }
  }, label + ' ', el('span', { class: 'arrow', text: active ? (S.sort.dir > 0 ? '▲' : '▼') : '' }));
}

function resultsTable(books, options) {
  const body = el('tbody');
  books.forEach(b => {
    const row = el('tr', { class: b.deleted ? 'deleted' : '', onclick: () => go('#/book/' + b.id) },
      el('td', { class: 'title', text: b.title }),
      el('td', { text: b._authors }),
      el('td', { text: b.publisher }),
      el('td', { class: 'loc' }, el('b', { text: b.box }), ' ', b.box_ref),
      el('td', { text: b.library }),
      el('td', { class: 'more', text: b.more }));
    body.appendChild(row);
  });
  const table = el('table', { class: 'results' },
    el('thead', {}, el('tr', {},
      sortHeader('title', t('search.title')),
      sortHeader('authors', t('search.authors')),
      sortHeader('publisher', t('search.publisher')),
      sortHeader('box', t('search.box')),
      sortHeader('library', t('search.library')),
      sortHeader('more', t('search.more')))),
    body);
  // Only where the table shares its width with something else; wrapping it on
  // the search page would turn the sticky header into a nested scroll area.
  return (options && options.scroll)
    ? el('div', { class: 'table-scroll' }, table) : table;
}

function resultsCards(books) {
  const wrap = el('div', { class: 'cards' });
  books.forEach(b => {
    wrap.appendChild(el('button', {
      class: 'book-card' + (b.deleted ? ' deleted' : ''),
      onclick: () => go('#/book/' + b.id)
    },
      el('div', { class: 'bt', text: b.title }),
      el('div', { class: 'ba', text: b._authors }),
      el('div', { class: 'bl' },
        el('span', { class: 'pin', text: b.box_ref + ' · ' + b.box }),
        el('span', { text: b.library }),
        b.publisher ? el('span', { text: '· ' + b.publisher }) : null)));
  });
  return wrap;
}

/* ------------------------------------------------------------ shelves view */

function viewShelves() {
  const view = $('#view');
  view.appendChild(el('div', { class: 'page-head' },
    el('h1', { text: t('shelves.title') }),
    el('span', { class: 'count',
                 text: S.data.libraries.length + ' ' + t('nav.libraries').toLowerCase() })));
  view.appendChild(el('p', { class: 'hint', text: t('shelves.hint') }));

  const grid = el('div', { class: 'lib-grid', style: 'margin-top:14px' });
  S.data.libraries.forEach(lib => {
    const boxes = S.data.boxes.filter(b => b.library === lib.id);
    const books = S.usage.libraries[lib.id] || 0;
    const card = el('div', { class: 'card lib-card' },
      el('h3', { text: lib.name }),
      el('div', { class: 'place', text: lib.place || '' }),
      el('div', { class: 'muted', style: 'font-size:.8rem;margin-bottom:8px',
                  text: plural(boxes.length, 'lib.box', 'lib.boxes') + ' · '
                        + plural(books, 'app.book', 'app.books') }),
      shelfSvg(lib, { onPick: box => go('#/box/' + box.id) }));
    grid.appendChild(card);
  });
  view.appendChild(grid);
}

function viewLibrary(id) {
  const lib = S.libById[id];
  if (!lib) { go('#/shelves'); return; }
  const view = $('#view');
  view.appendChild(el('div', { class: 'page-head' },
    el('a', { class: 'btn small ghost', href: '#/shelves', text: '← ' + t('shelves.title') }),
    el('h1', { text: lib.name })));
  view.appendChild(el('p', { class: 'hint', text: lib.place || '' }));
  view.appendChild(el('div', { class: 'card panel' },
    shelfSvg(lib, { onPick: box => go('#/box/' + box.id) })));
}

function viewBox(id) {
  const box = S.boxById[id];
  if (!box) { go('#/shelves'); return; }
  const lib = S.libById[box.library];
  const books = S.data.books.filter(b => b.box_id === id && (S.showDeleted || !b.deleted))
    .sort((a, b) => collator.compare(a.title, b.title));
  const view = $('#view');

  view.appendChild(el('div', { class: 'page-head' },
    el('a', { class: 'btn small ghost', href: '#/shelves', text: '← ' + t('shelves.title') }),
    el('h1', { text: box.name }),
    el('span', { class: 'count', text: plural(books.length, 'app.book', 'app.books') }),
    el('button', { class: 'btn small', text: t('app.edit'),
                   onclick: () => boxDialog(box) })));
  view.appendChild(el('p', { class: 'hint',
    text: (lib ? lib.name + ' — ' : '') + box.column + box.line + (lib && lib.place ? ' · ' + lib.place : '') }));

  // A flex row rather than the shared two-column grid: the grid's 1fr tracks
  // are min-width:auto, so the table refused to shrink and slid underneath the
  // shelf drawing, hiding the Détails column.
  view.appendChild(el('div', { class: 'box-layout' },
    el('div', { class: 'box-books' }, books.length
      ? el('div', {}, resultsTable(books, { scroll: true }), resultsCards(books))
      : el('div', { class: 'empty', text: t('box.empty') })),
    lib ? el('div', { class: 'card panel box-plan' }, shelfSvg(lib, {
      selectedBox: box, caption: true, onPick: b => go('#/box/' + b.id) })) : null));
}

/* --------------------------------------------------- authors and publishers */

function viewPeople(kind) {
  const isAuthors = kind === 'authors';
  const view = $('#view');
  const items = isAuthors ? S.data.authors : S.data.publishers;
  const usage = isAuthors ? S.usage.authors : S.usage.publishers;
  const labelOf = item => isAuthors ? item.label : item.name;
  const picked = new Set();

  const search = el('input', { type: 'search', placeholder: t('app.search'), autocomplete: 'off' });
  const mergeButton = el('button', {
    class: 'btn small', text: t('author.merge'), disabled: true,
    onclick: () => mergeDialog()
  });
  const rows = el('div', { class: 'rows' });
  const countLabel = el('span', { class: 'count' });

  view.appendChild(el('div', { class: 'page-head' },
    el('h1', { text: t(isAuthors ? 'nav.authors' : 'nav.publishers') }),
    countLabel,
    el('button', { class: 'btn small primary', text: '＋ ' + t(isAuthors ? 'author.new' : 'publisher.new'),
                   onclick: () => (isAuthors ? authorDialog : publisherDialog)(null) })));
  view.appendChild(el('div', { class: 'list-toolbar' }, search, mergeButton));
  view.appendChild(rows);

  function draw() {
    const needle = norm(search.value);
    const found = items.filter(i => !needle || norm(labelOf(i)).includes(needle));
    countLabel.textContent = found.length + ' / ' + items.length;
    rows.textContent = '';
    found.slice(0, 400).forEach(item => {
      const used = usage[item.id] || 0;
      const check = el('input', {
        type: 'checkbox', checked: picked.has(item.id),
        onchange: ev => {
          if (ev.target.checked) picked.add(item.id); else picked.delete(item.id);
          mergeButton.disabled = picked.size < 2;
          mergeButton.textContent = t('author.merge') + (picked.size ? ' (' + picked.size + ')' : '');
        }
      });
      rows.appendChild(el('div', { class: 'row' + (used ? '' : ' orphan') },
        check,
        el('div', { class: 'grow' },
          el('div', { class: 'name', text: labelOf(item) }),
          el('div', { class: 'sub', text: used ? used + ' ' + t('app.books') : t('author.orphan') })),
        used ? el('button', { class: 'btn small', text: t('app.view_books'),
          onclick: () => {
            S.filters = { all: '', title: '', authors: '', publisher: '', box: '', library: '' };
            S.filters[isAuthors ? 'authors' : 'publisher'] = labelOf(item);
            S.showFilters = true; S.limit = 200; go('#/search');
          } }) : null,
        el('button', { class: 'btn small', text: t('app.edit'),
          onclick: () => (isAuthors ? authorDialog : publisherDialog)(item) })));
    });
    if (found.length > 400) {
      rows.appendChild(el('div', { class: 'row muted',
        text: '… ' + (found.length - 400) + ' ' + t('app.of') + ' ' + found.length }));
    }
  }
  search.addEventListener('input', debounce(draw, 120));
  draw();

  function mergeDialog() {
    const chosen = items.filter(i => picked.has(i.id));
    const target = el('select', {});
    chosen.forEach(i => target.appendChild(el('option', {
      value: i.id, text: labelOf(i) + ' (' + (usage[i.id] || 0) + ')' })));
    const body = el('div', {},
      el('p', { class: 'hint', text: t('author.merge_help') }),
      el('label', { class: 'field' },
        el('span', { class: 'label', text: t('author.merge_target') }), target),
      el('p', { class: 'hint', text: t('author.merge_note') }));
    openModal({
      title: t(isAuthors ? 'author.merge_title' : 'publisher.merge_title'), body: body,
      actions: [
        { label: t('app.cancel'), run: () => closeModal() },
        { label: t('author.merge'), kind: 'primary', run: async () => {
          const keep = +target.value;
          closeModal();
          const result = await mutate({
            path: '/api/' + (isAuthors ? 'authors' : 'publishers') + '/merge',
            body: { target_id: keep, source_ids: chosen.map(i => i.id).filter(i => i !== keep) }
          });
          if (result) { picked.clear(); toast(t('author.merge_done', result.updated)); }
        } }]
    });
  }
}

/* --------------------------------------------------------- boxes, libraries */

function viewBoxes() {
  const view = $('#view');
  const search = el('input', { type: 'search', placeholder: t('app.search'), autocomplete: 'off' });
  const rows = el('div', { class: 'rows' });
  view.appendChild(el('div', { class: 'page-head' },
    el('h1', { text: t('nav.boxes') }),
    el('span', { class: 'count', text: S.data.boxes.length }),
    el('button', { class: 'btn small primary', text: '＋ ' + t('box.new'),
                   onclick: () => boxDialog(null) })));
  view.appendChild(el('div', { class: 'list-toolbar' }, search));
  view.appendChild(rows);

  function draw() {
    const needle = norm(search.value);
    rows.textContent = '';
    S.data.boxes
      .filter(b => !needle || norm(b.name + ' ' + b.library_name).includes(needle))
      .forEach(box => {
        const count = S.usage.boxes[box.id] || 0;
        rows.appendChild(el('div', { class: 'row' },
          el('div', { class: 'grow' },
            el('div', { class: 'name', text: box.name }),
            el('div', { class: 'sub', text: box.library_name + ' · ' + box.column + box.line
                          + ' · ' + plural(count, 'app.book', 'app.books') })),
          el('button', { class: 'btn small', text: t('app.view'),
                         onclick: () => go('#/box/' + box.id) }),
          el('button', { class: 'btn small ghost', text: t('app.edit'),
                         onclick: () => boxDialog(box) })));
      });
  }
  search.addEventListener('input', debounce(draw, 120));
  draw();
}

function viewLibraries() {
  const view = $('#view');
  const rows = el('div', { class: 'rows' });
  view.appendChild(el('div', { class: 'page-head' },
    el('h1', { text: t('nav.libraries') }),
    el('span', { class: 'count', text: S.data.libraries.length }),
    el('button', { class: 'btn small primary', text: '＋ ' + t('lib.new'),
                   onclick: () => libraryDialog(null) })));
  view.appendChild(rows);
  S.data.libraries.forEach(lib => {
    const boxes = S.data.boxes.filter(b => b.library === lib.id).length;
    rows.appendChild(el('div', { class: 'row' },
      el('div', { class: 'grow' },
        el('div', { class: 'name', text: lib.name }),
        el('div', { class: 'sub', text: (lib.place || '').replace(/\n/g, ' · ')
          + ' · ' + lib.lines + '×' + lib.columns + ' · '
          + plural(boxes, 'lib.box', 'lib.boxes') })),
      el('button', { class: 'btn small', text: t('app.view'),
                     onclick: () => go('#/library/' + lib.id) }),
      el('button', { class: 'btn small ghost', text: t('app.edit'),
                     onclick: () => libraryDialog(lib) })));
  });
}

/* ------------------------------------------------------------- tools view */

function viewTools() {
  const view = $('#view');
  view.appendChild(el('h1', { text: t('tools.title') }));
  view.appendChild(toolMove());
  view.appendChild(toolSwitch());
  view.appendChild(toolVolumes());
  view.appendChild(toolDuplicates());
}

function toolMove() {
  const panel = el('div', { class: 'card panel' });
  const search = el('input', { type: 'search', placeholder: t('search.placeholder'), autocomplete: 'off' });
  const rows = el('div', { class: 'rows', style: 'max-height:320px;overflow-y:auto' });
  const target = combo({
    items: S.data.boxes.map(b => ({ id: b.id, label: boxLabel(b) })),
    placeholder: t('tools.move_target')
  });
  const action = el('button', { class: 'btn primary', disabled: true, text: t('tools.move_do', 0) });

  function refreshAction() {
    action.disabled = S.selection.size === 0 || target.invalid;
    action.textContent = t('tools.move_do', S.selection.size);
  }
  target.node.addEventListener('input', () => setTimeout(refreshAction, 0));
  target.node.addEventListener('click', () => setTimeout(refreshAction, 150));

  function draw() {
    const needle = norm(search.value);
    rows.textContent = '';
    if (!needle && !S.selection.size) {
      rows.appendChild(el('div', { class: 'row muted', text: t('tools.move_help') }));
      return;
    }
    const found = S.data.books.filter(b => !b.deleted &&
      (S.selection.has(b.id) || (needle && b._all.includes(needle)))).slice(0, 150);
    found.forEach(b => {
      rows.appendChild(el('div', { class: 'row' },
        el('input', { type: 'checkbox', checked: S.selection.has(b.id),
          onchange: ev => {
            if (ev.target.checked) S.selection.add(b.id); else S.selection.delete(b.id);
            refreshAction();
          } }),
        el('div', { class: 'grow' },
          el('div', { class: 'name', text: b.title }),
          el('div', { class: 'sub', text: b._authors + ' · ' + b.box + ' ' + b.box_ref }))));
    });
    if (!found.length) rows.appendChild(el('div', { class: 'row muted', text: t('search.none') }));
  }
  search.addEventListener('input', debounce(draw, 120));
  draw();

  action.addEventListener('click', async () => {
    const result = await mutate({ path: '/api/books/move',
      body: { book_ids: Array.from(S.selection), box_id: target.value } });
    if (result) { toast(t('tools.moved', result.moved)); S.selection.clear(); go('#/tools'); render(); }
  });

  panel.appendChild(el('h2', { text: t('tools.move') }));
  panel.appendChild(el('p', { class: 'hint', text: t('tools.move_help') }));
  panel.appendChild(el('div', { class: 'list-toolbar', style: 'margin-top:10px' }, search,
    el('button', { class: 'btn small ghost', text: t('app.clear'),
      onclick: () => { S.selection.clear(); draw(); refreshAction(); } })));
  panel.appendChild(rows);
  panel.appendChild(el('div', { class: 'btn-row', style: 'margin-top:12px' },
    el('div', { style: 'flex:1;min-width:200px' }, target.node), action));
  return panel;
}

function toolSwitch() {
  const panel = el('div', { class: 'card panel' });
  const items = S.data.boxes.map(b => ({ id: b.id, label: boxLabel(b) }));
  const from = combo({ items: items, placeholder: t('tools.switch_from') });
  const to = combo({ items: items, placeholder: t('tools.switch_to') });
  const action = el('button', { class: 'btn primary', text: t('tools.switch_do'),
    onclick: () => {
      if (from.invalid || to.invalid) { toast(t('app.error'), 'error'); return; }
      if (from.value === to.value) { toast(t('app.error'), 'error'); return; }
      const count = S.usage.boxes[from.value] || 0;
      confirmDialog(t('tools.switch'),
        t('tools.switch_confirm', count, S.boxById[from.value].name, S.boxById[to.value].name),
        t('tools.switch_do'), async () => {
          const result = await mutate({ path: '/api/boxes/switch',
            body: { from_box_id: from.value, to_box_id: to.value } });
          if (result) toast(t('tools.moved', result.moved));
        });
    } });

  panel.appendChild(el('h2', { text: t('tools.switch') }));
  panel.appendChild(el('p', { class: 'hint', text: t('tools.switch_help') }));
  panel.appendChild(el('div', { class: 'grid-2', style: 'margin-top:10px' },
    el('label', { class: 'field' }, el('span', { class: 'label', text: t('tools.switch_from') }), from.node),
    el('label', { class: 'field' }, el('span', { class: 'label', text: t('tools.switch_to') }), to.node)));
  panel.appendChild(action);
  return panel;
}

function toolVolumes() {
  const panel = el('div', { class: 'card panel' });
  panel.appendChild(el('h2', { text: t('tools.volumes') }));
  panel.appendChild(el('p', { class: 'hint', text: t('tools.volumes_help') }));
  const slot = el('div', { style: 'margin-top:10px' },
    el('div', { class: 'loading' }, el('span', { class: 'spinner' })));
  panel.appendChild(slot);

  api('/api/stats').then(stats => {
    slot.textContent = '';
    const pending = stats.unresolved_volumes || [];
    if (!pending.length) {
      slot.appendChild(el('p', { class: 'muted', text: t('tools.volumes_none') }));
      return;
    }
    const rows = el('div', { class: 'rows' });
    pending.forEach(entry => {
      const input = el('input', { type: 'number', min: '1', value: '1',
                                  style: 'width:80px' });
      rows.appendChild(el('div', { class: 'row' },
        el('div', { class: 'grow' },
          el('div', { class: 'name', text: entry.title }),
          el('div', { class: 'sub', text: entry.text || '—' })),
        input,
        el('button', { class: 'btn small primary', text: t('tools.volumes_save'),
          onclick: async ev => {
            const row = ev.target.closest('.row');
            try {
              await api('/api/volumes/resolve', { method: 'POST',
                body: { book_ids: [entry.id], count: +input.value,
                        text: entry.text } });
              row.remove();
              await loadCatalog();
              refreshSync();
              toast(t('app.saved'));
            } catch (err) { toast(err.message, 'error'); }
          } })));
    });
    slot.appendChild(rows);
  }).catch(err => { slot.textContent = ''; slot.appendChild(
    el('p', { class: 'muted', text: err.message })); });
  return panel;
}

function toolDuplicates() {
  const panel = el('div', { class: 'card panel' });
  panel.appendChild(el('h2', { text: t('tools.duplicates') }));
  panel.appendChild(el('p', { class: 'hint', text: t('tools.duplicates_help') }));

  const groups = {};
  S.data.books.filter(b => !b.deleted).forEach(b => {
    const key = b._nt + '|' + b._na;
    (groups[key] = groups[key] || []).push(b);
  });
  const dupes = Object.values(groups).filter(g => g.length > 1)
    .sort((a, b) => collator.compare(a[0].title, b[0].title));

  if (!dupes.length) {
    panel.appendChild(el('p', { class: 'muted', text: t('tools.duplicates_none') }));
    return panel;
  }
  const rows = el('div', { class: 'rows', style: 'margin-top:10px' });
  dupes.forEach(group => {
    rows.appendChild(el('div', { class: 'row' },
      el('div', { class: 'grow' },
        el('div', { class: 'name', text: group[0].title }),
        el('div', { class: 'sub', text: group[0]._authors + ' — '
          + group.map(b => b.box + ' ' + b.box_ref).join(' · ') })),
      el('span', { class: 'badge warn', text: '×' + group.length }),
      el('button', { class: 'btn small', text: t('search.more'),
        onclick: () => go('#/book/' + group[0].id) })));
  });
  panel.appendChild(rows);
  return panel;
}

/* ------------------------------------------------------------- trash view */

function viewTrash() {
  const view = $('#view');
  const deleted = S.data.books.filter(b => b.deleted)
    .sort((a, b) => collator.compare(a.title, b.title));
  view.appendChild(el('div', { class: 'page-head' },
    el('h1', { text: t('trash.title') }),
    el('span', { class: 'count', text: deleted.length })));
  view.appendChild(el('p', { class: 'hint', text: t('trash.help') }));
  if (!deleted.length) {
    view.appendChild(el('div', { class: 'empty', text: t('trash.empty') }));
    return;
  }
  const rows = el('div', { class: 'rows', style: 'margin-top:12px' });
  deleted.forEach(b => {
    rows.appendChild(el('div', { class: 'row' },
      el('div', { class: 'grow' },
        el('div', { class: 'name', text: b.title, style: 'text-decoration:line-through' }),
        el('div', { class: 'sub', text: b._authors + ' · ' + b.box + ' ' + b.box_ref })),
      el('button', { class: 'btn small', text: t('search.more'), onclick: () => go('#/book/' + b.id) }),
      el('button', { class: 'btn small primary', text: t('app.restore'),
        onclick: () => mutate({ path: '/api/books/' + b.id + '/restore' }, t('book.restored')) })));
  });
  view.appendChild(rows);
}

/* ----------------------------------------------------------- history view */

function viewHistory() {
  const view = $('#view');
  view.appendChild(el('h1', { text: t('history.title') }));
  view.appendChild(el('p', { class: 'hint', text: t('history.help') }));
  const slot = el('div', { style: 'margin-top:12px' },
    el('div', { class: 'loading' }, el('span', { class: 'spinner' })));
  view.appendChild(slot);

  api('/api/history?limit=200').then(found => {
    slot.textContent = '';
    if (!found.entries.length) {
      slot.appendChild(el('div', { class: 'empty', text: t('history.empty') }));
      return;
    }
    const rows = el('div', { class: 'rows' });
    found.entries.forEach(entry => {
      let label = entry.name || [entry.christian_name, entry.last_name].filter(Boolean).join(' ') || '—';
      const sub = [];
      if (entry.table === 'books') {
        const box = S.boxById[entry.box];
        sub.push((S.pubById[entry.publisher] || {}).name || '');
        if (box) sub.push(box.name);
        if (entry.more) sub.push(entry.more);
      } else if (entry.table === 'boxes') {
        sub.push((S.libById[entry.library] || {}).name || '');
        sub.push(String(entry.column || '') + (entry.line || ''));
      } else if (entry.table === 'libraries') {
        sub.push(entry.place || '');
      }
      rows.appendChild(el('div', { class: 'row' },
        el('span', { class: 'badge', text: t('history.table.' + entry.table) }),
        el('div', { class: 'grow' },
          el('div', { class: 'name', text: label }),
          el('div', { class: 'sub', text: sub.filter(Boolean).join(' · ') })),
        entry.table === 'books' && S.byId[entry.id]
          ? el('button', { class: 'btn small ghost', text: t('app.view'),
              onclick: () => go('#/book/' + entry.id) }) : null));
    });
    slot.appendChild(rows);
  }).catch(err => { slot.textContent = ''; slot.appendChild(
    el('div', { class: 'empty', text: err.message })); });
}

/* ------------------------------------------------------------- stats view */

function viewStats() {
  const view = $('#view');
  view.appendChild(el('h1', { text: t('stats.title') }));
  const slot = el('div', {}, el('div', { class: 'loading' }, el('span', { class: 'spinner' })));
  view.appendChild(slot);

  api('/api/stats').then(stats => {
    slot.textContent = '';
    const tiles = el('div', { class: 'tiles' });
    [['stats.books', stats.totals.books], ['stats.volumes', stats.totals.volumes],
     ['stats.authors', stats.totals.authors], ['stats.publishers', stats.totals.publishers],
     ['stats.boxes', stats.totals.boxes], ['stats.libraries', stats.totals.libraries],
     ['stats.deleted', stats.totals.deleted]
    ].forEach(([key, value]) => {
      tiles.appendChild(el('div', { class: 'card tile' },
        el('div', { class: 'n', text: value.toLocaleString(LANG) }),
        el('div', { class: 'l', text: t(key) })));
    });
    slot.appendChild(tiles);

    if ((stats.unresolved_volumes || []).length) {
      slot.appendChild(el('p', { class: 'hint' },
        t('stats.volumes_hint', stats.unresolved_volumes.length) + ' ',
        el('a', { href: '#/tools', style: 'text-decoration:underline', text: t('tools.title') })));
    }

    const chart = (title, data) => {
      const max = Math.max(1, ...data.map(d => d.count));
      const bars = el('div', { class: 'bars' });
      data.forEach(d => bars.appendChild(el('div', { class: 'bar' },
        el('div', { class: 'bn', text: d.name, title: d.name }),
        el('div', { class: 'bt' }, el('div', { class: 'bf',
          style: 'width:' + (100 * d.count / max) + '%' })),
        el('div', { class: 'bv', text: d.count }))));
      return el('div', { class: 'card panel' }, el('h2', { text: title }), bars);
    };
    slot.appendChild(el('div', { class: 'cols-2' },
      chart(t('stats.by_library'), stats.by_library),
      chart(t('stats.by_box'), stats.by_box),
      chart(t('stats.by_author'), stats.by_author),
      chart(t('stats.by_publisher'), stats.by_publisher)));
  }).catch(err => { slot.textContent = ''; slot.appendChild(
    el('div', { class: 'empty', text: err.message })); });
}

/* ------------------------------------------------------------ export view */

function viewExport() {
  const view = $('#view');
  const libSelect = el('select', {}, el('option', { value: 'all', text: t('export.all') }));
  S.data.libraries.forEach(l => libSelect.appendChild(
    el('option', { value: l.id, text: l.name })));
  const formatSelect = el('select', {},
    el('option', { value: 'txt', text: t('export.txt') }),
    el('option', { value: 'csv', text: t('export.csv') }),
    el('option', { value: 'json', text: t('export.json') }));
  const withDeleted = el('input', { type: 'checkbox' });
  const preview = el('pre', { class: 'card panel',
    style: 'max-height:420px;overflow:auto;white-space:pre-wrap;font-size:.82rem' });

  const url = () => '/api/export?library=' + libSelect.value
    + '&format=' + formatSelect.value + (withDeleted.checked ? '&deleted=1' : '');

  view.appendChild(el('h1', { text: t('export.title') }));
  view.appendChild(el('p', { class: 'hint', text: t('export.help') }));
  view.appendChild(el('div', { class: 'card panel', style: 'margin-top:12px' },
    el('div', { class: 'grid-2' },
      el('label', { class: 'field' }, el('span', { class: 'label', text: t('export.library') }), libSelect),
      el('label', { class: 'field' }, el('span', { class: 'label', text: t('export.format') }), formatSelect)),
    el('div', { class: 'checkrow' }, el('label', {}, withDeleted, t('export.deleted'))),
    el('div', { class: 'btn-row' },
      el('a', { class: 'btn primary', href: url(), text: '↧ ' + t('export.download'),
                id: 'export-dl', download: '' }),
      el('button', { class: 'btn', text: t('export.preview'), onclick: async () => {
        preview.textContent = '…';
        try {
          const response = await fetch(url());
          preview.textContent = (await response.text()).slice(0, 40000);
        } catch (err) { preview.textContent = err.message; }
      } }))));
  view.appendChild(preview);

  const sync = () => { $('#export-dl').href = url(); };
  libSelect.addEventListener('change', sync);
  formatSelect.addEventListener('change', sync);
  withDeleted.addEventListener('change', sync);
}

/* ------------------------------------------------------------------- chrome */

function openNav() {
  $('#sidenav').classList.add('open');
  $('#scrim').hidden = false;
  $('#nav-toggle').setAttribute('aria-expanded', 'true');
}
function closeNav() {
  $('#sidenav').classList.remove('open');
  $('#scrim').hidden = true;
  $('#nav-toggle').setAttribute('aria-expanded', 'false');
}

function wireChrome() {
  $('#nav-toggle').addEventListener('click', () =>
    $('#sidenav').classList.contains('open') ? closeNav() : openNav());
  $('#more-btn').addEventListener('click', openNav);
  $('#scrim').addEventListener('click', closeNav);
  $('#sync-chip').addEventListener('click', syncNow);

  $('#lang-btn').addEventListener('click', () => {
    LANG = LANG === 'fr' ? 'en' : 'fr';
    localStorage.setItem('homelib.lang', LANG);
    applyStaticI18n();
    indexCatalog(S.data);   // the anonymous/collective labels are translated
    render();
  });

  $('#theme-btn').addEventListener('click', () => {
    const order = ['', 'light', 'dark'];
    const next = order[(order.indexOf(currentTheme()) + 1) % order.length];
    if (next) localStorage.setItem('homelib.theme', next);
    else localStorage.removeItem('homelib.theme');
    applyTheme(next);
  });

  window.addEventListener('hashchange', render);

  document.addEventListener('keydown', ev => {
    if (ev.key === 'Escape' && !$('#modal-root').hidden) { closeModal(); return; }
    if (ev.key === 'Escape') { closeNav(); return; }
    const typing = /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement.tagName);
    if (typing) return;
    // The Qt window used Ctrl+N for a new book; keep the habit.
    if ((ev.ctrlKey || ev.metaKey) && ev.key.toLowerCase() === 'n') {
      ev.preventDefault(); go('#/new');
    } else if (ev.key === '/') {
      ev.preventDefault();
      go('#/search');
      setTimeout(() => { const i = $('.searchbar input'); if (i) i.focus(); }, 30);
    }
  });

  window.addEventListener('online', () => { loadCatalog().then(render); });
  window.addEventListener('offline', () => { S.offline = true; render(); });
}

/* --------------------------------------------------------------------- boot */

async function boot() {
  applyTheme(currentTheme());
  applyStaticI18n();
  wireChrome();

  try {
    await loadCatalog();
  } catch (err) {
    $('#view').textContent = '';
    $('#view').appendChild(el('div', { class: 'empty' },
      el('p', { text: t('app.error') + ' : ' + err.message }),
      el('button', { class: 'btn', text: t('app.retry'), onclick: () => location.reload() })));
    return;
  }
  if (!location.hash) location.hash = '#/search';
  render();
  refreshSync();
  syncTimer = setInterval(refreshSync, 60000);

  // The offline copy above works over plain http; a service worker needs a
  // secure context, so this quietly does nothing until the site is on https.
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/sw.js').catch(() => {});
  }
}

document.addEventListener('DOMContentLoaded', boot);
})();
