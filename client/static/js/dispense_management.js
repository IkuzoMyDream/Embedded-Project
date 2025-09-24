// Helpers
const unitFor = t => t === 'liquid' ? 'ลิตร' : 'เม็ด';
const Q = s => document.querySelector(s);
let LOOKUP = {patients:[], pills:[]};
let ITEMS = []; // [{pill_id,name,type,amount,quantity}]

// ---- API calls used here ----
const API = {
  lookup:    () => fetch('/api/lookup').then(r=>r.json()),
  addQueue:  (payload) => fetch('/api/queues',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)}).then(r=>r.json()),
  // stock management:
  listPills: () => fetch('/api/pills').then(r=>r.json()),
  addPill:   (d) => fetch('/api/pills',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(d)}).then(r=>r.json()),
  patchPill: (id, d) => fetch(`/api/pills/${id}`,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify(d)}).then(r=>r.json()),
  delPill:   (id) => fetch(`/api/pills/${id}`,{method:'DELETE'}).then(r=>r.json()),
};

// ---- Render queue items ----
function renderItems(){
  const tb = Q('#itemsTbl tbody');
  tb.innerHTML = ITEMS.map((it, i)=>{
    const qtyCell = it.type === 'liquid'
      ? `<input type="number" class="qty" value="1" min="1" disabled>`
      : `<input type="number" class="qty qty-edit" data-i="${i}" value="${it.quantity}" min="1">`;
    return `<tr>
      <td>${it.name}</td>
      <td>${it.type==='liquid'?'ยาน้ำ':'ยาเม็ด'}</td>
      <td class="right">${it.amount} ${unitFor(it.type)}</td>
      <td class="right">${qtyCell}</td>
      <td><button class="btn del" data-i="${i}">ลบ</button></td>
    </tr>`;
  }).join('');

  tb.querySelectorAll('.del').forEach(b=> b.onclick = e=>{
    ITEMS.splice(+e.currentTarget.dataset.i, 1);
    renderItems();
  });
  tb.querySelectorAll('.qty-edit').forEach(inp=> inp.oninput = e=>{
    const i = +e.currentTarget.dataset.i;
    const v = Math.max(1, parseInt(e.currentTarget.value||'1',10));
    ITEMS[i].quantity = v;
  });
}

// ---- Render stock table ----
async function renderStock(){
  const pills = await API.listPills(); // [{id,name,type,amount}]
  LOOKUP.pills = pills; // sync for selects
  fillSelects();        // refresh selects with amounts

  const tb = Q('#stockTbl tbody');
  tb.innerHTML = pills.map(p=>`
    <tr>
      <td>${p.name}</td>
      <td>${p.type==='liquid'?'ยาน้ำ':'ยาเม็ด'}</td>
      <td class="right"><b>${p.amount}</b> ${unitFor(p.type)}</td>
      <td class="right">
        <input type="number" class="qty adj" data-id="${p.id}" placeholder="+/- จำนวน">
        <button class="btn do-adj" data-id="${p.id}">บันทึก</button>
      </td>
      <td><button class="btn danger del-pill" data-id="${p.id}">ลบ</button></td>
    </tr>
  `).join('');

  tb.querySelectorAll('.do-adj').forEach(btn=> btn.onclick = async e=>{
    const id = +e.currentTarget.dataset.id;
    const inp = tb.querySelector(`.adj[data-id="${id}"]`);
    const delta = parseInt(inp.value||'0', 10);
    if(!delta) return;
    await API.patchPill(id, { delta });
    await renderStock();
  });

  tb.querySelectorAll('.del-pill').forEach(btn=> btn.onclick = async e=>{
    const id = +e.currentTarget.dataset.id;
    if(!confirm('ลบยานี้?')) return;
    await API.delPill(id);
    await renderStock();
  });
}

// ---- Fill selects ----
function fillSelects(){
  // patients
  Q('#patient').innerHTML = LOOKUP.patients
    .map(p=>`<option value="${p.id}">${p.name}</option>`).join('');
  // pills (show amount & unit)
  Q('#pill').innerHTML = LOOKUP.pills
    .map(p=>`<option value="${p.id}" data-type="${p.type}" data-name="${p.name}" data-amount="${p.amount}">
      ${p.name} — คงเหลือ ${p.amount} ${unitFor(p.type)}
    </option>`).join('');
}

// ---- Page init ----
async function init(){
  try{
    LOOKUP = await API.lookup();  // {patients, pills, rooms}
  }catch(e){
    Q('#msg').innerHTML = '<span class="danger">โหลดข้อมูลล้มเหลว /api/lookup</span>';
    return;
  }
  fillSelects();
  renderItems();
  await renderStock();
}
init();

// ---- Event bindings (Queue) ----
Q('#addItemBtn').onclick = ()=>{
  const sel = Q('#pill'); const opt = sel.selectedOptions[0]; if(!opt) return;
  const pill_id = +opt.value;
  const name = opt.dataset.name;
  const type = opt.dataset.type;
  const amount = +opt.dataset.amount;
  let quantity = Math.max(1, parseInt(Q('#qty').value||'1',10));
  if(type==='liquid'){ quantity = 1; Q('#qty').value = 1; Q('#qty').disabled = true; }
  else { Q('#qty').disabled = false; }

  const exist = ITEMS.find(x=> x.pill_id === pill_id);
  if(exist){
    if(type!=='liquid') exist.quantity = quantity;
  }else{
    ITEMS.push({pill_id, name, type, amount, quantity});
  }
  renderItems();
};

Q('#submitQueueBtn').onclick = async ()=>{
  if(!ITEMS.length){ Q('#msg').innerHTML = '<span class="danger">กรุณาเพิ่มรายการยา</span>'; return; }
  const patient_id = +Q('#patient').value;
  const payload = {
    patient_id,
    items: ITEMS.map(x=>({pill_id:x.pill_id, quantity: x.type==='liquid'?1:x.quantity}))
  };
  const res = await API.addQueue(payload);
  if(res.error){
    Q('#msg').innerHTML = `<span class="danger">ผิดพลาด: ${res.error}</span>`;
  }else{
    Q('#msg').innerHTML = `<span class="success">สร้างคิว #${res.queue_number} (ห้อง ${res.target_room}) สำเร็จ</span>`;
    ITEMS = []; renderItems();
  }
};

// ---- Stock: add pill ----
Q('#addPillBtn').onclick = async ()=>{
  const name = Q('#newPillName').value.trim();
  const type = Q('#newPillType').value;
  const amount = Math.max(0, parseInt(Q('#newPillAmount').value||'0',10));
  if(!name) return;
  await API.addPill({ name, type, amount });
  Q('#newPillName').value = ''; Q('#newPillAmount').value = '0';
  await renderStock();
};
