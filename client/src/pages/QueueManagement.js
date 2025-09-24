import React, { useEffect, useState } from 'react'
import '../App.css'

const API = {
  getDashboard: () => fetch('/api/dashboard').then(r=>r.json())
}

export default function QueueManagement(){
  const [data, setData] = useState({})

  function poll(){
    API.getDashboard().then(d=>{
      console.debug('API /api/dashboard ->', d)
      setData(d || {})
    }).catch(e=>console.error(e))
  }

  useEffect(()=>{ poll(); const t=setInterval(poll,3000); return ()=>clearInterval(t) },[])

  const current = data.current || null
  const previous = data.previous || data.prev || data.prev_queue || null
  const next = data.next || data.nxt || data.next_queue || null

  function renderStatus(s){
    if(!s) return <span className="sticker">ไม่ระบุ</span>
    const key = String(s).toLowerCase()
    if(key.includes('success') || key.includes('done') || key.includes('served')) return <span className="sticker">✅ เสร็จสิ้น</span>
    if(key.includes('sent') || key.includes('sending')) return <span className="sticker">📤 ส่งแล้ว</span>
    if(key.includes('fail') || key.includes('error')) return <span className="sticker">❌ ล้มเหลว</span>
    return <span className="sticker">{s}</span>
  }

  function Card({item, title, prominent}){
    const cls = `card ${prominent? 'full':'side'}`

    if(!item) return (
      <div className={cls} style={{minHeight:220,display:'flex',alignItems:'center',justifyContent:'center'}}>
        <div style={{textAlign:'center',color:'#7b8b7b'}}>{title}<div className="muted">ไม่มีข้อมูล</div></div>
      </div>
    )

    const qnum = item.queue_number ?? item.queue_id ?? '-'
    const patient = item.patient_name ?? item.patient ?? '-'
    const room = item.room ?? item.room_name ?? '-'

    return (
      <div className={cls}>
        <div className="card-header"><div><div className="card-title">{title}</div><div className="card-sub">ข้อมูลคิว</div></div></div>
        <div style={{display:'flex',alignItems:'center',gap:12,justifyContent: prominent? 'center' : 'flex-start'}}>
          <div style={{flex:'0 0 auto'}}>
            <div className="queue-number">{qnum}</div>
          </div>
          <div style={{flex:1,textAlign:'left'}}>
            <div style={{fontSize:18,fontWeight:800}}>{patient}</div>
            <div className="muted" style={{marginTop:6}}>ห้อง: {room}</div>
            <div style={{marginTop:10}}>{renderStatus(item.status)}</div>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="fullpage">
      <div className="full-grid">
        <Card item={previous} title="คิวที่ผ่านมา" />
        <Card item={current} title="คิวปัจจุบัน" prominent />
        <Card item={next} title="คิวถัดไป" />
      </div>
    </div>
  )
}
