/* Le Relevé : sources des chiffres, infobulles, curseur des courbes, tri des tableaux. */
(function () {
  var nf = new Intl.NumberFormat('fr-FR');

  // Fiche source au survol ou au focus d'un chiffre
  var pop = null;
  function showFact(a) {
    hideFact();
    pop = document.createElement('div');
    pop.className = 'fact-pop';
    pop.setAttribute('role', 'tooltip');
    var b = document.createElement('b'); b.textContent = a.dataset.fact;
    var s = document.createElement('span'); s.textContent = 'Source : ' + a.dataset.where;
    pop.appendChild(b); pop.appendChild(s);
    document.body.appendChild(pop);
    var r = a.getBoundingClientRect();
    var left = Math.min(Math.max(8, r.left + window.scrollX), window.scrollX + document.documentElement.clientWidth - pop.offsetWidth - 8);
    pop.style.left = left + 'px';
    pop.style.top = (r.top + window.scrollY - pop.offsetHeight - 8) + 'px';
    a.classList.add('on');
  }
  function hideFact() {
    if (pop) { pop.remove(); pop = null; }
    document.querySelectorAll('a.fait.on').forEach(function (x) { x.classList.remove('on'); });
  }
  document.querySelectorAll('a.fait').forEach(function (a) {
    a.addEventListener('mouseenter', function () { showFact(a); });
    a.addEventListener('focus', function () { showFact(a); });
    a.addEventListener('mouseleave', hideFact);
    a.addEventListener('blur', hideFact);
  });

  // Infobulle des barres
  var tip = null;
  document.querySelectorAll('[data-tip]').forEach(function (el) {
    el.addEventListener('mousemove', function (e) {
      if (!tip) { tip = document.createElement('div'); tip.className = 'chart-tip'; document.body.appendChild(tip); }
      tip.textContent = el.dataset.tip;
      tip.style.left = e.clientX + 'px'; tip.style.top = e.clientY + 'px';
    });
    el.addEventListener('mouseleave', function () { if (tip) { tip.remove(); tip = null; } });
  });

  // Curseur des courbes
  var df = new Intl.DateTimeFormat('fr-FR', { weekday: 'short', day: 'numeric', month: 'numeric', hour: 'numeric', minute: '2-digit', timeZone: 'Europe/Paris' });
  document.querySelectorAll('.line-plot').forEach(function (plot) {
    var pts = JSON.parse(plot.dataset.points), unit = plot.dataset.unit;
    var t0 = pts[0][0], t1 = pts[pts.length - 1][0];
    var ch = plot.querySelector('.crosshair'), tp = ch.querySelector('.tip');
    function move(clientX) {
      var r = plot.getBoundingClientRect();
      var x = Math.min(Math.max(0, clientX - r.left), r.width);
      var t = t0 + (t1 - t0) * x / r.width, best = pts[0];
      for (var i = 1; i < pts.length; i++) if (Math.abs(pts[i][0] - t) < Math.abs(best[0] - t)) best = pts[i];
      ch.hidden = false;
      ch.style.left = ((best[0] - t0) / (t1 - t0) * 100) + '%';
      tp.textContent = df.format(new Date(best[0] * 1000)) + ' : ' + nf.format(best[1]) + ' ' + unit;
    }
    plot.addEventListener('mousemove', function (e) { move(e.clientX); });
    plot.addEventListener('touchmove', function (e) { move(e.touches[0].clientX); }, { passive: true });
    plot.addEventListener('mouseleave', function () { ch.hidden = true; });
  });

  // Tri des tableaux
  document.querySelectorAll('table.sortable').forEach(function (table) {
    var ths = table.querySelectorAll('th');
    ths.forEach(function (th, idx) {
      if (!th.dataset.sort) return;
      var btn = document.createElement('button');
      btn.type = 'button'; btn.textContent = th.textContent; th.textContent = ''; th.appendChild(btn);
      btn.addEventListener('click', function () {
        var dir = th.getAttribute('aria-sort') === 'descending' ? 'ascending' : 'descending';
        ths.forEach(function (o) { o.removeAttribute('aria-sort'); });
        th.setAttribute('aria-sort', dir);
        var body = table.tBodies[0], rows = Array.prototype.slice.call(body.rows);
        rows.sort(function (a, b) {
          var va = +(a.cells[idx].dataset.v || a.cells[idx].textContent.replace(/\D/g, ''));
          var vb = +(b.cells[idx].dataset.v || b.cells[idx].textContent.replace(/\D/g, ''));
          return dir === 'descending' ? vb - va : va - vb;
        });
        rows.forEach(function (r) { body.appendChild(r); });
      });
    });
  });
})();

/* Comparateur de deux jeux */
(function () {
  var form = document.getElementById('compare');
  if (!form) return;
  var fig = document.getElementById('compare-chart'), api = fig.dataset.api;
  var plot = document.getElementById('compare-plot'), legend = document.getElementById('compare-legend');
  var title = document.getElementById('compare-title'), stats = document.getElementById('compare-stats');
  var nf = new Intl.NumberFormat('fr-FR'), cache = {};
  var q = new URLSearchParams(location.search);
  var a = form.elements.a, b = form.elements.b;
  a.value = q.get('a') || form.dataset.a || a.value;
  b.value = q.get('b') || (form.dataset.b !== a.value ? form.dataset.b : form.dataset.a) || b.value;
  function get(id) { return cache[id] ? Promise.resolve(cache[id]) : fetch(api + id + '.json').then(function (r) { return r.json(); }).then(function (d) { cache[id] = d; return d; }); }
  function esc(s) { var d = document.createElement('div'); d.textContent = s; return d.innerHTML; }
  function draw(ga, gb) {
    var series = [ga, gb], all = [];
    series.forEach(function (g) { g.serie.forEach(function (p) { all.push([Date.parse(p[0]), p[1]]); }); });
    var t0 = Math.min.apply(null, all.map(function (p) { return p[0]; })), t1 = Math.max.apply(null, all.map(function (p) { return p[0]; }));
    var vmax = Math.max.apply(null, all.map(function (p) { return p[1]; })) || 1;
    var mag = Math.pow(10, Math.floor(Math.log10(vmax))), top = Math.ceil(vmax / mag) * mag;
    var W = 1000, H = 300, span = (t1 - t0) || 1, svg = '';
    series.forEach(function (g, i) {
      var d = '', prev = null;
      g.serie.forEach(function (p) {
        var t = Date.parse(p[0]), x = (t - t0) / span * W, y = H - p[1] / top * H;
        d += (prev && t - prev <= 3 * 3600e3 ? ' L' : ' M') + x.toFixed(1) + ',' + y.toFixed(1); prev = t;
      });
      svg += '<path class="s' + (i + 1) + '" d="' + d + '" vector-effect="non-scaling-stroke"/>';
    });
    var grid = '';
    for (var k = 0; k <= 4; k++) { var v = top * k / 4; grid += '<div class="ytick" style="bottom:' + (k * 25) + '%"><span>' + (v >= 1e6 ? (v / 1e6).toLocaleString('fr-FR') + ' M' : v >= 1e3 ? Math.round(v / 1e3) + ' k' : v) + '</span></div>'; }
    plot.innerHTML = grid + '<svg viewBox="0 0 ' + W + ' ' + H + '" preserveAspectRatio="none" aria-hidden="true">' + svg + '</svg>';
    var dfx = new Intl.DateTimeFormat('fr-FR', { day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit', timeZone: 'Europe/Paris' });
    document.getElementById('compare-x').innerHTML = '<span>' + dfx.format(new Date(t0)) + '</span><span>' + dfx.format(new Date(t1)) + '</span>';
    legend.innerHTML = series.map(function (g, i) { return '<li><i class="s' + (i + 1) + '"></i>' + esc(g.nom) + '</li>'; }).join('');
    title.textContent = ga.nom + ' face à ' + gb.nom;
    stats.innerHTML = series.map(function (g, i) {
      return '<div class="stat c' + (i + 1) + '"><span class="stat-label">' + esc(g.nom) + '</span><span class="stat-value">' + nf.format(g.joueurs) +
        '</span><span class="stat-note">joueurs au dernier relevé, pic sur 24 h : ' + (g.pic_24h != null ? nf.format(g.pic_24h) : '—') + '</span></div>';
    }).join('');
  }
  function update() {
    var p = new URLSearchParams({ a: a.value, b: b.value });
    history.replaceState(null, '', '?' + p.toString());
    title.textContent = 'Chargement…';
    Promise.all([get(a.value), get(b.value)]).then(function (r) { draw(r[0], r[1]); })
      .catch(function () { title.textContent = 'Données indisponibles pour ce jeu. Choisissez-en un autre.'; });
  }
  a.addEventListener('change', update); b.addEventListener('change', update);
  update();
})();

/* Lignes cliquables, copie de liens, notifications */
(function () {
  document.querySelectorAll('tr[data-href]').forEach(function (tr) {
    tr.addEventListener('click', function (e) { if (e.target.closest('a,button')) return; location.href = tr.dataset.href; });
  });
  var toast = document.getElementById('toast');
  function notify(msg) {
    if (!toast) return;
    toast.textContent = msg; toast.classList.add('show');
    clearTimeout(notify.t); notify.t = setTimeout(function () { toast.classList.remove('show'); }, 2200);
  }
  function copy(text, ok) {
    var done = function () { notify(ok); };
    if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(text).then(done, function () { fallback(text); done(); });
    else { fallback(text); done(); }
  }
  function fallback(text) {
    var ta = document.createElement('textarea'); ta.value = text; ta.style.position = 'fixed'; ta.style.opacity = '0';
    document.body.appendChild(ta); ta.select(); try { document.execCommand('copy'); } catch (e) {} ta.remove();
  }
  var share = document.getElementById('share-btn');
  if (share) share.addEventListener('click', function () {
    var data = { title: document.title, url: location.href };
    if (navigator.share && matchMedia('(pointer: coarse)').matches) navigator.share(data).catch(function () {});
    else copy(location.href, 'Lien copié dans le presse-papier !');
  });
  document.querySelectorAll('[data-copy]').forEach(function (b) { b.addEventListener('click', function () { copy(b.dataset.copy, b.dataset.copyMsg || 'Adresse copiée !'); }); });
  document.querySelectorAll('[data-copy-from]').forEach(function (b) {
    b.addEventListener('click', function () { copy(document.getElementById(b.dataset.copyFrom).textContent, 'Code copié !'); });
  });
})();

/* Filtres par genre, partage X, état des relevés */
(function () {
  document.querySelectorAll('.filters').forEach(function (bar) {
    var table = bar.nextElementSibling && bar.nextElementSibling.querySelector('table');
    if (!table) return;
    bar.addEventListener('click', function (e) {
      var b = e.target.closest('[data-filter]'); if (!b) return;
      bar.querySelectorAll('.chip').forEach(function (c) { c.classList.toggle('on', c === b); c.setAttribute('aria-pressed', c === b); });
      var g = b.dataset.filter;
      table.querySelectorAll('tbody tr').forEach(function (tr) { tr.hidden = !!g && tr.dataset.genre !== g; });
    });
  });
  var xs = document.getElementById('x-share'), cp = document.getElementById('copy-btn');
  function names() {
    var f = document.getElementById('compare'); if (!f) return ['', ''];
    return [f.elements.a.selectedOptions[0].text, f.elements.b.selectedOptions[0].text];
  }
  function refreshX() {
    if (!xs) return;
    var n = names();
    var text = n[0] + ' face à ' + n[1] + ' : joueurs en ligne, heure par heure, sur Le Relevé 📊';
    xs.href = 'https://twitter.com/intent/tweet?text=' + encodeURIComponent(text) + '&url=' + encodeURIComponent(location.href);
  }
  if (xs) { refreshX(); document.getElementById('compare').addEventListener('change', function () { setTimeout(refreshX, 50); }); xs.addEventListener('focus', refreshX); xs.addEventListener('mouseenter', refreshX); }
  if (cp) cp.addEventListener('click', function () {
    var t = document.getElementById('toast');
    var done = function () { if (t) { t.textContent = 'Lien copié dans le presse-papier !'; t.classList.add('show'); setTimeout(function () { t.classList.remove('show'); }, 2200); } };
    if (navigator.clipboard) navigator.clipboard.writeText(location.href).then(done, done); else done();
  });
  var fs = document.querySelector('.feed-status');
  if (fs) {
    var last = Date.parse(fs.dataset.last), next = fs.querySelector('.fs-next');
    var tick = function () {
      var m = Math.round((last + 3600e3 - Date.now()) / 60000);
      next.innerHTML = ' <span class="sep">•</span> ' + (m > 0 ? 'Prochain relevé dans ' + m + ' min' : 'Prochain relevé imminent');
    };
    tick(); setInterval(tick, 30000);
  }
})();

/* Recherche de jeux */
(function () {
  var box = document.querySelector('.search'); if (!box) return;
  var input = box.querySelector('input'), list = box.querySelector('.search-res'), data = null, sel = -1;
  function norm(s) { return s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase(); }
  function load() { if (data) return Promise.resolve(data); return fetch(box.dataset.index).then(function (r) { return r.json(); }).then(function (d) { data = d.jeux; return data; }); }
  function render(q) {
    if (!q) { list.hidden = true; return; }
    var n = norm(q), res = data.filter(function (g) { return norm(g.nom).indexOf(n) >= 0; }).slice(0, 8);
    list.innerHTML = res.length ? res.map(function (g, i) {
      var a = document.createElement('a'); a.href = box.dataset.base + g.slug + '/'; a.textContent = g.nom;
      return '<li' + (i === sel ? ' class="on"' : '') + '>' + a.outerHTML + '<span>' + (g.rang ? g.rang + 'e' : '') + '</span></li>';
    }).join('') : '<li class="none">Aucun jeu suivi ne correspond</li>';
    list.hidden = false;
  }
  input.addEventListener('focus', load);
  input.addEventListener('input', function () { sel = -1; load().then(function () { render(input.value.trim()); }); });
  input.addEventListener('keydown', function (e) {
    var items = list.querySelectorAll('li a');
    if (e.key === 'ArrowDown') { sel = Math.min(sel + 1, items.length - 1); render(input.value.trim()); e.preventDefault(); }
    else if (e.key === 'ArrowUp') { sel = Math.max(sel - 1, 0); render(input.value.trim()); e.preventDefault(); }
    else if (e.key === 'Enter') { var t = items[sel >= 0 ? sel : 0]; if (t) location.href = t.href; }
    else if (e.key === 'Escape') { list.hidden = true; }
  });
  document.addEventListener('click', function (e) { if (!box.contains(e.target)) list.hidden = true; });
})();

(function () {
  var btn = document.querySelector('.menu-btn'), head = document.querySelector('.site-head');
  if (!btn || !head) return;
  function set(open) {
    head.classList.toggle('open', open); document.body.classList.toggle('menu-open', open);
    btn.setAttribute('aria-expanded', open ? 'true' : 'false');
    btn.setAttribute('aria-label', open ? 'Fermer le menu' : 'Ouvrir le menu');
  }
  btn.addEventListener('click', function () { set(!head.classList.contains('open')); });
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape' && head.classList.contains('open')) { set(false); btn.focus(); } });
  matchMedia('(min-width: 761px)').addEventListener('change', function (m) { if (m.matches) set(false); });
})();
(function () {
  var h = document.querySelector('.site-head');
  if (!h) return;
  function upd() { document.documentElement.style.setProperty('--head-h', h.offsetHeight + 'px'); }
  upd(); addEventListener('resize', upd);
})();
