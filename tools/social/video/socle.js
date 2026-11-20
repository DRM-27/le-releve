/* Socle des vidéos PlayLedger (voir README.md).
   Règles : la 1re image est la couverture (lisible, vrais chiffres) ; dès 0,25 s quelque chose bouge ; jamais plus d'1 s figé ;
   le titre reste épinglé pendant que le visuel raconte ; la question arrive pendant le moment fort (2 à 3 s) ;
   la dernière seconde ramène à la couverture pour que la vidéo boucle. Aucun chiffre intermédiaire inventé :
   les chiffres « tombent » caractère par caractère à leur valeur finale. */
let D = null;
const $ = id => typeof id === "string" ? document.getElementById(id) : id;
const NB = s => String(s ?? "").replace(/[  ]/g, " ");
const F = k => NB((D.facts || {})[k] ?? "");
const R = k => (D.raw || {})[k];
const nf = new Intl.NumberFormat("fr-FR");
const fmt = n => nf.format(Math.round(n)).replace(/\s/g, " ");
const clean = s => String(s).replace(/^(\s*[\[(][^\])]*[\])]\s*)+/, "").replace(/\s*[\[(][^\])]*[\])]\s*$/, "").trim();
const court = s => clean(String(s).replace(/^[\p{Extended_Pictographic}\u{1F3FB}-\u{1F3FF}‍️\s]+/u, "")).replace(/[\p{Extended_Pictographic}\u{1F3FB}-\u{1F3FF}‍️].*$/u, "").trim();
const clamp = (x, a = 0, b = 1) => Math.max(a, Math.min(b, x));
const lerp = (a, b, x) => a + (b - a) * x;
const eo = x => 1 - Math.pow(1 - clamp(x), 3);
const ei = x => Math.pow(clamp(x), 3);
const eio = x => { x = clamp(x); return x < .5 ? 4*x*x*x : 1 - Math.pow(-2*x + 2, 3)/2; };
const back = x => { x = clamp(x); const c = 1.7; return 1 + (c + 1) * Math.pow(x - 1, 3) + c * Math.pow(x - 1, 2); };
const seg = (t, a, b) => clamp((t - a) / (b - a));
const JOURS = ["dimanche","lundi","mardi","mercredi","jeudi","vendredi","samedi"];
const MOIS = ["janvier","février","mars","avril","mai","juin","juillet","août","septembre","octobre","novembre","décembre"];
const MOISC = ["janv.","févr.","mars","avr.","mai","juin","juil.","août","sept.","oct.","nov.","déc."];
const jourDe = iso => { const [y, m, d] = iso.slice(0, 10).split("-").map(Number); const dt = new Date(Date.UTC(y, m - 1, d, 12)); return {jour: JOURS[dt.getUTCDay()], d, mois: MOIS[m - 1], moisc: MOISC[m - 1]}; };
const dateLongue = iso => { const j = jourDe(iso); return `${j.jour} ${j.d === 1 ? "1er" : j.d} ${j.mois}`; };
const dateCourte = iso => { const j = jourDe(iso); return `${j.d === 1 ? "1er" : j.d} ${j.moisc}`; };
const dateMoy = iso => { const j = jourDe(iso); return `${j.d === 1 ? "1er" : j.d} ${j.mois}`; };
const Maj = s => s.replace(/^./, c => c.toUpperCase());
const typo = s => String(s).replace(/ ([?!:;%»])/g, "\u00a0$1").replace(/« /g, "«\u00a0");   // espaces insécables du français
const ICON = '<svg viewBox="0 0 32 32"><rect width="32" height="32" rx="7" fill="#1b2a41" stroke="#3a4f73" stroke-width="1"/><rect x="7" y="16" width="5" height="10" rx="1" fill="#86a9ff"/><rect x="13.5" y="6" width="5" height="20" rx="1" fill="#86a9ff"/><rect x="20" y="11" width="5" height="15" rx="1" fill="#86a9ff"/></svg>';
const ico = (uid, size, extra = "") => `<img class="ico" src="icones/${uid}.png" style="width:${size}px;height:${size}px;${extra}" alt="">`;

window.SFX = [];
const sfx = (t, s) => window.SFX.push([+t.toFixed(3), s]);
let DUR = 21, LOOPD = 1.0;
const loopP = t => eo(seg(t, DUR - LOOPD, DUR - .12));          // 0 → 1 : retour à la couverture

/* habillage : fond vivant, bandeau-signature, titre épinglé, carte-question, pied de page */
function chrome(opt){
  document.documentElement.style.setProperty("--c", opt.couleur);
  document.body.insertAdjacentHTML("afterbegin", `<div id="bg"></div><div id="grid"></div>`);
  document.body.insertAdjacentHTML("beforeend", `
  <div class="band" id="band"><b>${opt.mot}</b><span>${opt.sous || ""}</span></div>
  <div id="title"></div>
  <div id="qc"><div class="qq" id="qq"></div><div class="qs">Réponds en commentaire 👇</div></div>
  <div id="foot">${ICON}<span><b>PlayLedger</b> · ${opt.source}</span></div>
  <div id="flash"></div>`);
  const ti = $("title"); ti.innerHTML = typo(opt.titre); ti.style.fontSize = (opt.taille || 76) + "px";
  if (opt.maxH) { let s = opt.taille || 76; while (ti.offsetHeight > opt.maxH && s > 44) { s -= 2; ti.style.fontSize = s + "px"; } }
  $("qq").textContent = typo(opt.question);
  $("qc").style.top = (opt.qTop ?? 1090) + "px";
}
/* fond : la lueur et la grille dérivent sur un cycle exact de la durée, pour que la dernière image rejoigne la première */
function amb(t){
  const w = 2 * Math.PI * t / DUR;
  $("grid").style.transform = `translate(${(90 * t / DUR) % 90}px, ${(180 * t / DUR) % 90}px)`;
  $("bg").style.background = `radial-gradient(900px 900px at ${50 + 7 * Math.sin(w)}% ${40 + 5 * Math.sin(2 * w)}%, color-mix(in srgb, var(--c) 22%, transparent) 0%, transparent 70%), linear-gradient(#0f1622,#0a0f16)`;
}
/* caméra : zoom lent et secousse, appliqués à la scène (pas au titre ni au bandeau) */
function camera(t, z = 1, shakes = []){
  let sx = 0, sy = 0;
  shakes.forEach(([at, amp, d = .5]) => { const p = seg(t, at, at + d); if (p > 0 && p < 1) { const k = (1 - p) * (1 - p) * amp; sx += k * Math.sin(t * 97); sy += k * Math.cos(t * 73); } });
  $("stage").style.transform = `translate(${sx.toFixed(2)}px, ${sy.toFixed(2)}px) scale(${z.toFixed(5)})`;
  window.CAM = {sx, sy};
}
/* chiffres qui tombent caractère par caractère : on ne voit jamais une autre valeur que la vraie */
const SEGM = new Intl.Segmenter("fr", {granularity: "grapheme"});
function split(el, text){ el = $(el); el.dataset.txt = text; el.innerHTML = [...SEGM.segment(NB(text))].map(s => `<span class="dg">${s.segment.replace(/&/g, "&amp;").replace(/</g, "&lt;")}</span>`).join(""); }
function drop(el, t, at, st = .035, dy = 50){
  el = $(el);
  [...el.querySelectorAll(":scope > .dg")].forEach((s, i) => {
    const p = seg(t, at + i * st, at + i * st + .3);
    s.style.opacity = p > 0 ? Math.min(1, p * 3) : 0;
    s.style.transform = `translateY(${((1 - back(p)) * -dy).toFixed(2)}px)`;
  });
}
function setDrop(el, text, t, at){ el = $(el); if (el.dataset.txt !== text) split(el, text); drop(el, t, at); }
/* apparitions */
function pop(el, t, at, from = .8, extra = ""){ el = $(el); const p = seg(t, at, at + .34); el.style.opacity = p > 0 ? 1 : 0; el.style.transform = `${extra} scale(${(from + (1 - from) * back(p)).toFixed(4)})`; return p; }
function fade(el, t, at, d = .3, dy = 24){ el = $(el); const v = eo(seg(t, at, at + d)); el.style.opacity = v; el.style.transform = `translateY(${((1 - v) * dy).toFixed(2)}px)`; return v; }
function vis(el, v){ $(el).style.opacity = clamp(v); }
/* carte-question : arrive en rebond pendant le moment fort, grossit doucement, repart avant la boucle */
function qcard(t, at, end){
  const el = $("qc"), i = seg(t, at, at + .38), o = 1 - eo(seg(t, end - .3, end));
  if (t < at || t > end) { el.style.opacity = 0; $("foot").style.opacity = 1; return; }
  el.style.opacity = Math.min(1, i * 3, o);
  if (el.offsetTop + el.offsetHeight > 1436) $("foot").style.opacity = 1 - el.style.opacity;   // la carte basse masque le pied le temps de la question
  el.style.transform = `scale(${(.84 + .14 * back(i) + .015 * seg(t, at, end)).toFixed(4)})`;
}
function flash(t, at, d = .35, k = .55){ return t >= at ? k * (1 - seg(t, at, at + d)) : 0; }
function setFlash(v){ $("flash").style.opacity = v; }
function stack(ids, gap = 22){ for (let i = 1; i < ids.length; i++) { const a = $(ids[i - 1]), b = $(ids[i]); b.style.top = (a.offsetTop + a.offsetHeight + gap) + "px"; } }
/* courbe : points {x, y}, dévoilée jusqu'à l'index fractionnaire idx ; renvoie le point de tête */
function curveIdx(path, fill, pts, idx, base){
  const n = pts.length - 1; idx = clamp(idx, 0, n);
  const i0 = Math.floor(idx), out = pts.slice(0, i0 + 1);
  if (i0 < n) { const a = pts[i0], b = pts[i0 + 1], f = idx - i0; out.push({x: a.x + (b.x - a.x) * f, y: a.y + (b.y - a.y) * f}); }
  const d = out.map((q, i) => (i ? "L" : "M") + q.x.toFixed(1) + " " + q.y.toFixed(1)).join(" ");
  path.setAttribute("d", d);
  if (fill) fill.setAttribute("d", d + ` L ${out[out.length - 1].x.toFixed(1)} ${base} L ${out[0].x.toFixed(1)} ${base} Z`);
  return out[out.length - 1];
}
/* temps « déformé » : une suite de tronçons [durée, vitesse] ; renvoie la position atteinte à l'instant t (ralentis sans à-coups) */
function warp(t, t0, parts){
  let pos = 0, at = t0;
  for (const [len, dur] of parts) { if (t <= at) break; const f = clamp((t - at) / dur); pos += len * f; at += dur; }
  return pos;
}
window.__defineGetter__("DURATION", () => DUR);

/* Contrôles automatiques, appelés sur chaque image filmée (shoot3.py) :
   1. la carte-question ne recouvre jamais un chiffre du moment fort (classe .fort) ;
   2. tout ce qui est visible reste dans la zone sûre (x 72 → 900, y 230 → 1436 ; le pied de page peut descendre plus bas) ;
   3. un chiffre attaché à un jeu (classe .val) s'affiche à sa valeur finale (data-v) : aucun compteur sur ces chiffres. */
window.ERREURS = {};
const ZS = {x0: 72, x1: 900, y0: 230, y1: 1436}, TOL = 8;
function opac(el){ let o = 1; for (let e = el; e && e !== document.body; e = e.parentElement) { const cs = getComputedStyle(e); if (cs.display === "none" || cs.visibility === "hidden") return 0; o *= +cs.opacity; } return o; }
function inter(a, b){ return Math.max(0, Math.min(a.right, b.right) - Math.max(a.left, b.left)) * Math.max(0, Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top)); }
function err(k, msg, t){ if (!window.ERREURS[k]) window.ERREURS[k] = `${msg} (à ${t.toFixed(2)} s)`; }
const nom = el => el.id ? "#" + el.id : el.className ? "." + String(el.className).split(" ")[0] : el.tagName;
function verif(t){
  if (window.verifPage) verifPage(t);
  const qc = $("qc");
  if (qc && opac(qc) > .3) { const r = qc.getBoundingClientRect();
    document.querySelectorAll(".fort").forEach(f => { if (opac(f) > .3) { const a = inter(r, f.getBoundingClientRect()); if (a > 200) err("q" + nom(f), `la question recouvre le chiffre fort ${nom(f)}`, t); } }); }
  document.querySelectorAll("#title,.band,#qc,.chip,.fort,.val,.zs,img.ico").forEach(el => {
    if (opac(el) < .15) return; const q = el.getBoundingClientRect(); if (!q.width) return;
    const c = window.CAM && $("stage") && $("stage").contains(el) ? window.CAM : {sx: 0, sy: 0};
    const r = {left: q.left - c.sx, right: q.right - c.sx, top: q.top - c.sy, bottom: q.bottom - c.sy};
    if (r.left < ZS.x0 - TOL || r.right > ZS.x1 + TOL || r.top < ZS.y0 - TOL || r.bottom > ZS.y1 + TOL) err("z" + nom(el), `${nom(el)} sort de la zone sûre (${Math.round(r.left)}, ${Math.round(r.top)}, ${Math.round(r.right)}, ${Math.round(r.bottom)})`, t);
  });
  document.querySelectorAll(".val").forEach(el => { if (opac(el) > .15 && el.dataset.v !== undefined && NB(el.textContent).trim() !== NB(el.dataset.v).trim()) err("v" + nom(el), `${nom(el)} affiche « ${el.textContent} » au lieu de « ${el.dataset.v} »`, t); });
}
function setVal(el, v){ el = $(el); v = NB(v); el.dataset.v = v; if (el.dataset.txt !== undefined) { if (el.dataset.txt !== v) split(el, v); } else el.textContent = v; }
