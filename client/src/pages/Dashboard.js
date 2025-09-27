import React, { useEffect, useState } from 'react'
import '../App.css'

const API = { getDashboard: () => fetch('/api/dashboard').then(r=>r.json()) }

export default function Dashboard(){
  const [current, setCurrent] = useState(null)
  const [success, setSuccess] = useState(0)
  const [logs, setLogs] = useState([])
  const [expanded, setExpanded] = useState({})
  const [pending, setPending] = useState([])
  const [processing, setProcessing] = useState([])
  const [served, setServed] = useState([])
  const [showPendingModalc, setShowPendingModal] = useState(false)

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

  useEffect(()=>{ poll(); const t=setInterval(poll,3000); return ()=>clearInterval(t) },[])

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

  return (
    <div className="container">
      <div className="header">
        <div className="header-left">
          <div className="brand">
            <div className="logo">SD</div>
            <div>
              <h1>แดชบอร์ด</h1>
              <div className="subtitle">ภาพรวมและเหตุการณ์ล่าสุด</div>
            </div>
          </div>
        </div>
        <div className="nav" style={{display:'flex',alignItems:'center',justifyContent:'space-between'}}>
          <div className="stickers-row">
            <div className="sticker-badge"><span className="emoji">🩺</span><span className="text">คลินิก</span></div>
            <div className="sticker-badge"><span className="emoji">💊</span><span className="text">ตู้ยา</span></div>
          </div>
          {/* เพิ่มแสดง Role ใน nav ตามหน้า */}
          <div style={{minWidth:160}}>
            <div className="card" style={{background:'#e3f2fd',color:'#1976d2',padding:'8px 16px',textAlign:'center',boxShadow:'0 2px 8px rgba(0,0,0,0.04)',fontSize:16}}>
              <span className="emoji" style={{fontSize:20,marginRight:6}}>👩‍⚕️</span>Role: พยาบาล
            </div>
          </div>
        </div>
      </div>

      {/* First row: summary/stat cards side by side */}
      <div style={{display:'flex',gap:24,margin:'24px 0'}}>
        {/* Card: คิวปัจจุบัน */}
        <div className="card" style={{flex:1,minWidth:220}}>
          <div className="card-header">
            <div>
              <div className="card-title">คิวปัจจุบัน</div>
              <div className="card-sub">คิวที่รอดำเนินการ / ส่งแล้ว</div>
            </div>
          </div>
          <div className="stat">
            <div className="value">{current ? `#${current.queue_number} — ${current.patient_name}` : '—'}</div>
            <div className="label">{current ? `Room: ${current.room} / ${current.status}` : 'No active queue'}</div>
          </div>
          <div className="card-footer">Updated: <span className="helper">auto</span></div>
        </div>
        {/* Card: กำลังดำเนินการ */}
        <div className="card" style={{flex:1,minWidth:220}}>
          <div className="card-header"><div><div className="card-title">กำลังดำเนินการ</div><div className="card-sub">อุปกรณ์กำลังทำงาน</div></div></div>
          <div style={{padding:12}}>
            <div style={{fontSize:22,fontWeight:800}}>{processing.length}</div>
            <div className="muted">คิวที่กำลังทำ</div>
            {processing.slice(0,3).map(p=> (
              <div key={p.queue_id} style={{marginTop:8}} className="muted">#{p.queue_number} — {p.patient_name}</div>
            ))}
          </div>
          <div className="card-footer"><span className="helper">อัปเดต</span></div>
        </div>
        {/* Card: คิวสั่งยา (คิวค้าง) */}
        <div className="card" style={{flex:1,minWidth:220}}>
          <div className="card-header"><div><div className="card-title">คิวสั่งยา</div><div className="card-sub">รอส่งไปยังอุปกรณ์</div></div></div>
          <div style={{padding:12}}>
            <div style={{fontSize:22,fontWeight:800}}>{pending.length}</div>
            <div className="muted">จำนวนคิวสั่งยา</div>
          </div>
          <div className="card-footer"><span className="helper">ล่าสุด</span></div>
        </div>
      </div>

      {/* Second row: recent served queues */}
      <div style={{margin:'24px 0'}}>
        <div className="card">
          <div className="card-header"><div><div className="card-title">คิวที่เสร็จ</div><div className="card-sub">รายการล่าสุดที่สถานะ success</div></div></div>
          <div style={{padding:8}}>
            {served.slice(0,8).map(s=> (
              <div key={s.queue_id} style={{padding:8,borderBottom:'1px solid rgba(0,0,0,0.04)'}}>
                <div style={{fontWeight:800}}>#{s.queue_number} — {s.patient_name}</div>
                <div className="muted">ห้อง {s.room} • {s.served_at || '-'}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* รายละเอียดของรายการสั่งยา (table ล่างสุด) */}
      <div className="col-12">
        <div className="card">
          <div className="card-header"><div><div className="card-title">รายละเอียดของรายการสั่งยา</div><div className="card-sub">ข้อมูลคิวสั่งยาทั้งหมด</div></div></div>
          <table>
            <thead>
              <tr>
                <th style={{width:80}}>คิว</th>
                <th>ผู้ป่วย</th>
                <th>ห้อง</th>
                <th>รายการยา</th>
                <th>สถานะ</th>
              </tr>
            </thead>
            <tbody>
              {pending.length === 0 ? (
                <tr><td colSpan={5} className="muted">ไม่มีรายการสั่งยา</td></tr>
              ) : (
                pending.map(p => (
                  <tr key={p.queue_id}>
                    <td>#{p.queue_number}</td>
                    <td>{p.patient_name}</td>
                    <td>{p.room}</td>
                    <td>
                      {Array.isArray(p.items) && p.items.length > 0 ? (
                        <ul style={{margin:0,paddingLeft:18}}>
                          {p.items.map((it,idx) => (
                            <li key={idx}>{it.name || `ID:${it.pill_id}`} × {it.quantity}</li>
                          ))}
                        </ul>
                      ) : (
                        <span className="muted">ไม่มีข้อมูลรายการยา</span>
                      )}
                    </td>
                    <td>{p.status || '-'}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      <div className="footer">Smart Dispense — สถานะและบันทึก</div>
    </div>
  )
}
