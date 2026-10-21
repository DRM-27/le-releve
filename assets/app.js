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
