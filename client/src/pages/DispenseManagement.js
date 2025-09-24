import React, { useEffect, useState } from 'react'
import '../App.css'

const API = {
  getLookup:    () => fetch('/api/lookup').then(r=>r.json()),
  addQueue:     (payload) => fetch('/api/queues', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)}).then(r=>r.json()),
  addPatient:   (payload) => fetch('/api/patients', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)}).then(r=>r.json()),
}

export default function DispenseManagement(){
  const [lookup, setLookup] = useState({patients:[], pills:[]})
  const [patient, setPatient] = useState('')
  const [pill, setPill] = useState('')
  const [qty, setQty] = useState(1)
  const [items, setItems] = useState([])
  const [msg, setMsg] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(()=>{
    let mounted = true
    setLoading(true)
    API.getLookup().then(data=>{
      console.log('lookup:', data)
      if(!mounted) return
      setLookup(data || {patients:[],pills:[]})
      if(data && data.pills && data.pills.length) setPill(String(data.pills[0].id))
      if(data && data.patients && data.patients.length) setPatient(String(data.patients[0].id))
    }).catch(err=>{
      console.error('Failed to fetch lookup', err)
      setMsg('ไม่สามารถโหลดข้อมูลจากเซิร์ฟเวอร์')
    }).finally(()=>{ if(mounted) setLoading(false) })
    return ()=>{ mounted = false }
  },[])

  function addItem(){
    const p = lookup.pills.find(x=>String(x.id)===String(pill))
    if(!p) return setMsg('เลือกยาก่อน')
    const q = p.type==='liquid'?1:Math.max(1,parseInt(qty)||1)
    setItems(prev=>[...prev,{pill_id:p.id, name:p.name, type:p.type, quantity:q}])
  }

  function submit(){
    if(!patient) return setMsg('เลือกผู้ป่วย')
    if(!items || items.length===0) return setMsg('เลือกรายการยาก่อน')
    API.addQueue({patient_id:parseInt(patient), items}).then(r=>{
      if(r && r.error){
        setMsg('เกิดข้อผิดพลาด: '+r.error)
      } else {
        setMsg('บันทึกแล้ว: '+(r.queue_number||r.queue_id))
        setItems([])
      }
    }).catch(e=>{
      console.error(e)
      setMsg('บันทึกไม่สำเร็จ')
    })
  }

  return (
    <div className="container">
      <div className="header">
        <div className="header-left">
          <div className="brand">
            <div className="logo">SD</div>
            <div>
              <h1>จัดการคิว & สต็อกยา</h1>
              <div className="subtitle">สร้างคิวและสั่งจ่ายยาสำหรับผู้ป่วย</div>
            </div>
          </div>
        </div>
        <div className="nav">
          <div className="stickers-row">
            <div className="sticker-badge"><span className="emoji">💊</span><span className="text">ตู้ยา</span></div>
            <div className="sticker-badge"><span className="emoji">🩺</span><span className="text">แผนก</span></div>
          </div>
        </div>
      </div>

      <div className="card">
        <div className="card-header">
          <div>
            <div className="card-title">เลือกผู้ป่วยและยา</div>
            <div className="card-sub">เลือกรายการยาที่ต้องการจ่าย</div>
          </div>
        </div>

        <div className="row">
          <label>ผู้ป่วย</label>
          <select value={patient} onChange={e=>setPatient(e.target.value)}>
            <option value="">-- เลือก --</option>
            {lookup.patients.map(p=> <option key={p.id} value={String(p.id)}>{p.name}</option>)}
          </select>
        </div>

        <div className="row" style={{marginTop:8}}>
          <label>เลือกยา</label>
          <select value={pill} onChange={e=>setPill(e.target.value)}>
            <option value="">-- เลือก --</option>
            {lookup.pills.map(p=> <option key={p.id} value={String(p.id)}>{p.name}</option>)}
          </select>
          <input className="qty" type="number" min="1" value={qty} onChange={e=>setQty(e.target.value)} />
          <button className="btn" onClick={addItem}>เพิ่มเข้ารายการ</button>
        </div>
      </div>

      <div className="card">
        <div className="card-header">
          <div>
            <div className="card-title">รายการยา</div>
            <div className="card-sub">ตรวจสอบก่อนบันทึก</div>
          </div>
        </div>
        <table>
          <thead>
            <tr><th>ยา</th><th>ประเภท</th><th className="right">สต็อกคงเหลือ</th><th className="right">จำนวนที่จ่าย</th><th>ลบ</th></tr>
          </thead>
          <tbody>
            {items.map((it,idx)=> (
              <tr key={idx}>
                <td>{it.name}</td>
                <td>{it.type}</td>
                <td className="right">-</td>
                <td className="right">{it.quantity}</td>
                <td><button className="btn secondary" onClick={()=>setItems(items.filter((_,i)=>i!==idx))}>ลบ</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="card">
        <div className="card-header">
          <div>
            <div className="card-title">ดำเนินการ</div>
            <div className="card-sub">บันทึกหรือยกเลิกการทำรายการ</div>
          </div>
        </div>
        <div className="row" style={{justifyContent:'space-between', alignItems:'center'}}>
          <div>
            <button className="btn" onClick={submit}>บันทึกคิว</button>
            <button className="btn secondary" style={{marginLeft:8}} onClick={()=>{setItems([]); setMsg('')}}>ล้าง</button>
          </div>
          <div className="muted">{msg}</div>
        </div>
      </div>
    </div>
  )
}
