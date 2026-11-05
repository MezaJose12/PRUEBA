barra('seguimiento.html');
const out = document.getElementById('resultado'), input = document.getElementById('codigo');

async function consultar(codigo) {
  out.innerHTML = '';
  try {
    const { envio, eventos } = await api('/envios/' + encodeURIComponent(codigo.trim().toUpperCase()));
    let ev = '';
    if (envio.estado === 'entregado') {   // la evidencia vive en MongoDB; si no responde, el resto se sigue viendo
      try { const x = await api(`/envios/${envio.codigo}/evidencia`);
        ev = `<section><h2>Prueba de entrega</h2><dl class="datos"><dt>Recibido por</dt><dd>${esc(x.receptor)}</dd>
          <dt>Observacion</dt><dd>${esc(x.observacion || '-')}</dd></dl></section>`; }
      catch (e) { ev = `<div class="banner">Evidencia no disponible por ahora: ${esc(e.message)}</div>`; }
    }
    out.innerHTML = `<section><h2><span class="mono">${esc(envio.codigo)}</span> ${badge(envio.estado)}</h2>
      <p class="pista">Para ${esc(envio.destinatario)} - zona ${esc(envio.zona)}</p>${lineaDeTiempo(eventos)}</section>${ev}`;
  } catch (e) { aviso(e.status === 404 ? 'No existe un envio con ese codigo.' : e.message, 'error'); }
}
document.getElementById('f').addEventListener('submit', e => { e.preventDefault(); consultar(input.value); });
if (parametro('codigo')) { input.value = parametro('codigo'); consultar(input.value); }
