import React, { useEffect, useState } from 'react'
import '../App.css'

const API = {
  getDashboard: () => fetch('/api/dashboard').then(r=>r.json()),
  getPills: () => fetch('/api/pills').then(r=>r.json()),
  deleteQueue: (id) => fetch(`/api/queues/${id}`, { method: 'DELETE' })
}

export default function Dashboard(){
  const [current, setCurrent] = useState(null)
  const [success, setSuccess] = useState(0)
  const [logs, setLogs] = useState([])
  const [expanded, setExpanded] = useState({})
  const [pending, setPending] = useState([])
  const [processing, setProcessing] = useState([])
  const [served, setServed] = useState([])
  const [showPendingModalc, setShowPendingModal] = useState(false)
  const [showDrugModal, setShowDrugModal] = useState(false);
  const [drugList, setDrugList] = useState([]);
  const [pills, setPills] = useState([]); // เก็บข้อมูลยาเดิม

  function poll(){
    API.getDashboard().then(d=>{
      setCurrent(d.current)
      setLogs(d.logs||[])
      setSuccess(d.success_count||0)
      setPending(d.pending || [])
      setProcessing(d.processing || [])
      setServed(d.served || [])
      console.log("pending queues:", d.pending)
    }).catch(console.error)
  }

  useEffect(()=>{ 
    poll(); 
    API.getPills().then(setPills).catch(()=>{}); // โหลดข้อมูลยาเดิม
    const t=setInterval(poll,3000); 
    return ()=>clearInterval(t) 
  },[])

  function toggleExpand(id){
    setExpanded(prev => ({...prev, [id]: !prev[id]}))
  }

  function renderMessage(msg){
    if(!msg) return ''
    try{
      const j = typeof msg === 'string' ? JSON.parse(msg) : msg
      // prettify known shapes
      if(j.items && Array.isArray(j.items)){
        // รวมรายการที่ชื่อเดียวกัน
        const merged = {}
        j.items.forEach(it => {
          const name = it.name || `ID:${it.pill_id}`
          if(!merged[name]) merged[name] = 0
          merged[name] += it.quantity
        })
        // แสดงแต่ละรายการยาแยกบรรทัด
        return Object.entries(merged)
          .map(([name, qty]) => `${name} × ${qty}`)
          .join('\n')
      }
      if(j.patient_id){
        return `patient:${j.patient_id}` + (j.items? ' items:'+ (Array.isArray(j.items)? j.items.length : '') : '')
      }
      return typeof j === 'object' ? JSON.stringify(j) : String(j)
    }catch(e){
      return String(msg)
    }
  }

  async function saveDrugListToDB() {
    try {
      const res = await fetch('/api/drugs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ drugs: drugList })
      });
      if (res.ok) {
        alert('บันทึกข้อมูลยาเรียบร้อยแล้ว');
        setShowDrugModal(false);
        // reload pills หลังบันทึกสำเร็จ
        const pillsData = await API.getPills();
        setPills(pillsData);
      } else {
        alert('เกิดข้อผิดพลาดในการบันทึกข้อมูลยา');
      }
    } catch (e) {
      alert('ไม่สามารถเชื่อมต่อเซิร์ฟเวอร์ได้');
    }
  }

  return (
    <div className="container">
      
      {/* <div style={{minWidth:160, marginBottom:16, display:'flex', justifyContent:'flex-end'}}>
            <div className="card" style={{background:'#e3f2fd',color:'#1976d2',padding:'8px 16px',textAlign:'center',boxShadow:'0 2px 8px rgba(0,0,0,0.04)',fontSize:16}}>
              <span className="emoji" style={{fontSize:20,marginRight:6}}>👩‍⚕️</span>Role: พยาบาล
            </div>
          </div> */}
      {/* First row: summary/stat cards side by side */}
      <div style={{display:'flex',gap:24,margin:'24px 0'}}>
        {/* Card: คิวปัจจุบัน */}
        <div className="card" style={{flex:1,minWidth:220, display:'flex', flexDirection:'column', justifyContent:'flex-start', alignItems:'stretch', padding:'0', boxShadow:'0 2px 8px rgba(25,118,210,0.07)'}}>
          <div className="card-header" style={{background:'#e3f2fd', color:'#1976d2', padding:'12px 20px', borderTopLeftRadius:8, borderTopRightRadius:8}}>
            <div className="card-title" style={{fontSize:18, fontWeight:800, letterSpacing:1}}>คิวปัจจุบัน</div>
            <div className="card-sub" style={{fontSize:14, color:'#1976d2', opacity:0.7}}>คิวที่รอดำเนินการ</div>
          </div>
            <div style={{display:'flex', alignItems:'center', width:'100%', padding:'20px 20px 8px 20px'}}>
            <div style={{fontSize:38, fontWeight:900, color:'#1976d2', minWidth:70, textAlign:'center', letterSpacing:1}}>
              {current ? `#${current.queue_number}` : '—'}
            </div>
            <div style={{borderLeft:'3px solid #1976d2', height:48, margin:'0 16px'}}></div>
            <div style={{flex:1}}>
              <div style={{fontSize:18, fontWeight:700}}>{current ? current.patient_name : ''}</div>
              <div className="muted" style={{fontSize:15}}>{current ? `Room: ${current.room}` : ''}</div>
              <div className="muted" style={{fontSize:15}}>{current ? (current.status || '-') : ''}</div>
            </div>
          </div>
        </div>
        {/* Card: คิวที่เสร็จสิ้นแล้ว */}
        <div className="card" style={{flex:1,minWidth:220, display:'flex', flexDirection:'column', justifyContent:'flex-start', alignItems:'stretch', padding:'0', boxShadow:'0 2px 8px rgba(76,175,80,0.07)'}}>
          <div className="card-header" style={{background:'#e8f5e9', color:'#388e3c', padding:'12px 20px', borderTopLeftRadius:8, borderTopRightRadius:8, borderBottom:'1px solid #c8e6c9'}}>
            <div className="card-title" style={{fontSize:18, fontWeight:800, letterSpacing:1}}>คิวที่เสร็จสิ้นแล้ว</div>
            <div className="card-sub" style={{fontSize:14, color:'#388e3c', opacity:0.7}}>จำนวนคิวที่ดำเนินการเสร็จ</div>
          </div>
          <div style={{padding:'32px 20px 16px 20px', textAlign:'center'}}>
            <div style={{fontSize:32, fontWeight:900, color:'#388e3c'}}>{served.length}</div>
            <div className="muted" style={{fontSize:15}}>คิวที่เสร็จสิ้นแล้ว</div>
          </div>
          <div className="card-footer" style={{marginTop:8, padding:'8px 20px', borderTop:'1px solid #c8e6c9', color:'#388e3c', fontSize:13}}><span className="helper">อัปเดต</span></div>
        </div>
        {/* Card: คิวสั่งยา (คิวค้าง) */}
        <div className="card" style={{flex:1,minWidth:220, display:'flex', flexDirection:'column', justifyContent:'flex-start', alignItems:'stretch', padding:'0', boxShadow:'0 2px 8px rgba(255,235,59,0.07)'}}>
          <div className="card-header" style={{background:'#fffde7', color:'#fbc02d', padding:'12px 20px', borderTopLeftRadius:8, borderTopRightRadius:8, borderBottom:'1px solid #fff9c4'}}>
            <div className="card-title" style={{fontSize:18, fontWeight:800, letterSpacing:1}}>คิวสั่งยา</div>
            <div className="card-sub" style={{fontSize:14, color:'#d6a11cff', opacity:0.7}}>รอส่งไปยังอุปกรณ์</div>
          </div>
          <div style={{padding:'32px 20px 16px 20px', textAlign:'center'}}>
            <div style={{fontSize:32, fontWeight:900, color:'#fbc02d'}}>{pending.length}</div>
            <div className="muted" style={{fontSize:15}}>จำนวนคิวสั่งยา</div>
          </div>
          <div className="card-footer" style={{marginTop:8, padding:'8px 20px', borderTop:'1px solid #fff9c4', color:'#b89c3b', fontSize:13}}><span className="helper">ล่าสุด</span></div>
        </div>
      </div>

      {/* รายละเอียดของรายการสั่งยา (table ล่างสุด) */}
      <div className="col-12">
        <h2 style={{fontSize: '1.5rem', fontWeight: 800, margin: '16px 0 8px 0', color: '#1976d2', letterSpacing: 1}}>รายละเอียดของรายการสั่งยา</h2>
        <button onClick={async () => {
        // ดึงข้อมูลยาเดิมจาก pills (มี id)
        let pillData = pills;
        // fallback ถ้า pills ยังไม่โหลด ให้ fetch ทันที
        if (!pillData || pillData.length === 0) {
          pillData = await API.getPills();
          setPills(pillData);
        }
        // map เป็น drugList ที่มี id, name, type, quantity
        setDrugList(pillData.map(p => ({
          id: p.id,
          name: p.name,
          type: p.type,
          quantity: p.amount
        })));
        setShowDrugModal(true);
      }}
      style={{marginBottom:12, background:'#1976d2', color:'#fff', border:'none', borderRadius:6, padding:'8px 18px', fontWeight:700, fontSize:16, cursor:'pointer', boxShadow:'0 2px 8px rgba(25,118,210,0.07)'}}>รายละเอียดยาทั้งหมด</button>
  {/* Modal รายละเอียดยา (แก้ไข/ลบ/เพิ่มได้) */}
  {showDrugModal && (
    <div style={{position:'fixed', top:0, left:0, width:'100vw', height:'100vh', background:'rgba(0,0,0,0.25)', zIndex:1000, display:'flex', alignItems:'center', justifyContent:'center'}}>
      <div style={{background:'#fff', borderRadius:10, minWidth:340, maxWidth:540, padding:24, boxShadow:'0 4px 24px rgba(0,0,0,0.15)'}}>
        <h3 style={{marginTop:0, color:'#1976d2'}}>รายละเอียดยาทั้งหมด</h3>
        <table style={{width:'100%', borderCollapse:'collapse'}}>
          <thead>
            <tr style={{background:'#e3f2fd'}}>
              <th style={{padding:'6px 8px', textAlign:'left'}}>ชื่อ</th>
              <th style={{padding:'6px 8px', textAlign:'left'}}>ชนิด</th>
              <th style={{padding:'6px 8px', textAlign:'right'}}>จำนวน</th>
              <th style={{padding:'6px 8px'}}></th>
            </tr>
          </thead>
          <tbody>
            {drugList.length === 0 ? (
              <tr><td colSpan={4} className="muted">ไม่มีข้อมูลยา</td></tr>
            ) : drugList.map((d, i) => (
              <tr key={d.id || i}>
                <td style={{padding:'6px 8px'}}>
                  <input value={d.name} onChange={e => {
                    const newList = [...drugList];
                    newList[i] = {...newList[i], name: e.target.value};
                    setDrugList(newList);
                  }} style={{width:'100%', padding:'4px 6px', fontSize:15}} />
                </td>
                <td style={{padding:'6px 8px'}}>
                  <select value={d.type} onChange={e => {
                    const newList = [...drugList];
                    newList[i] = {...newList[i], type: e.target.value};
                    setDrugList(newList);
                  }} style={{width:'100%', padding:'4px 6px', fontSize:15}}>
                    <option value="solid">solid</option>
                    <option value="liquid">liquid</option>
                  </select>
                </td>
                <td style={{padding:'6px 8px', textAlign:'right'}}>
                  <input type="number" min={0} value={d.quantity} onChange={e => {
                    const newList = [...drugList];
                    newList[i] = {...newList[i], quantity: Number(e.target.value)};
                    setDrugList(newList);
                  }} style={{width:60, padding:'4px 6px', fontSize:15, textAlign:'right'}} />
                </td>
                <td style={{padding:'6px 8px', textAlign:'center'}}>
                  <button onClick={() => {
                    const newList = drugList.filter((_, idx) => idx !== i);
                    setDrugList(newList);
                  }} style={{background:'#e53935', color:'#fff', border:'none', borderRadius:4, padding:'4px 10px', fontWeight:700, fontSize:15, cursor:'pointer'}}>ลบ</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <div style={{margin:'12px 0 0 0', textAlign:'left'}}>
          <button onClick={() => setDrugList([...drugList, { name: '', type: '', quantity: 0 }])} style={{background:'#43a047', color:'#fff', border:'none', borderRadius:6, padding:'6px 16px', fontWeight:700, fontSize:15, cursor:'pointer'}}>+ เพิ่มยา</button>
        </div>
        <div style={{textAlign:'right', marginTop:18, display:'flex', gap:8, justifyContent:'flex-end'}}>
          <button onClick={()=>setShowDrugModal(false)} style={{background:'#888', color:'#fff', border:'none', borderRadius:6, padding:'6px 18px', fontWeight:700, fontSize:15, cursor:'pointer'}}>ปิด</button>
          <button onClick={saveDrugListToDB} style={{background:'#1976d2', color:'#fff', border:'none', borderRadius:6, padding:'6px 18px', fontWeight:700, fontSize:15, cursor:'pointer'}}>บันทึก</button>
        </div>
      </div>
    </div>
  )}
        <div className="card">
          <div className="card-header"><div><div className="card-title">รายละเอียดของรายการสั่งยา</div><div className="card-sub">ข้อมูลคิวสั่งยาทั้งหมด</div></div></div>
          <div style={{overflowX:'auto', maxHeight:400}}>
            <table>
              <thead>
                <tr>
                  <th style={{width:80}}>คิว</th>
                  <th>ผู้ป่วย</th>
                  <th>ห้อง</th>
                  <th>รายการยา</th>
                  <th>สถานะ</th>
                  <th>เสร็จเมื่อ</th>
                  <th style={{width:110}}>การกระทำ</th>
                </tr>
              </thead>
              <tbody>
                {(() => {
                  // รวมทุกคิว (pending, processing, served) แล้วเรียงตาม queue_number
                  const queueMap = {};
                  [...pending, ...processing, ...(served||[])].forEach(q => {
                    const key = q.queue_id || q.queue_number;
                    queueMap[key] = q; // overwrite with latest occurrence
                  });
                  const allQueues = Object.values(queueMap).sort((a, b) => {
                    const na = parseInt(a.queue_number||a.queue_id||0)
                    const nb = parseInt(b.queue_number||b.queue_id||0)
                    return na - nb
                  });
                  if (allQueues.length === 0) {
                    return <tr><td colSpan={7} className="muted">ไม่มีรายการสั่งยา</td></tr>
                  }
                  return allQueues.map(q => {
                    let rowStyle = {};
                    if (q.status === 'pending') rowStyle = { background: '#ffe082' } // dark yellow
                    else if (q.status === 'in_progress') rowStyle = { background: '#ffcc80' } // orange
                    else if (served.includes(q)) rowStyle = { background: '#e8f5e9' } // green for served
                    return (
                      <tr key={q.queue_id} style={rowStyle}>
                        <td>#{q.queue_number}</td>
                        <td>{q.patient_name}</td>
                        <td>{q.room}</td>
                        <td>
                          {Array.isArray(q.items) && q.items.length > 0 ? (
                            <ul style={{margin:0,paddingLeft:18}}>
                              {q.items.map((it,idx) => (
                                <li key={idx}>{it.name || `ID:${it.pill_id}`} × {it.quantity}</li>
                              ))}
                            </ul>
                          ) : (
                            <span className="muted">ไม่มีข้อมูลรายการยา</span>
                          )}
                        </td>
                        <td>{q.status || '-'}</td>
                        <td>{q.served_at || '-'}</td>
                        <td style={{textAlign:'center'}}>
                          <button
                            onClick={async () => {
                              if (!confirm(`ยืนยันการลบคิว #${q.queue_number || q.queue_id}?`)) return;
                              try {
                                const res = await API.deleteQueue(q.queue_id);
                                if (res.ok) {
                                  alert('ลบคิวเรียบร้อย');
                                  poll();
                                } else {
                                  const txt = await res.text();
                                  alert('ลบไม่สำเร็จ: ' + txt);
                                }
                              } catch (e) {
                                alert('ไม่สามารถเชื่อมต่อเซิร์ฟเวอร์ได้');
                              }
                            }}
                            disabled={q.status === 'in_progress'}
                            style={{background:'#e53935', color:'#fff', border:'none', borderRadius:6, padding:'6px 12px', fontWeight:700, cursor: q.status === 'in_progress' ? 'not-allowed' : 'pointer'}}
                          >ลบ</button>
                        </td>
                      </tr>
                    )
                  })
                })()}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <div className="footer">Smart Dispense — สถานะและบันทึก</div>
    </div>
  )
}
