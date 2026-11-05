barra('repartidor.html');
const $ = id => document.getElementById(id);
// Botones segun el estado. 'entrega' abre el formulario de evidencia; 'incidencia' pide el motivo.
const ACCIONES = {
  retirado: [['en_transito', 'En transito'], ['incidencia', 'Reportar incidencia']],
  en_transito: [['entrega', 'Entregar'], ['incidencia', 'Reportar incidencia']],
  incidencia: [],   // la resuelve el operador desde el panel de despacho
};
let codigoEntrega = null;
const repId = () => Number($('rep').value);
const actor = () => 'repartidor-' + repId();

function botones(x) {
  if (x.estado === 'asignado' && !x.aceptada)
    return `<button class="chico" data-aceptar="${x.asignacion_id}">Aceptar</button>
            <button class="chico peligro" data-rechazar="${x.asignacion_id}">Rechazar</button>`;
  if (x.estado === 'asignado') return `<button class="chico" data-cod="${esc(x.codigo)}" data-estado="retirado">Retirar paquete</button>`;
  if (x.estado === 'incidencia') return '<span class="pista">Esperando resolucion del operador</span>';
  return (ACCIONES[x.estado] || []).map(([e, txt]) =>
    `<button class="chico ${e === 'incidencia' ? 'peligro' : ''}" data-cod="${esc(x.codigo)}" data-estado="${e}">${txt}</button>`).join('');
}

async function tareas() {
  const t = await api(`/repartidores/${repId()}/tareas`);
  $('tareas').innerHTML = t.length ? `<table><thead><tr><th>Codigo</th><th>Destino</th><th>Zona</th><th>Estado</th><th>Acciones</th></tr></thead><tbody>` +
    t.map(x => `<tr><td class="mono">${esc(x.codigo)}</td><td>${esc(x.destino)}</td><td>${esc(x.zona)}</td>
      <td>${badge(x.estado)}${x.estado === 'asignado' && !x.aceptada ? ' <span class="pista">pendiente de aceptar</span>' : ''}</td>
      <td class="acciones">${botones(x)}</td></tr>`).join('') + '</tbody></table>'
    : '<p class="vacio">No tiene tareas asignadas. El operador le asignara envios desde el panel de despacho.</p>';
}

async function posicion() {
  try { const p = await api(`/repartidores/${repId()}/posicion`);
    $('posinfo').textContent = p.vigente ? `Posicion vigente ${p.lat.toFixed(4)}, ${p.lon.toFixed(4)} (expira en ${p.ttl_restante} s)` : 'Posicion no vigente (expiro o nunca se envio)';
  } catch (e) { $('posinfo').textContent = e.message; }
}

$('tareas').addEventListener('click', async ev => {
  const b = ev.target.closest('button'); if (!b) return; const d = b.dataset;
  if (d.aceptar || d.rechazar) {
    b.disabled = true;
    const accion = d.aceptar ? 'aceptar' : 'rechazar';
    await intentar(() => api(`/asignaciones/${d.aceptar || d.rechazar}/${accion}`, { method: 'PATCH', body: { actor: actor(), evento_id: uuid() } }),
      d.aceptar ? 'Asignacion aceptada' : 'Asignacion rechazada');
    return tareas();
  }
  if (d.estado === 'entrega') { codigoEntrega = d.cod; $('cod-entrega').textContent = codigoEntrega; $('form-entrega').hidden = false; $('fe').receptor.focus(); return; }
  let detalle;
  if (d.estado === 'incidencia') { detalle = prompt('Motivo de la incidencia:'); if (!detalle || !detalle.trim()) return; }
  b.disabled = true;
  await intentar(() => api(`/envios/${d.cod}/estado`, { method: 'PATCH', body: { nuevo_estado: d.estado, actor: actor(), evento_id: uuid(), detalle } }), 'Estado actualizado');
  tareas();
});

$('fe').addEventListener('submit', async e => {
  e.preventDefault();
  const d = Object.fromEntries(new FormData(e.target)); if (!d.foto_url) delete d.foto_url;
  const r = await intentar(() => api(`/envios/${codigoEntrega}/entrega`, { method: 'POST',
    body: { ...d, actor: actor(), evidencia_id: uuid(), evento_id: uuid() } }), 'Entrega registrada con evidencia');
  if (r) { $('form-entrega').hidden = true; e.target.reset(); tareas(); }
});
$('cancelar-entrega').addEventListener('click', () => { $('form-entrega').hidden = true; });

$('pos').addEventListener('click', async () => {   // posicion ficticia cerca del centro de Quito
  const lat = -0.1807 + (Math.random() - .5) * .04, lon = -78.4678 + (Math.random() - .5) * .04;
  await intentar(() => api(`/repartidores/${repId()}/posicion`, { method: 'PUT', body: { lat, lon } }), 'Posicion enviada');
  posicion();
});
$('rep').addEventListener('change', () => { tareas(); posicion(); });

(async () => { const r = await intentar(() => api('/repartidores'));
  if (!r) return; $('rep').innerHTML = r.map(x => `<option value="${x.id}">${esc(x.nombre)}</option>`).join(''); tareas(); posicion(); })();
