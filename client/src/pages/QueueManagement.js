import React, { useEffect, useState } from 'react'
import '../App.css'

const API = {
  getDashboard: () => fetch('/api/dashboard').then(r=>r.json())
}

export default function QueueManagement(){
  const [data, setData] = useState({})

  function poll(){
    API.getDashboard().then(d=>{
      setData(d || {})
    }).catch(e=>console.error(e))
  }

  useEffect(()=>{ poll(); const t=setInterval(poll,3000); return ()=>clearInterval(t) },[])

  const pending = (data.pending || []).slice(0,5)
  const current = data.current || null
  const previous = data.previous || data.prev || data.prev_queue || null
  const lastFinished = (data.served && data.served.length) ? data.served[0] : null

  function renderStatus(s){
    if(!s) return <span className="sticker">ไม่ระบุ</span>
    const key = String(s).toLowerCase()
    if(key.includes('success') || key.includes('done') || key.includes('served')) return <span className="sticker">✅ เสร็จสิ้น</span>
    if(key.includes('sent') || key.includes('sending')) return <span className="sticker">📤 ส่งแล้ว</span>
    if(key.includes('pending')) return <span className="sticker">⏳ รอ</span>
    if(key.includes('processing')) return <span className="sticker">🔄 กำลังทำ</span>
    if(key.includes('fail') || key.includes('error')) return <span className="sticker">❌ ล้มเหลว</span>
    return <span className="sticker">{s}</span>
  }

  function Card({item, title, prominent}){
    const cls = `card ${prominent? 'full':'side'}`
    if(!item) return (
      <div className={cls} style={{minHeight:180,display:'flex',alignItems:'center',justifyContent:'center'}}>
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

  function PendingList({items}){
    if(!items || items.length===0) return <div style={{padding:12,color:'#7b8b7b'}}>ไม่มีคิวค้าง</div>
    return (
      <div style={{padding:8}}>
        {items.map(it=> (
          <div key={it.queue_id} style={{padding:8, borderBottom:'1px solid rgba(0,0,0,0.06)'}}>
            <div style={{fontWeight:700}}>{it.queue_number}</div>
            <div className="muted">{it.patient_name} • ห้อง {it.room}</div>
            <div style={{marginTop:6}}>{renderStatus(it.status)}</div>
          </div>
        ))}
      </div>
    )
  }

  const [bannerPos, setBannerPos] = useState(0);
  const bannerRef = React.useRef();

  useEffect(() => {
    let running = true;
    function animate() {
      if (!running) return;
      if (bannerRef.current && bannerRef.current.parentElement) {
        setBannerPos(pos => {
          const parentWidth = bannerRef.current.parentElement.offsetWidth;
          const bannerWidth = bannerRef.current.offsetWidth;
          let next = pos - 1; // ลดความเร็วลง
          if (next < -bannerWidth) next = parentWidth;
          return next;
        });
      }
      requestAnimationFrame(animate);
    }
    animate();
    return () => { running = false; };
  }, []);

  return (
    <div>
      <div style={{overflow:'hidden',height:64,margin:'24px auto 32px auto',maxWidth:700}}>
        <div
          ref={bannerRef}
          style={{
            whiteSpace:'nowrap',
            display:'inline-block',
            fontSize:18,
            fontWeight:600,
            background:'#e3f2fd',
            color:'#1976d2',
            padding:'18px 28px',
            borderRadius:12,
            boxShadow:'0 2px 8px rgba(0,0,0,0.04)',
            position:'relative',
            transform:`translateX(${bannerPos}px)`
          }}
        >
          <span className="emoji" style={{fontSize:22,marginRight:8}}>🧑‍🦰</span>
          ระบบนี้จะแสดงสถานะคิวของคนไข้ที่รอรับยา สามารถตรวจสอบคิวปัจจุบัน คิวที่รอ และคิวที่เสร็จแล้วได้
        </div>
      </div>
      <div style={{maxWidth:700,margin:'0 auto',padding:12}}>
        <Card item={current} title="คิวปัจจุบัน" prominent={true} />
        <div style={{display:'flex',gap:12,marginTop:12}}>
          <Card item={previous} title="คิวก่อนหน้า" />
          <Card item={lastFinished} title="คิวที่เสร็จแล้ว" />
        </div>
        <div style={{marginTop:24}}>
          <div style={{fontSize:16,fontWeight:700}}>คิวที่รอรับยา</div>
          <PendingList items={pending} />
        </div>
      </div>
    </div>
  )
}
