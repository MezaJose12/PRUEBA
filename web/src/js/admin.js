barra('admin.html');
const $ = id => document.getElementById(id);

async function zonas() {
  const z = await api('/zonas');
  $('zonas').innerHTML = `<table><thead><tr><th>Id</th><th>Nombre</th><th>Acciones</th></tr></thead><tbody>` +
    z.map(x => `<tr><td>${x.id}</td><td>${esc(x.nombre)}</td><td><button class="chico sec" data-renombrar="${x.id}" data-nombre="${esc(x.nombre)}">Renombrar</button></td></tr>`).join('') + '</tbody></table>';
}
async function reps() {
  const r = await api('/repartidores');
  $('reps').innerHTML = `<table><thead><tr><th>Id</th><th>Nombre</th><th>Capacidad</th><th>Carga</th><th>Activo</th><th>Acciones</th></tr></thead><tbody>` +
    r.map(x => `<tr><td>${x.id}</td><td>${esc(x.nombre)}</td><td>${x.capacidad_max}</td><td>${x.carga_actual}</td><td>${x.activo ? 'Si' : 'No'}</td>
      <td class="acciones"><button class="chico sec" data-cap="${x.id}" data-actual="${x.capacidad_max}">Cambiar capacidad</button>
      <button class="chico sec" data-activo="${x.id}" data-valor="${x.activo}">${x.activo ? 'Desactivar' : 'Activar'}</button></td></tr>`).join('') + '</tbody></table>';
}
async function tipos() {
  const t = await api('/tipos-servicio?todos=true');
  $('tipos').innerHTML = `<table><thead><tr><th>Id</th><th>Nombre</th><th>Activo</th><th>Acciones</th></tr></thead><tbody>` +
    t.map(x => `<tr><td>${x.id}</td><td>${esc(x.nombre)}</td><td>${x.activo ? 'Si' : 'No'}</td><td class="acciones">
      <button class="chico sec" data-tren="${x.id}" data-nombre="${esc(x.nombre)}">Renombrar</button>
      <button class="chico sec" data-tact="${x.id}" data-valor="${x.activo}">${x.activo ? 'Desactivar' : 'Activar'}</button></td></tr>`).join('') + '</tbody></table>';
}
const todo = () => intentar(async () => { await zonas(); await tipos(); await reps(); });
$('ft').addEventListener('submit', async e => { e.preventDefault();
  if (await intentar(() => api('/tipos-servicio', { method: 'POST', body: { nombre: e.target.nombre.value } }), 'Tipo de servicio creado')) { e.target.reset(); todo(); } });
$('tipos').addEventListener('click', async ev => { const b = ev.target.closest('button'); if (!b) return; const d = b.dataset;
  if (d.tren) { const n = prompt('Nuevo nombre:', d.nombre); if (!n) return;
    await intentar(() => api('/tipos-servicio/' + d.tren, { method: 'PATCH', body: { nombre: n } }), 'Tipo actualizado'); }
  if (d.tact) await intentar(() => api('/tipos-servicio/' + d.tact, { method: 'PATCH', body: { activo: d.valor !== 'true' } }), 'Tipo actualizado');
  todo(); });

$('fz').addEventListener('submit', async e => { e.preventDefault();
  if (await intentar(() => api('/zonas', { method: 'POST', body: { nombre: e.target.nombre.value } }), 'Zona creada')) { e.target.reset(); todo(); } });
$('fr').addEventListener('submit', async e => { e.preventDefault();
  const b = { nombre: e.target.nombre.value, capacidad_max: Number(e.target.capacidad_max.value) };
  if (await intentar(() => api('/repartidores', { method: 'POST', body: b }), 'Repartidor creado')) { e.target.reset(); todo(); } });

$('zonas').addEventListener('click', async ev => { const b = ev.target.closest('button'); if (!b) return;
  const n = prompt('Nuevo nombre de la zona:', b.dataset.nombre); if (!n) return;
  await intentar(() => api('/zonas/' + b.dataset.renombrar, { method: 'PATCH', body: { nombre: n } }), 'Zona actualizada'); todo(); });
$('reps').addEventListener('click', async ev => { const b = ev.target.closest('button'); if (!b) return; const d = b.dataset;
  if (d.cap) { const n = Number(prompt('Nueva capacidad maxima:', d.actual)); if (!n) return;
    await intentar(() => api('/repartidores/' + d.cap, { method: 'PATCH', body: { capacidad_max: n } }), 'Capacidad actualizada'); }
  if (d.activo) await intentar(() => api('/repartidores/' + d.activo, { method: 'PATCH', body: { activo: d.valor !== 'true' } }), 'Repartidor actualizado');
  todo(); });
todo();
