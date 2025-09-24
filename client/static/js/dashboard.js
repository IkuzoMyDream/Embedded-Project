async function refresh(){
  const d = await API.getDashboard();
  const cur = d.current ?
    `#${d.current.queue_id} — ${d.current.patient_name} → ${d.current.room} (${d.current.status})`
    : '—';
  document.getElementById('current').textContent = cur;
  document.getElementById('success').textContent = d.success_count ?? 0;

  const lines = (d.logs||[]).map(x=>`[${x.ts}] q=${x.queue_id||'-'} ${x.event} ${x.message||''}`);
  document.getElementById('logs').textContent = lines.join('\n');
}
refresh();
setInterval(refresh, 1500);
