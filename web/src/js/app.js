/* app.js - Utilidades compartidas por todas las pantallas.
   El navegador SOLO habla con la API (ruta /api/), nunca con las bases de datos. */

const API = '/api';

/** Rol activo (simulado). Se guarda en sessionStorage y se envia en X-Rol. */
function rolActual() { return sessionStorage.getItem('rol') || 'administrador'; }

/** Llama a la API. Devuelve el JSON o lanza Error con un mensaje legible (err.status = codigo HTTP). */
async function api(ruta, { method = 'GET', body } = {}) {
  let r;
  try {
    r = await fetch(API + ruta, {
      method,
      headers: { 'Content-Type': 'application/json', 'X-Rol': rolActual() },
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch (e) {
    const err = new Error('No se pudo contactar con la API. Verifique que los contenedores esten activos.');
    err.status = 0; throw err;
  }
  let datos = null;
  try { datos = await r.json(); } catch (e) { /* respuesta sin cuerpo */ }
  if (!r.ok) {
    const d = datos && datos.detail;
    let msg = 'Error ' + r.status;
    if (typeof d === 'string') msg = d;
    else if (Array.isArray(d)) msg = d.map(x => (x.loc || []).slice(1).join('.') + ': ' + x.msg).join('; ');
    const err = new Error(msg); err.status = r.status; throw err;
  }
  return datos;
}

/** Escapa texto antes de meterlo en innerHTML (evita XSS con datos escritos por usuarios). */
function esc(t) {
  return String(t ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

/** UUID v4 (crypto.randomUUID solo existe en contextos seguros; hay alternativa). */
function uuid() {
  if (crypto.randomUUID) return crypto.randomUUID();
  const b = crypto.getRandomValues(new Uint8Array(16));
  b[6] = (b[6] & 0x0f) | 0x40; b[8] = (b[8] & 0x3f) | 0x80;
  const h = [...b].map(x => x.toString(16).padStart(2, '0')).join('');
  return `${h.slice(0, 8)}-${h.slice(8, 12)}-${h.slice(12, 16)}-${h.slice(16, 20)}-${h.slice(20)}`;
}

function fmtFecha(iso) { return iso ? new Date(iso).toLocaleString() : '-'; }
function nombreEstado(e) { return String(e).replace('_', ' '); }
function badge(e) { return `<span class="badge e-${esc(e)}">${esc(nombreEstado(e))}</span>`; }

/** Mensaje flotante de exito o error (visible 6 s). */
function aviso(texto, tipo = 'ok') {
  let c = document.getElementById('avisos');
  if (!c) { c = document.createElement('div'); c.id = 'avisos'; c.setAttribute('role', 'status'); document.body.appendChild(c); }
  const d = document.createElement('div');
  d.className = 'aviso ' + (tipo === 'error' ? 'error' : '');
  d.textContent = texto; c.appendChild(d);
  setTimeout(() => d.remove(), 6000);
}

/** Ejecuta una accion y muestra el resultado; devuelve undefined si fallo. */
async function intentar(fn, textoOk) {
  try { const r = await fn(); if (textoOk) aviso(textoOk); return r; }
  catch (e) { aviso(e.message, 'error'); }
}

/** Linea de tiempo (lista de eventos de /envios/{codigo}). */
function lineaDeTiempo(eventos) {
  if (!eventos.length) return '<p class="vacio">Sin eventos todavia.</p>';
  return '<ol class="ruta">' + eventos.map((e, i) => {
    const fin = i === eventos.length - 1;
    const clase = (fin ? 'ultimo ' : '') + (['entregado', 'incidencia'].includes(e.estado_nuevo) ? 'fin-' + e.estado_nuevo : '');
    return `<li class="${clase}"><strong>${esc(nombreEstado(e.estado_nuevo))}</strong>${e.detalle ? ' - ' + esc(e.detalle) : ''}
      <div class="quien">${esc(fmtFecha(e.fecha))} - ${esc(e.actor)}</div></li>`;
  }).join('') + '</ol>';
}

const PAGINAS = [['index.html', 'Solicitar envio'], ['seguimiento.html', 'Seguimiento'], ['despacho.html', 'Despacho'],
                 ['repartidor.html', 'Repartidor'], ['detalle.html', 'Detalle'], ['admin.html', 'Administracion']];

/** Dibuja la barra superior con navegacion y selector de rol. */
function barra(activa) {
  const h = document.createElement('header'); h.className = 'barra';
  h.innerHTML = `<span class="marca">Mensajeria urbana</span><nav aria-label="Principal">` +
    PAGINAS.map(([u, t]) => `<a href="${u}" class="${u === activa ? 'activa' : ''}">${t}</a>`).join('') + `</nav>
    <label>Rol simulado
      <select id="rol">${['cliente', 'operador', 'repartidor', 'administrador']
        .map(r => `<option ${r === rolActual() ? 'selected' : ''}>${r}</option>`).join('')}</select></label>`;
  document.body.prepend(h);
  h.querySelector('#rol').addEventListener('change', e => { sessionStorage.setItem('rol', e.target.value); aviso('Rol activo: ' + e.target.value); });
}

/** Rellena un <select> con zonas. */
async function cargarZonas(sel, conTodas = false) {
  const zonas = await api('/zonas');
  sel.innerHTML = (conTodas ? '<option value="">Todas</option>' : '') +
    zonas.map(z => `<option value="${z.id}">${esc(z.nombre)}</option>`).join('');
  return zonas;
}

function parametro(nombre) { return new URLSearchParams(location.search).get(nombre) || ''; }
