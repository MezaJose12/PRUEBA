barra('despacho.html');
const $ = id => document.getElementById(id);
let repartidores = [];

async function cargarRepartidores() {
  repartidores = await api('/repartidores');
  let pos = {}; try { (await api('/posiciones')).forEach(p => pos[p.repartidor_id] = p); } catch (e) { /* Redis caido: se omite */ }
  $('repartidores').innerHTML = `<table><thead><tr><th>Repartidor</th><th>Carga</th><th>Disponible</th><th>Posicion vigente</th></tr></thead><tbody>` +
    repartidores.map(r => `<tr><td>${esc(r.nombre)}</td><td>${r.carga_actual} / ${r.capacidad_max}</td>
      <td>${r.disponible ? 'Si' : 'No'}</td><td class="mono">${pos[r.id] ? pos[r.id].lat.toFixed(4) + ', ' + pos[r.id].lon.toFixed(4) : 'no vigente'}</td></tr>`).join('') + '</tbody></table>';
}

async function cargarEnvios() {
  const q = new URLSearchParams(); if ($('f-estado').value) q.set('estado', $('f-estado').value); if ($('f-zona').value) q.set('zona_id', $('f-zona').value);
  const envios = await api('/envios?' + q);
  if (!envios.length) { $('envios').innerHTML = '<p class="vacio">No hay envios con esos filtros.</p>'; return; }
  const opciones = repartidores.filter(r => r.disponible).map(r => `<option value="${r.id}">${esc(r.nombre)} (${r.carga_actual}/${r.capacidad_max})</option>`).join('');
  $('envios').innerHTML = `<table><thead><tr><th>Codigo</th><th>Destinatario</th><th>Zona</th><th>Estado</th><th>Repartidor</th><th>Acciones</th></tr></thead><tbody>` +
    envios.map(e => {
      let acc = '';
      if (e.estado === 'creado') acc = `<select aria-label="Repartidor" data-sel="${esc(e.codigo)}">${opciones || '<option value="">Sin cupo</option>'}</select>
        <button class="chico" data-asignar="${esc(e.codigo)}" ${opciones ? '' : 'disabled'}>Asignar</button>
        <button class="chico peligro" data-cancelar="${esc(e.codigo)}">Cancelar</button>`;
      else if (e.estado === 'asignado') acc = `<button class="chico sec" data-liberar="${e.asignacion_id}">Liberar</button>
        <button class="chico peligro" data-cancelar="${esc(e.codigo)}">Cancelar</button>`;
      return `<tr><td class="mono"><a href="detalle.html?codigo=${encodeURIComponent(e.codigo)}">${esc(e.codigo)}</a></td><td>${esc(e.destinatario)}</td>
        <td>${esc(e.zona)}</td><td>${badge(e.estado)}</td><td>${esc(e.repartidor || '-')}</td><td class="acciones">${acc}</td></tr>`;
    }).join('') + '</tbody></table>';
}

async function cargarIncidencias() {
  const inc = await api('/envios?estado=incidencia');
  $('incidencias').innerHTML = inc.length ? `<table><thead><tr><th>Codigo</th><th>Destinatario</th><th>Repartidor</th><th>Motivo</th><th>Acciones</th></tr></thead><tbody>` +
    inc.map(e => `<tr><td class="mono"><a href="detalle.html?codigo=${encodeURIComponent(e.codigo)}">${esc(e.codigo)}</a></td><td>${esc(e.destinatario)}</td>
      <td>${esc(e.repartidor || '-')}</td><td>${esc(e.ultimo_detalle || '-')}</td>
      <td class="acciones"><button class="chico" data-inc="en_transito" data-cod="${esc(e.codigo)}">Reanudar entrega</button>
      <button class="chico peligro" data-inc="devuelto" data-cod="${esc(e.codigo)}">Devolver al remitente</button></td></tr>`).join('') + '</tbody></table>'
    : '<p class="vacio">No hay incidencias abiertas.</p>';
}
$('incidencias').addEventListener('click', async ev => {
  const b = ev.target.closest('button'); if (!b) return; b.disabled = true;
  await intentar(() => api(`/envios/${b.dataset.cod}/estado`, { method: 'PATCH', body: { nuevo_estado: b.dataset.inc, actor: 'operador',
    evento_id: uuid(), detalle: 'Incidencia resuelta por el operador' } }), 'Incidencia resuelta');
  refrescar();
});

async function refrescar() { await intentar(async () => { await cargarRepartidores(); await cargarEnvios(); await cargarIncidencias(); }); }

$('envios').addEventListener('click', async ev => {
  const b = ev.target.closest('button'); if (!b) return;
  const d = b.dataset; b.disabled = true;
  if (d.asignar) {
    const rep = document.querySelector(`[data-sel="${d.asignar}"]`).value;
    await intentar(() => api('/asignaciones', { method: 'POST', body: { codigo_envio: d.asignar, repartidor_id: Number(rep), actor: 'operador', evento_id: uuid() } }), 'Envio asignado');
  } else if (d.liberar) {
    await intentar(() => api(`/asignaciones/${d.liberar}/liberar`, { method: 'PATCH', body: { actor: 'operador', evento_id: uuid() } }), 'Asignacion liberada');
  } else if (d.cancelar) {
    await intentar(() => api(`/envios/${d.cancelar}/estado`, { method: 'PATCH', body: { nuevo_estado: 'cancelado', actor: 'operador', evento_id: uuid() } }), 'Envio cancelado');
  }
  refrescar();
});
$('f-estado').addEventListener('change', refrescar); $('f-zona').addEventListener('change', refrescar); $('recargar').addEventListener('click', refrescar);

async function estadoSync() {
  try { const s = await api('/sincronizacion/estado');
    $('sync').textContent = `Indice: ${s.envios_en_busqueda ?? 'no disponible'} de ${s.envios_postgres} envios - avisos pendientes: ${s.outbox.pendientes} - ${s.sincronizado ? 'sincronizado' : 'con retraso'}`;
  } catch (e) { $('sync').textContent = e.message; }
}

$('fb').addEventListener('submit', async e => {
  e.preventDefault();
  const q = new URLSearchParams(); new FormData(e.target).forEach((v, k) => { if (v) q.set(k, k === 'hasta' ? v + 'T23:59:59' : v); });
  estadoSync();
  try {
    const r = await api('/buscar?' + q);
    $('busqueda').innerHTML = r.resultados.length ? `<table><thead><tr><th>Codigo</th><th>Destinatario</th><th>Zona</th><th>Estado</th><th>Creado</th></tr></thead><tbody>` +
      r.resultados.map(x => `<tr><td class="mono">${esc(x._id)}</td><td>${esc(x.destinatario)}</td><td>${esc(x.zona)}</td><td>${badge(x.estado)}</td><td>${esc(fmtFecha(x.creado_en))}</td></tr>`).join('') + '</tbody></table>'
      : '<p class="vacio">Sin resultados (si el envio es muy reciente, el indice puede ir con unos segundos de retraso).</p>';
  } catch (err) { $('busqueda').innerHTML = `<div class="banner">${esc(err.message)}</div>`; }
});

(async () => { await intentar(async () => { const z = await cargarZonas($('f-zona'), true); }); $('f-estado').value = 'creado'; await refrescar(); estadoSync(); })();
