/* Langue de la page : traductions de l'interface et formats (le français est la langue source). */
var LR = (function () {
  var l = (document.documentElement.lang || 'fr').toLowerCase(), k = l.indexOf('pt') === 0 ? 'pt' : l.slice(0, 2);
  var D = {"en": {"Source : ": "Source: ", "24 h": "24h", "7 j": "7d", "30 j": "30d", "Tout": "All", "Pic ": "Peak ", "Creux ": "Low ", "sur la période": "over the period", "Période": "Period", " face à ": " vs ", "joueurs au dernier relevé, pic sur 24 h : ": "players at the latest reading, 24h peak: ", "Données indisponibles pour ce jeu. Choisissez-en un autre.": "No data for this game. Pick another one.", "Lien copié dans le presse-papier !": "Link copied to clipboard!", "Adresse copiée !": "Address copied!", "Code copié !": "Code copied!", " : joueurs en ligne, heure par heure, sur Le Relevé 📊": ": players online, hour by hour, on Le Relevé 📊", "Prochain relevé dans ": "Next reading in ", "Prochain relevé imminent": "Next reading imminent", "Aucun jeu suivi ne correspond": "No tracked game matches", "Fermer le menu": "Close menu", "Ouvrir le menu": "Open menu"}, "es": {"Source : ": "Fuente: ", "24 h": "24 h", "7 j": "7 d", "30 j": "30 d", "Tout": "Todo", "Pic ": "Pico ", "Creux ": "Mínimo ", "sur la période": "en el periodo", "Période": "Periodo", " face à ": " frente a ", "joueurs au dernier relevé, pic sur 24 h : ": "jugadores en la última medición, pico en 24 h: ", "Données indisponibles pour ce jeu. Choisissez-en un autre.": "No hay datos para este juego. Elige otro.", "Lien copié dans le presse-papier !": "¡Enlace copiado al portapapeles!", "Adresse copiée !": "¡Dirección copiada!", "Code copié !": "¡Código copiado!", " : joueurs en ligne, heure par heure, sur Le Relevé 📊": ": jugadores en línea, hora a hora, en Le Relevé 📊", "Prochain relevé dans ": "Próxima medición en ", "Prochain relevé imminent": "Próxima medición inminente", "Aucun jeu suivi ne correspond": "Ningún juego seguido coincide", "Fermer le menu": "Cerrar el menú", "Ouvrir le menu": "Abrir el menú"}, "pt": {"Source : ": "Fonte: ", "24 h": "24 h", "7 j": "7 d", "30 j": "30 d", "Tout": "Tudo", "Pic ": "Pico ", "Creux ": "Mínimo ", "sur la période": "no período", "Période": "Período", " face à ": " contra ", "joueurs au dernier relevé, pic sur 24 h : ": "jogadores na última medição, pico em 24 h: ", "Données indisponibles pour ce jeu. Choisissez-en un autre.": "Sem dados para este jogo. Escolha outro.", "Lien copié dans le presse-papier !": "Link copiado para a área de transferência!", "Adresse copiée !": "Endereço copiado!", "Code copié !": "Código copiado!", " : joueurs en ligne, heure par heure, sur Le Relevé 📊": ": jogadores online, hora a hora, no Le Relevé 📊", "Prochain relevé dans ": "Próxima medição em ", "Prochain relevé imminent": "Próxima medição iminente", "Aucun jeu suivi ne correspond": "Nenhum jogo acompanhado corresponde", "Fermer le menu": "Fechar o menu", "Ouvrir le menu": "Abrir o menu"}};
  var loc = { fr: 'fr-FR', en: 'en-US', es: 'es-ES', pt: 'pt-BR' }[k] || 'fr-FR';
  function ord(n) { if (k === 'fr') return n + 'e'; if (k === 'en') { var m = n % 100; return n + ((m > 10 && m < 14) ? 'th' : ({ 1: 'st', 2: 'nd', 3: 'rd' }[n % 10] || 'th')); } return n + 'º'; }
  return { k: k, loc: loc, t: function (s) { return (D[k] && D[k][s]) || s; }, ord: ord };
})();

/* Le Relevé : sources des chiffres, infobulles, curseur des courbes, tri des tableaux. */
(function () {
  var nf = new Intl.NumberFormat(LR.loc);

  // Fiche source au survol ou au focus d'un chiffre
  var pop = null;
  function showFact(a) {
    hideFact();
    pop = document.createElement('div');
    pop.className = 'fact-pop';
    pop.setAttribute('role', 'tooltip');
    var b = document.createElement('b'); b.textContent = a.dataset.fact;
    var s = document.createElement('span'); s.textContent = LR.t('Source : ') + a.dataset.where;
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

  // Courbes : rendu interactif (périodes, pic, curseur)
  var df = new Intl.DateTimeFormat(LR.loc, { weekday: 'short', day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit', timeZone: 'Europe/Paris' });
  var dHour = new Intl.DateTimeFormat(LR.loc, { hour: 'numeric', timeZone: 'Europe/Paris' });
  var dDay = new Intl.DateTimeFormat(LR.loc, { day: 'numeric', month: 'numeric', timeZone: 'Europe/Paris' });
  var pf = new Intl.NumberFormat(LR.loc, { maximumFractionDigits: 1, signDisplay: 'always' });
  function compactN(n) {
    var a = Math.abs(n);
    if (a >= 1e6) return (n / 1e6).toLocaleString(LR.loc, { maximumFractionDigits: 1 }) + ' M';
    if (a >= 1e3) return Math.round(n / 1e3).toLocaleString(LR.loc) + ' k';
    return nf.format(n);
  }
  function niceRange(vmin, vmax, n) {
    if (vmax <= vmin) { var e = Math.max(1, Math.abs(vmax) * .05); vmax += e; vmin = Math.max(0, vmin - e); }
    var pad = (vmax - vmin) * .12, lo = Math.max(0, vmin - pad), hi = vmax + pad, raw = (hi - lo) / n;
    var mag = Math.pow(10, Math.floor(Math.log10(Math.max(raw, 1)))), step = mag;
    var ms = [1, 2, 2.5, 5, 10];
    for (var i = 0; i < ms.length; i++) { step = ms[i] * mag; if (step >= raw) break; }
    lo = step * Math.floor(lo / step); hi = step * Math.ceil(hi / step);
    var out = []; for (var v = lo; v <= hi + step / 2; v += step) out.push(v);
    return out;
  }
  function smooth(p) {
    var n = p.length, i;
    if (n < 3) return 'M' + p.map(function (q) { return q[0].toFixed(1) + ',' + q[1].toFixed(1); }).join(' L');
    var dx = [], sl = [], m = [];
    for (i = 0; i < n - 1; i++) { dx.push(p[i + 1][0] - p[i][0] || 1e-6); sl.push((p[i + 1][1] - p[i][1]) / dx[i]); }
    m.push(sl[0]);
    for (i = 1; i < n - 1; i++) m.push(sl[i - 1] * sl[i] <= 0 ? 0 : (sl[i - 1] + sl[i]) / 2);
    m.push(sl[n - 2]);
    for (i = 0; i < n - 1; i++) {
      if (sl[i] === 0) { m[i] = m[i + 1] = 0; continue; }
      var a = m[i] / sl[i], b = m[i + 1] / sl[i], h = a * a + b * b;
      if (h > 9) { var t = 3 / Math.sqrt(h); m[i] = t * a * sl[i]; m[i + 1] = t * b * sl[i]; }
    }
    var d = 'M' + p[0][0].toFixed(1) + ',' + p[0][1].toFixed(1);
    for (i = 0; i < n - 1; i++) {
      d += ' C' + (p[i][0] + dx[i] / 3).toFixed(1) + ',' + (p[i][1] + m[i] * dx[i] / 3).toFixed(1) + ' ' +
        (p[i + 1][0] - dx[i] / 3).toFixed(1) + ',' + (p[i + 1][1] - m[i + 1] * dx[i] / 3).toFixed(1) + ' ' + p[i + 1][0].toFixed(1) + ',' + p[i + 1][1].toFixed(1);
    }
    return d;
  }
  window.__chart = { smooth: smooth, niceRange: niceRange, compact: compactN };
  var RANGES = [[LR.t('24 h'), 86400], [LR.t('7 j'), 7 * 86400], [LR.t('30 j'), 30 * 86400], [LR.t('Tout'), 0]];
  var reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
  document.querySelectorAll('.line-plot').forEach(function (plot, k) {
    var all = JSON.parse(plot.dataset.points), unit = plot.dataset.unit;
    var head = plot.previousElementSibling && plot.previousElementSibling.classList.contains('line-head') ? plot.previousElementSibling : null;
    var fullSpan = all[all.length - 1][0] - all[0][0];
    var cur = 0, pts = all;
    function draw(range, animate) {
      cur = range;
      var tEnd = all[all.length - 1][0];
      pts = range ? all.filter(function (q) { return q[0] >= tEnd - range; }) : all;
      if (pts.length < 2) pts = all.slice(-2);
      var t0 = pts[0][0], t1 = pts[pts.length - 1][0], span = (t1 - t0) || 1;
      var vals = pts.map(function (q) { return q[1]; });
      var vmax = Math.max.apply(null, vals), vmin = Math.min.apply(null, vals);
      var ticks = niceRange(vmin, vmax, 4), lo = ticks[0], hi = ticks[ticks.length - 1];
      var W = 1000, H = 300, first = vals[0], last = vals[vals.length - 1];
      var trend = last < first ? 'down' : 'up';
      function xy(q) { return [(q[0] - t0) / span * W, H - (q[1] - lo) / (hi - lo) * H]; }
      var segs = [], seg = [], prev = null;
      pts.forEach(function (q) { if (prev && q[0] - prev > 3 * 3600) { segs.push(seg); seg = []; } seg.push(xy(q)); prev = q[0]; });
      segs.push(seg);
      var dl = segs.filter(function (s) { return s.length; }).map(smooth).join(' ');
      var da = segs.filter(function (s) { return s.length > 1; }).map(function (s) { return smooth(s) + ' L' + s[s.length - 1][0].toFixed(1) + ',' + H + ' L' + s[0][0].toFixed(1) + ',' + H + ' Z'; }).join(' ');
      var html = ticks.map(function (v) { return '<div class="ytick" style="bottom:' + ((v - lo) / (hi - lo) * 100).toFixed(2) + '%"><span>' + compactN(v) + '</span></div>'; }).join('');
      // repères horizontaux : heures si période courte, jours sinon
      var stepH = span <= 36 * 3600 ? (span <= 14 * 3600 ? 2 : 4) * 3600 : 0;
      if (stepH) {
        for (var t = Math.ceil(t0 / stepH) * stepH; t < t1; t += stepH) {
          var lft = (t - t0) / span * 100;
          if (lft < 4 || lft > 96) continue;
          var hr = dHour.format(new Date(t * 1000));
          var isMid = /^0?0/.test(hr);
          html += '<div class="xtick' + (isMid ? ' day' : '') + '" style="left:' + lft.toFixed(2) + '%"><span>' + (isMid ? dDay.format(new Date(t * 1000)) : hr) + '</span></div>';
        }
      } else {
        var every = span > 20 * 86400 ? 5 : span > 8 * 86400 ? 2 : 1, n = 0;
        var d0 = new Date(t0 * 1000); d0.setHours(24, 0, 0, 0);
        for (var dd = d0.getTime() / 1000; dd < t1; dd += 86400, n++) {
          if (n % every) continue;
          html += '<div class="xtick day" style="left:' + ((dd - t0) / span * 100).toFixed(2) + '%"><span>' + dDay.format(new Date(dd * 1000)) + '</span></div>';
        }
      }
      var gidc = 'lgj' + k;
      html += '<svg viewBox="0 0 ' + W + ' ' + H + '" preserveAspectRatio="none" aria-hidden="true"' + (animate && !reduced ? ' class="reveal"' : '') + '><defs><linearGradient id="' + gidc + '" x1="0" y1="0" x2="0" y2="1">' +
        '<stop offset="0" stop-color="currentColor" stop-opacity=".35"/><stop offset=".7" stop-color="currentColor" stop-opacity=".06"/><stop offset="1" stop-color="currentColor" stop-opacity="0"/></linearGradient></defs>' +
        '<path class="area" d="' + da + '" style="fill:url(#' + gidc + ')"/><path class="stroke" d="' + dl + '" vector-effect="non-scaling-stroke"/></svg>';
      var ip = vals.indexOf(vmax), im = vals.indexOf(vmin);
      var pk = xy(pts[ip]), mn = xy(pts[im]), le = xy(pts[pts.length - 1]);
      if (ip !== pts.length - 1) html += '<span class="peak' + (pk[0] / W > .8 ? ' left' : '') + '" style="left:' + (pk[0] / W * 100).toFixed(2) + '%;top:' + (pk[1] / H * 100).toFixed(2) + '%"><i></i><b>' + LR.t('Pic ') + nf.format(vmax) + '</b></span>';
      if (im !== pts.length - 1 && im !== 0 && vmax !== vmin) html += '<span class="peak low' + (mn[0] / W > .8 ? ' left' : '') + '" style="left:' + (mn[0] / W * 100).toFixed(2) + '%;top:' + (mn[1] / H * 100).toFixed(2) + '%"><i></i><b>' + LR.t('Creux ') + nf.format(vmin) + '</b></span>';
      html += '<span class="end-dot" style="left:' + (le[0] / W * 100).toFixed(2) + '%;top:' + (le[1] / H * 100).toFixed(2) + '%"></span>' +
        '<span class="end-label" style="top:' + (le[1] / H * 100).toFixed(2) + '%">' + compactN(last) + '</span>' +
        '<div class="crosshair" hidden><span class="hline"></span><span class="cdot"></span><span class="tip"></span></div>';
      plot.innerHTML = html;
      plot.classList.remove('up', 'down'); plot.classList.add(trend);
      plot._geo = { t0: t0, span: span, lo: lo, hi: hi };
      if (head) {
        var ch = first ? (last / first - 1) * 100 : 0;
        var btns = RANGES.filter(function (r) { return !r[1] || r[1] < fullSpan; });
        head.hidden = false;
        head.innerHTML = '<div class="lh-main"><span class="lh-val">' + nf.format(last) + '</span><span class="lh-unit">' + unit + '</span>' +
          '<span class="pill ' + (ch >= 0 ? 'up' : 'down') + '">' + pf.format(ch).replace('-', '\u2212') + (LR.k === 'en' ? '%' : ' %') + '</span>' +
          '<span class="lh-range">' + LR.t('sur la période') + '</span></div>' +
          '<div class="lh-side"><span>' + LR.t('Pic ') + '<b>' + nf.format(vmax) + '</b></span><span>' + LR.t('Creux ') + '<b>' + nf.format(vmin) + '</b></span></div>' +
          (btns.length > 1 ? '<div class="seg" role="group" aria-label="' + LR.t('Période') + '">' + btns.map(function (r) {
            return '<button type="button" data-r="' + r[1] + '"' + (r[1] === cur ? ' aria-pressed="true"' : ' aria-pressed="false"') + '>' + r[0] + '</button>';
          }).join('') + '</div>' : '');
        head.querySelectorAll('.seg button').forEach(function (b) { b.addEventListener('click', function () { draw(+b.dataset.r, true); }); });
      }
    }
    draw(0, true);
    function move(clientX) {
      var g = plot._geo, r = plot.getBoundingClientRect();
      var x = Math.min(Math.max(0, clientX - r.left), r.width);
      var t = g.t0 + g.span * x / r.width, best = pts[0];
      for (var i = 1; i < pts.length; i++) if (Math.abs(pts[i][0] - t) < Math.abs(best[0] - t)) best = pts[i];
      var ch = plot.querySelector('.crosshair'), tp = ch.querySelector('.tip');
      var yp = (1 - (best[1] - g.lo) / (g.hi - g.lo)) * 100, xp = (best[0] - g.t0) / g.span * 100;
      ch.hidden = false;
      ch.style.left = xp + '%';
      ch.querySelector('.cdot').style.top = yp + '%';
      ch.querySelector('.hline').style.top = yp + '%';
      tp.innerHTML = '<b>' + nf.format(best[1]) + '</b> ' + unit + '<br><span>' + df.format(new Date(best[0] * 1000)) + '</span>';
      tp.classList.toggle('flip-l', xp > 82); tp.classList.toggle('flip-r', xp < 18);
    }
    plot.addEventListener('mousemove', function (e) { move(e.clientX); });
    plot.addEventListener('touchmove', function (e) { move(e.touches[0].clientX); }, { passive: true });
    plot.addEventListener('mouseleave', function () { var c = plot.querySelector('.crosshair'); if (c) c.hidden = true; });
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
  var nf = new Intl.NumberFormat(LR.loc), cache = {};
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
    var C = window.__chart, vals = all.map(function (p) { return p[1]; });
    var ticks = C.niceRange(Math.min.apply(null, vals), Math.max.apply(null, vals), 4), lo = ticks[0], hi = ticks[ticks.length - 1];
    var W = 1000, H = 300, span = (t1 - t0) || 1, svg = '', dots = '', defs = '';
    series.forEach(function (g, i) {
      var segs = [], seg = [], prev = null, last = null;
      g.serie.forEach(function (p) {
        var t = Date.parse(p[0]), pt = [(t - t0) / span * W, H - (p[1] - lo) / (hi - lo) * H];
        if (prev && t - prev > 3 * 3600e3) { segs.push(seg); seg = []; }
        seg.push(pt); prev = t; last = pt;
      });
      segs.push(seg);
      var id = 'cg' + i;
      var col = i ? '#f97316' : '#3b82f6';
      defs += '<linearGradient id="' + id + '" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="' + col + '" stop-opacity=".22"/><stop offset="1" stop-color="' + col + '" stop-opacity="0"/></linearGradient>';
      svg += '<g class="s' + (i + 1) + '">' + segs.filter(function (q) { return q.length > 1; }).map(function (q) {
        return '<path class="area" d="' + C.smooth(q) + ' L' + q[q.length - 1][0].toFixed(1) + ',' + H + ' L' + q[0][0].toFixed(1) + ',' + H + ' Z" style="fill:url(#' + id + ')"/>';
      }).join('') + '<path class="stroke" d="' + segs.filter(function (q) { return q.length; }).map(C.smooth).join(' ') + '" vector-effect="non-scaling-stroke"/></g>';
      if (last) dots += '<span class="end-dot s' + (i + 1) + '" style="left:' + (last[0] / W * 100).toFixed(2) + '%;top:' + (last[1] / H * 100).toFixed(2) + '%"></span>';
    });
    var grid = ticks.map(function (v) { return '<div class="ytick" style="bottom:' + ((v - lo) / (hi - lo) * 100).toFixed(2) + '%"><span>' + C.compact(v) + '</span></div>'; }).join('');
    plot.innerHTML = grid + '<svg viewBox="0 0 ' + W + ' ' + H + '" preserveAspectRatio="none" aria-hidden="true"><defs>' + defs + '</defs>' + svg + '</svg>' + dots;
    var dfx = new Intl.DateTimeFormat(LR.loc, { day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit', timeZone: 'Europe/Paris' });
    document.getElementById('compare-x').innerHTML = '<span>' + dfx.format(new Date(t0)) + '</span><span>' + dfx.format(new Date(t1)) + '</span>';
    legend.innerHTML = series.map(function (g, i) { return '<li><i class="s' + (i + 1) + '"></i>' + esc(g.nom) + '</li>'; }).join('');
    title.textContent = ga.nom + LR.t(' face à ') + gb.nom;
    stats.innerHTML = series.map(function (g, i) {
      return '<div class="stat c' + (i + 1) + '"><span class="stat-label">' + esc(g.nom) + '</span><span class="stat-value">' + nf.format(g.joueurs) +
        '</span><span class="stat-note">' + LR.t('joueurs au dernier relevé, pic sur 24 h : ') + (g.pic_24h != null ? nf.format(g.pic_24h) : '—') + '</span></div>';
    }).join('');
  }
  function update() {
    var p = new URLSearchParams({ a: a.value, b: b.value });
    history.replaceState(null, '', '?' + p.toString());
    title.textContent = 'Chargement…';
    Promise.all([get(a.value), get(b.value)]).then(function (r) { draw(r[0], r[1]); })
      .catch(function () { title.textContent = LR.t('Données indisponibles pour ce jeu. Choisissez-en un autre.'); });
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
    else copy(location.href, LR.t('Lien copié dans le presse-papier !'));
  });
  document.querySelectorAll('[data-copy]').forEach(function (b) { b.addEventListener('click', function () { copy(b.dataset.copy, b.dataset.copyMsg || LR.t('Adresse copiée !')); }); });
  document.querySelectorAll('[data-copy-from]').forEach(function (b) {
    b.addEventListener('click', function () { copy(document.getElementById(b.dataset.copyFrom).textContent, LR.t('Code copié !')); });
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
    var text = n[0] + LR.t(' face à ') + n[1] + LR.t(' : joueurs en ligne, heure par heure, sur Le Relevé 📊');
    xs.href = 'https://twitter.com/intent/tweet?text=' + encodeURIComponent(text) + '&url=' + encodeURIComponent(location.href);
    var li = document.getElementById('li-share'); if (li) li.href = 'https://www.linkedin.com/sharing/share-offsite/?url=' + encodeURIComponent(location.href);
  }
  if (xs) { refreshX(); document.getElementById('compare').addEventListener('change', function () { setTimeout(refreshX, 50); }); xs.addEventListener('focus', refreshX); xs.addEventListener('mouseenter', refreshX); }
  if (cp) cp.addEventListener('click', function () {
    var t = document.getElementById('toast');
    var done = function () { if (t) { t.textContent = LR.t('Lien copié dans le presse-papier !'); t.classList.add('show'); setTimeout(function () { t.classList.remove('show'); }, 2200); } };
    if (navigator.clipboard) navigator.clipboard.writeText(location.href).then(done, done); else done();
  });
  var fs = document.querySelector('.feed-status');
  if (fs) {
    var last = Date.parse(fs.dataset.last), next = fs.querySelector('.fs-next');
    var tick = function () {
      var m = Math.round((last + 3600e3 - Date.now()) / 60000);
      next.innerHTML = ' <span class="sep">•</span> ' + (m > 0 ? LR.t('Prochain relevé dans ') + m + ' min' : LR.t('Prochain relevé imminent'));
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
      return '<li' + (i === sel ? ' class="on"' : '') + '>' + a.outerHTML + '<span>' + (g.rang ? LR.ord(g.rang) : '') + '</span></li>';
    }).join('') : '<li class="none">' + LR.t('Aucun jeu suivi ne correspond') + '</li>';
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
    btn.setAttribute('aria-label', open ? LR.t('Fermer le menu') : LR.t('Ouvrir le menu'));
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

(function () {
  var q = document.getElementById('q'), k = document.querySelector('.search .kbd');
  if (!q) return;
  var mac = /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent);
  if (k && mac) k.textContent = '\u2318K';
  document.addEventListener('keydown', function (e) {
    if ((e.metaKey || e.ctrlKey) && (e.key === 'k' || e.key === 'K')) {
      e.preventDefault();
      var head = document.querySelector('.site-head'), btn = document.querySelector('.menu-btn');
      if (btn && getComputedStyle(btn).display !== 'none' && !head.classList.contains('open')) btn.click();
      q.focus(); q.select();
    }
  });
})();
