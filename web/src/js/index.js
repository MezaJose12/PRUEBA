barra('index.html');
const zona = document.getElementById('zona');
intentar(() => cargarZonas(zona));
intentar(async () => {   // los tipos de servicio los mantiene el administrador
  const tipos = await api('/tipos-servicio');
  document.getElementById('tipo').innerHTML = tipos.map(t => `<option value="${esc(t.nombre)}">${esc(t.nombre)}</option>`).join('');
});

document.getElementById('f').addEventListener('submit', async e => {
  e.preventDefault();
  const btn = document.getElementById('enviar'); btn.disabled = true;   // evita doble clic
  const d = Object.fromEntries(new FormData(e.target)); d.zona_id = Number(d.zona_id);
  const envio = await intentar(() => api('/envios', { method: 'POST', body: d }), 'Envio registrado');
  btn.disabled = false;
  if (!envio) return;
  document.getElementById('comprobante').innerHTML = `<div class="comprobante">
    <div class="pista">Comprobante de envio</div><div class="codigo mono">${esc(envio.codigo)}</div>
    <dl class="datos"><dt>Estado</dt><dd>${badge(envio.estado)}</dd><dt>Destinatario</dt><dd>${esc(envio.destinatario)}</dd>
    <dt>Servicio</dt><dd>${esc(envio.tipo_servicio)}</dd><dt>Registrado</dt><dd>${esc(fmtFecha(envio.creado_en))}</dd></dl>
    <p><a href="seguimiento.html?codigo=${encodeURIComponent(envio.codigo)}">Ver seguimiento</a></p></div>`;
  e.target.reset();
});
