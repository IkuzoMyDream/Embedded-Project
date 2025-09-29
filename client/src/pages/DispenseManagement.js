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
  const [showModal, setShowModal] = useState(false)
  const [modalMsg, setModalMsg] = useState('')

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
    setItems(prev => {
      // ถ้ามีรายการนี้อยู่แล้ว ให้เพิ่มจำนวน
      const idx = prev.findIndex(it => String(it.pill_id) === String(p.id))
      if(idx !== -1){
        const updated = [...prev]
        updated[idx] = { ...updated[idx], quantity: updated[idx].quantity + q }
        return updated
      }
      // ถ้ายังไม่มี ให้เพิ่มใหม่
      return [...prev,{pill_id:p.id, name:p.name, type:p.type, quantity:q}]
    })
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
        setShowModal(true)
        setModalMsg('บันทึกคิวเสร็จสิ้น!')
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

  // Shared empty placeholder style for cards
  const emptyBoxStyle = { display:'flex', alignItems:'center', justifyContent:'center', minHeight:80, color:'#7b8b7b', fontSize:16, padding:12 }

  return (
    <div className="container">
      {/* แสดง Role คนไข้ ใน nav ด้านขวาบน */}
      <div className="nav" style={{display:'flex',alignItems:'center',justifyContent:'flex-end',marginBottom:16}}>
        <div style={{minWidth:160}}>
          <div className="card" style={{background:'#fff3e0',color:'#f57c00',padding:'8px 16px',textAlign:'center',boxShadow:'0 2px 8px rgba(0,0,0,0.04)',fontSize:16}}>
            <span className="emoji" style={{fontSize:20,marginRight:6}}>🧑‍🦰</span>Role: คนไข้
          </div>
        </div>
      </div>
      {/* Modal Success */}
      {showModal && (
        <div style={{position:'fixed',top:0,left:0,width:'100vw',height:'100vh',background:'rgba(0,0,0,0.25)',zIndex:999,display:'flex',alignItems:'center',justifyContent:'center'}}>
          <div style={{background:'#fff',borderRadius:12,padding:32,minWidth:320,boxShadow:'0 2px 16px rgba(0,0,0,0.12)',textAlign:'center',position:'relative'}}>
            <div style={{fontSize:64,marginBottom:16}}>✅</div>
            <div style={{fontSize:22,fontWeight:700,marginBottom:8}}>{modalMsg}</div>
            <button className="btn" style={{marginTop:16}} onClick={()=>setShowModal(false)}>ปิด</button>
          </div>
        </div>
      )}

      <div className="card">
        <div className="card-header">
          <div>
            <div className="card-title">เลือกผู้ป่วย</div>
            <div className="card-sub">เลือกผู้ป่วยก่อนเพิ่มรายการยา</div>
          </div>
        </div>

        <div className="row">
          <label>ผู้ป่วย</label>
          { (lookup.patients && lookup.patients.length) ? (
            <>
              <select value={patient} onChange={e=>setPatient(e.target.value)}>
                <option value="">-- เลือก --</option>
                {lookup.patients.map(p=> <option key={p.id} value={String(p.id)}>{p.name}</option>)}
              </select>
              <div className="muted" style={{marginLeft:12}}>สถานะ: {loading? 'กำลังโหลด':''}</div>
            </>
          ) : (
            <div style={{flex:1}}>
              <div style={emptyBoxStyle}>ไม่มีผู้ป่วยในระบบ</div>
            </div>
          )}
        </div>
      </div>

      <div className="card">
        <div className="card-header"><div><div className="card-title">รายการยาทั้งหมด</div><div className="card-sub">เลือกจำนวนและเพิ่มไปยังรายการ</div></div></div>
        <table className="dispense-table">
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
            { (lookup.pills && lookup.pills.length) ? lookup.pills.map(p=>{
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
            }) : (
              <tr>
                <td colSpan="5" style={{textAlign:'center', padding:20}}>
                  <div style={emptyBoxStyle}>ไม่มีข้อมูลยาอยู่ในระบบ</div>
                </td>
              </tr>
            )}
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
            { (items && items.length) ? items.map((it,idx)=> {
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
                  <td>
                    <button className="btn" style={{color:'#fff',background:'#e53935',border:'none',fontSize:20,padding:'4px 12px',borderRadius:6}} onClick={()=>removeItem(idx)} title="ลบ">
                      ×
                    </button>
                  </td>
                </tr>
              )
            }) : (
              <tr>
                <td colSpan="5" style={{textAlign:'center', padding:20}}>
                  <div style={emptyBoxStyle}>ยังไม่มีรายการยา</div>
                </td>
              </tr>
            )}
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
            <button className="btn" onClick={submit} disabled={!patient || !(items && items.length)}>บันทึกคิว</button>
            <button className="btn secondary" style={{marginLeft:8}} onClick={()=>{setItems([]); setMsg('')}}>ล้าง</button>
          </div>
          <div className="muted">{msg}</div>
        </div>
      </div>
    </div>
  )
}
