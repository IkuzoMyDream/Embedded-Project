import React, { useEffect, useState } from 'react'
import '../App.css'

const API = {
  getLookup:    () => fetch('/api/lookup').then(r=>r.json()),
  addQueue:     (payload) => fetch('/api/queues', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)}).then(r=>r.json()),
  addPatient:   (payload) => fetch('/api/patients', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)}).then(r=>r.json())
}

export default function DispenseManagement(){
  const [lookup, setLookup] = useState({patients:[], pills:[]})
  const [patient, setPatient] = useState('')
  const [quantities, setQuantities] = useState({})
  const [items, setItems] = useState([])
  const [msg, setMsg] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(()=>{
    let mounted = true
    setLoading(true)
    API.getLookup().then(data=>{
      if(!mounted) return
      setLookup(data || {patients:[],pills:[]})
      // initialize patient and per-pill quantities
      if(data && data.patients && data.patients.length) setPatient(String(data.patients[0].id))
      const q = {}
      if(data && data.pills) data.pills.forEach(p=>{ q[String(p.id)] = 1 })
      setQuantities(q)
    }).catch(err=>{
      console.error('Failed to fetch lookup', err)
      setMsg('ไม่สามารถโหลดข้อมูลจากเซิร์ฟเวอร์')
    }).finally(()=>{ if(mounted) setLoading(false) })
    return ()=>{ mounted = false }
  },[])

  function setQty(pillId, val){
    setQuantities(prev=>({ ...prev, [String(pillId)]: Math.max(0, parseInt(val)||0) }))
  }

  function incQty(pillId, delta=1){
    setQuantities(prev=>{
      const cur = Math.max(0, parseInt(prev[String(pillId)]||0))
      return { ...prev, [String(pillId)]: cur + delta }
    })
  }

  function getStockFor(pill){
    if(!pill) return null
    // Prefer `amount` column from pills table, fallback to other common names
    const v = pill.amount ?? pill.stock ?? pill.qty ?? pill.quantity
    if (v === undefined || v === null) return null
    return Number(v) || 0
  }

  function getReserved(pillId){
    return items.filter(it=>String(it.pill_id)===String(pillId)).reduce((s,i)=>s + (parseInt(i.quantity)||0), 0)
  }

  function addItem(pillId){
    const p = lookup.pills.find(x=>String(x.id)===String(pillId))
    if(!p) return setMsg('ไม่พบยา')
    const q = Math.max(1, parseInt(quantities[String(pillId)]||1))
    const stock = getStockFor(p)
    const reserved = getReserved(pillId)
    const available = (stock === null) ? Infinity : (stock - reserved)
    if(stock !== null && q > available) return setMsg('จำนวนมากกว่าสต็อกคงเหลือ')
    setItems(prev=>[...prev,{pill_id:p.id, name:p.name, type:p.type, quantity:q}])
    setMsg('เพิ่มรายการยา: '+p.name)
  }

  function removeItem(idx){
    setItems(items.filter((_,i)=>i!==idx))
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
        // update local pill amounts if server returned updated_pills
        try {
          if (r.updated_pills && Array.isArray(r.updated_pills)) {
            // to avoid issues with setter references or weird bundled state, re-fetch the canonical lookup
            API.getLookup().then(data => {
              if (!data) return
              setLookup(data)
              // ensure reasonable defaults for quantities
              setQuantities(prevQ => {
                const next = { ...prevQ }
                ;(data.pills || []).forEach(p => {
                  const id = String(p.id)
                  if (Number(p.amount) <= 0) next[id] = 0
                  else if (!next[id]) next[id] = 1
                })
                return next
              })
            }).catch(err => {
              console.error('Failed to refresh lookup after queue add', err)
            })
          }
        } catch (err) {
          console.error('Error applying updated_pills', err)
        }
      }
    }).catch(e=>{
      console.error(e)
      setMsg('บันทึกไม่สำเร็จ')
    })
  }

  return (
    <div className="container">
      <div className="card">
        <div className="card-header">
          <div>
            <div className="card-title">เลือกผู้ป่วย</div>
            <div className="card-sub">เลือกผู้ป่วยก่อนเพิ่มรายการยา</div>
          </div>
        </div>

        <div className="row">
          <label>ผู้ป่วย</label>
          <select value={patient} onChange={e=>setPatient(e.target.value)}>
            <option value="">-- เลือก --</option>
            {lookup.patients.map(p=> <option key={p.id} value={String(p.id)}>{p.name}</option>)}
          </select>
          <div className="muted" style={{marginLeft:12}}>สถานะ: {loading? 'กำลังโหลด':''}</div>
        </div>
      </div>

      <div className="card">
        <div className="card-header"><div><div className="card-title">รายการยาทั้งหมด</div><div className="card-sub">เลือกจำนวนและเพิ่มไปยังรายการ</div></div></div>
        <table>
          <thead>
            <tr>
              <th>ยา</th>
              <th>ประเภท</th>
              <th className="right">สต็อกคงเหลือ</th>
              <th className="right">จำนวนที่จะเพิ่ม</th>
              <th>เพิ่ม</th>
            </tr>
          </thead>
          <tbody>
            {lookup.pills.map(p=>{
              const pid = String(p.id)
              const stock = getStockFor(p)
              const reserved = getReserved(pid)
              const remaining = (stock === null) ? Infinity : Math.max(0, stock - reserved)
              const desired = Math.max(0, parseInt(quantities[pid]||1))
              return (
                <tr key={p.id}>
                  <td>{p.name}</td>
                  <td>{p.type}</td>
                  <td className="right">{remaining===Infinity? '-' : remaining}</td>
                  <td className="right">
                    <div style={{display:'flex',alignItems:'center',justifyContent:'flex-end',gap:6}}>
                      <button className="btn secondary" onClick={()=>incQty(pid,-1)}>-</button>
                      <input type="number" value={desired} min="0" style={{width:70,textAlign:'right'}} onChange={e=>setQty(pid,e.target.value)} />
                      <button className="btn secondary" onClick={()=>incQty(pid,1)}>+</button>
                    </div>
                  </td>
                  <td>
                    <button className="btn" onClick={()=>addItem(pid)} disabled={desired<=0 || (remaining!==Infinity && remaining<=0)}>เพิ่ม</button>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
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
            {items.map((it,idx)=> {
              const p = lookup.pills.find(pp=>String(pp.id)===String(it.pill_id)) || {}
              const stock = getStockFor(p)
              const reservedBefore = items.slice(0,idx).filter(x=>String(x.pill_id)===String(it.pill_id)).reduce((s,i)=>s + (parseInt(i.quantity||0)), 0)
              const remaining = Math.max(0, stock - reservedBefore - parseInt(it.quantity||0))
              return (
                <tr key={idx}>
                  <td>{it.name}</td>
                  <td>{it.type}</td>
                  <td className="right">{Math.max(0, stock - (getReserved(it.pill_id)) )}</td>
                  <td className="right">{it.quantity}</td>
                  <td><button className="btn secondary" onClick={()=>removeItem(idx)}>ลบ</button></td>
                </tr>
              )
            })}
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
