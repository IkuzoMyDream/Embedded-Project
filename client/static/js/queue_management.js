async function loadLookup(){
  const d = await API.getLookup();
  const pSel = document.getElementById('patient');
  const pillSel = document.getElementById('pill');
  pSel.innerHTML = d.patients.map(p=>`<option value="${p.id}">${p.name}</option>`).join('');
  pillSel.innerHTML = d.pills.map(p=>`<option value="${p.id}">${p.name} (${p.type})</option>`).join('');
}
document.getElementById('addQueueBtn').onclick = async () => {
  const patient_id = +document.getElementById('patient').value;
  const pill_id = +document.getElementById('pill').value;
  const res = await API.addQueue({patient_id, pill_id});
  document.getElementById('msg').textContent = `Queued #${res.queue_id} → room ${res.target_room}`;
};
document.getElementById('addPatientBtn').onclick = async () => {
  const name = prompt('Patient name?'); if(!name) return;
  await API.addPatient({name});
  await loadLookup();
};
loadLookup();
