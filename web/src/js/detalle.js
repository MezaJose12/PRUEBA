barra('detalle.html');
const out = document.getElementById('resultado'), input = document.getElementById('codigo');

async function ver(codigo) {
  out.innerHTML = '';
  try {
    const d = await api('/envios/' + encodeURIComponent(codigo.trim().toUpperCase()));
    const e = d.envio;
    let evid = '<p class="vacio">Sin evidencia registrada.</p>';
    try { const x = await api(`/envios/${e.codigo}/evidencia`);
      evid = `<dl class="datos"><dt>Receptor</dt><dd>${esc(x.receptor)}</dd><dt>Observacion</dt><dd>${esc(x.observacion || '-')}</dd>
        <dt>Foto (URL)</dt><dd>${esc(x.foto_url || '-')}</dd><dt>Registrada</dt><dd>${esc(fmtFecha(x.registrada_en))} por ${esc(x.actor)}</dd></dl>`;
    } catch (err) { if (err.status !== 404) evid = `<div class="banner">${esc(err.message)}</div>`; }
    out.innerHTML = `<section><h2><span class="mono">${esc(e.codigo)}</span> ${badge(e.estado)}</h2>
      <dl class="datos"><dt>Remitente</dt><dd>${esc(e.remitente)}</dd><dt>Destinatario</dt><dd>${esc(e.destinatario)}</dd>
      <dt>Origen</dt><dd>${esc(e.origen)}</dd><dt>Destino</dt><dd>${esc(e.destino)}</dd>
      <dt>Servicio / zona</dt><dd>${esc(e.tipo_servicio)} / ${esc(e.zona)}</dd>
      <dt>Repartidor</dt><dd>${d.asignacion ? esc(d.asignacion.repartidor) + (d.asignacion.aceptada_en ? ' (acepto la asignacion)' : ' (pendiente de aceptar)') : 'Sin asignar'}</dd>
      <dt>Historial coherente</dt><dd>${d.consistente ? 'Si: el estado coincide con el ultimo evento' : 'NO - revisar'}</dd></dl></section>
      <section><h2>Historial</h2>${lineaDeTiempo(d.eventos)}</section><section><h2>Prueba de entrega</h2>${evid}</section>`;
  } catch (err) { aviso(err.status === 404 ? 'No existe un envio con ese codigo.' : err.message, 'error'); }
}
document.getElementById('f').addEventListener('submit', e => { e.preventDefault(); ver(input.value); });
if (parametro('codigo')) { input.value = parametro('codigo'); ver(input.value); }
