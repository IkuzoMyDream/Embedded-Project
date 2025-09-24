const API = {
  getDashboard: () => fetch('/api/dashboard').then(r=>r.json()),
  getLookup:    () => fetch('/api/lookup').then(r=>r.json()),
  addQueue:     (payload) =>
    fetch('/api/queues',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)}).then(r=>r.json()),
  addPatient:   (payload) =>
    fetch('/api/patients',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)}).then(r=>r.json()),
  deleteQueue:  (id) => fetch(`/api/queues/${id}`, {method:'DELETE'}).then(r=>r.json()),
};
