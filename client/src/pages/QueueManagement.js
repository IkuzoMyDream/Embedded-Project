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
  // const current = data.current || null
  // หา current จากทั้ง pending และ processing
  const current = ([...(data.pending||[]), ...(data.processing||[])]).find(q => (q.status && (q.status.toLowerCase() === 'in_progress' || q.status.toLowerCase() === 'processing'))) || null

  // หา previous 5 คิวล่าสุดก่อน current (ใน pending)
  let previous = [];
  if (data.pending && data.pending.length > 0 && current) {
    const idx = data.pending.findIndex(q => q.queue_id === current.queue_id);
    if (idx > -1) {
      // แก้ไขให้แสดง 5 คิวหลัง current
      previous = data.pending.slice(idx+1, idx+6);
    } else {
      // ถ้า current ไม่อยู่ใน pending ให้แสดง 5 คิวแรกของ pending
      previous = data.pending.slice(0,5);
    }
  } else if (data.pending && data.pending.length > 0) {
    previous = data.pending.slice(0,5);
  } else {
    previous = (data.previous || data.prev || data.prev_queue || []);
  }
  // Show up to 5 served as lastFinished (ใหม่สุด -> เก่าสุด)
  const lastFinished = (data.served && data.served.length) ? data.served.slice(-5).reverse() : null

  useEffect(() => {
    console.log('data:', data);
    console.log('pending:', data.pending);
    console.log('processing:', data.processing);
    console.log('current:', current);
  }, [data, current]);

  function renderStatus(s){
    if(!s) return <span className="sticker">ไม่ระบุ</span>
    const key = String(s).toLowerCase()
    if(key.includes('success') || key.includes('done') || key.includes('served')) return <span className="sticker">✅ เสร็จสิ้น</span>
    if(key.includes('sent') || key.includes('sending')) return <span className="sticker">📤 ส่งแล้ว</span>
    if(key.includes('pending')) return <span className="sticker">⏳ รอ</span>
    if(key.includes('processing') || key.includes('in_progress')) return <span className="sticker">💊 กำลังจัดยา</span>
    if(key.includes('fail') || key.includes('error')) return <span className="sticker">❌ ล้มเหลว</span>
    return <span className="sticker">{s}</span>
  }

  function Card({item, title, prominent}){
    const cls = `card ${prominent? 'full':'side'}`
    // If previous card and item is an array (pending list), show as list
    if(title === "คิวก่อนหน้า" && Array.isArray(item)) {
      const hasData = item && item.length > 0 && item.some(it => it && (it.queue_id || it.queue_number));
      return (
        <div className={cls} style={{minHeight:180, display:'flex',flexDirection:'column',justifyContent:'center',alignItems: !hasData ? 'center' : 'stretch'}}>
          <div className="card-header" style={{paddingBottom:10, borderBottom:'2.5px solid #1976d2', marginBottom:10, background:'#f5faff', borderRadius:'10px 10px 0 0'}}>
            <div>
              <div className="card-title" style={{fontSize:32, fontWeight:900, color:'#1565c0', letterSpacing:1.5, textShadow:'0 2px 8px #e3f2fd'}}>📝 {title}</div>
            </div>
          </div>
          <div style={{padding:8, width:'100%'}}>
            {!hasData ? <div style={{color:'#7b8b7b',textAlign:'center',fontSize:20}}>ไม่มีคิวค้าง</div> : item.slice(0,5).map(it=> {
              const qnum = it.queue_number ?? it.queue_id ?? '-';
              const patient = it.patient_name ?? it.patient ?? '-';
              const room = it.room ?? it.room_name ?? '-';
              return (
                <div key={it.queue_id} style={{display:'flex',alignItems:'center',gap:12,justifyContent:'flex-start',padding:8,borderBottom:'1px solid rgba(0,0,0,0.06)'}}>
                  <div style={{flex:'0 0 auto', borderRight:'2px solid #e0e0e0', paddingRight:16, marginRight:16}}>
                    <div className="queue-number" style={{color:'var(--gov-green)', fontSize:56, fontWeight:900}}>{qnum}</div>
                  </div>
                  <div style={{flex:1,textAlign:'left'}}>
                    <div style={{fontSize:18,fontWeight:800}}>{patient}</div>
                    <div className="muted" style={{marginTop:6}}>ห้อง: {room}</div>
                    <div style={{marginTop:10}}>{renderStatus(it.status)}</div>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )
    }
    // กรณี card คิวที่เสร็จแล้ว (lastFinished) ให้ใช้ style และโครงสร้างเดียวกับคิวก่อนหน้า
    if(title === "คิวที่เสร็จแล้ว" && Array.isArray(item)) return (
      <div className={cls} style={{minHeight:180, display:'flex',flexDirection:'column',justifyContent:'center',alignItems: item.length === 0 ? 'center' : 'stretch'}}>
        <div className="card-header" style={{paddingBottom:10, borderBottom:'2.5px solid #1976d2', marginBottom:10, background:'#f5faff', borderRadius:'10px 10px 0 0'}}>
          <div>
            <div className="card-title" style={{fontSize:32, fontWeight:900, color:'#1565c0', letterSpacing:1.5, textShadow:'0 2px 8px #e3f2fd'}}>✅ {title}</div>
          </div>
        </div>
        <div style={{padding:8, width:'100%'}}>
          {item.length === 0 ? <div style={{color:'#7b8b7b',textAlign:'center',fontSize:20}}>ไม่มีคิวเสร็จ</div> : item.slice(0,5).map(it=> {
            const qnum = it.queue_number ?? it.queue_id ?? '-';
            const patient = it.patient_name ?? it.patient ?? '-';
            const room = it.room ?? it.room_name ?? '-';
            return (
              <div key={it.queue_id} style={{display:'flex',alignItems:'center',gap:12,justifyContent:'flex-start',padding:8,borderBottom:'1px solid rgba(0,0,0,0.06)'}}>
                <div style={{flex:'0 0 auto', borderRight:'2px solid #e0e0e0', paddingRight:16, marginRight:16}}>
                  <div className="queue-number" style={{color:'var(--gov-green)', fontSize:56, fontWeight:900}}>{qnum}</div>
                </div>
                <div style={{flex:1,textAlign:'left'}}>
                  <div style={{fontSize:18,fontWeight:800}}>{patient}</div>
                  <div className="muted" style={{marginTop:6}}>ห้อง: {room}</div>
                  <div style={{marginTop:10}}>{renderStatus(it.status)}</div>
                  {it.served_at && <div className="muted" style={{marginTop:6}}>{`เสร็จเมื่อ: ${it.served_at}`}</div>}
                </div>
              </div>
            )
          })}
        </div>
      </div>
    )
    // If item is null or undefined, show no data (compressed card, all cards)
    if(!item) {
      // ใช้ layout เดียวกับตอนมีข้อมูล แต่แสดง placeholder
      return (
        <div className={cls} style={{display:'flex', flexDirection:'column'}}>
          <div className="card-header" style={{paddingBottom:10, borderBottom:'2.5px solid #1976d2', marginBottom:10, background:'#f5faff', borderRadius:'10px 10px 0 0'}}>
            <div>
              <div className="card-title" style={{fontSize:32, fontWeight:900, color:'#1565c0', letterSpacing:1.5, textShadow:'0 2px 8px #e3f2fd'}}>{title}</div>
            </div>
          </div>
          <div style={{display:'flex',alignItems:'flex-start',gap:12,justifyContent:'flex-start', marginTop:0, flex:'1 0 auto'}}>
            <div style={{flex:'0 0 auto', borderRight:'2px solid #e0e0e0', paddingRight:16, marginRight:16}}>
              <div className="queue-number" style={{color: prominent ? 'var(--gov-blue)' : 'var(--gov-green)', fontSize:72, fontWeight:900, lineHeight:'1.1'}}>-</div>
            </div>
            <div style={{flex:1,textAlign:'left'}}>
              <div style={{fontSize:18,fontWeight:800}}>ไม่พบข้อมูล</div>
              <div className="muted" style={{marginTop:6}}>ห้อง: -</div>
              <div style={{marginTop:10}}><span className="sticker">-</span></div>
            </div>
          </div>
        </div>
      )
    }
    const qnum = item.queue_number ?? item.queue_id ?? '-'
    const patient = item.patient_name ?? item.patient ?? '-'
    const room = item.room ?? item.room_name ?? '-'
    return (
      <div className={cls} style={{display:'flex', flexDirection:'column'}}>
        {/* Card header style: bigger, bold, clearer, with underline and accent color */}
        <div className="card-header" style={{paddingBottom:10, borderBottom:'2.5px solid #1976d2', marginBottom:10, background:'#f5faff', borderRadius:'10px 10px 0 0'}}>
          <div>
            <div className="card-title" style={{fontSize:32, fontWeight:900, color:'#1565c0', letterSpacing:1.5, textShadow:'0 2px 8px #e3f2fd'}}>{title}</div>
          </div>
        </div>
        <div style={{display:'flex',alignItems:'flex-start',gap:12,justifyContent:'flex-start', marginTop:0, flex:'1 0 auto'}}>
          <div style={{flex:'0 0 auto', borderRight:'2px solid #e0e0e0', paddingRight:16, marginRight:16}}>
            <div className="queue-number" style={{color: prominent ? 'var(--gov-blue)' : 'var(--gov-green)', fontSize:72, fontWeight:900, lineHeight:'1.1'}}>{qnum}</div>
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
    <div>
      <div style={{overflow:'hidden',height:64,margin:'24px auto 32px auto',maxWidth:1200}}>
        <div
          className="banner-marquee"
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
            minWidth:'100%'
          }}
        >
          <span className="emoji" style={{fontSize:22,marginRight:8}}>🧑‍🦰</span>
          ระบบนี้จะแสดงสถานะคิวของคนไข้ที่รอรับยา สามารถตรวจสอบคิวปัจจุบัน คิวที่รอ และคิวที่เสร็จแล้วได้
        </div>
      </div>
      <div style={{maxWidth:1200,margin:'0 auto',padding:12}}>
        <Card item={current} title="คิวปัจจุบัน" prominent={true} />
        <div style={{display:'flex',marginTop:12}}>
          <div style={{flex:1,marginRight:12}}>
            <Card item={previous} title="คิวก่อนหน้า" />
          </div>
          <div style={{flex:1}}>
            <Card item={lastFinished} title="คิวที่เสร็จแล้ว" />
          </div>
        </div>
      </div>
    </div>
  )
}
