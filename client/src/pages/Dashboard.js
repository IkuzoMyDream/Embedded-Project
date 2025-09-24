import React, { useEffect, useState } from 'react'
import '../App.css'

const API = { getDashboard: () => fetch('/api/dashboard').then(r=>r.json()) }

export default function Dashboard(){
  const [current, setCurrent] = useState(null)
  const [success, setSuccess] = useState(0)
  const [logs, setLogs] = useState([])
  const [expanded, setExpanded] = useState({})

  function poll(){
    API.getDashboard().then(d=>{
      setCurrent(d.current)
      setLogs(d.logs||[])
      setSuccess(d.success_count||0)
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
        return j.items.map(it=> `${it.pill_id}×${it.quantity}`).join(', ')
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
        <div className="nav">
          <div className="stickers-row">
            <div className="sticker-badge"><span className="emoji">🩺</span><span className="text">คลินิก</span></div>
            <div className="sticker-badge"><span className="emoji">💊</span><span className="text">ตู้ยา</span></div>
          </div>
        </div>
      </div>

      <div className="grid">
        <div className="col-4">
          <div className="card">
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
        </div>

        <div className="col-4">
          <div className="card">
            <div className="card-header">
              <div>
                <div className="card-title">จำนวนสำเร็จ</div>
                <div className="card-sub">การจ่ายยาที่เสร็จสมบูรณ์</div>
              </div>
            </div>
            <div className="stat">
              <div className="value">{success}</div>
              <div className="label">Total successful queues</div>
            </div>
            <div className="card-footer"><span className="helper">since init</span></div>
          </div>
        </div>

        <div className="col-4">
          <div className="card">
            <div className="card-header">
              <div>
                <div className="card-title">บันทึกล่าสุด</div>
                <div className="card-sub">เหตุการณ์ 50 รายการล่าสุด</div>
              </div>
            </div>
            <div className="helper">คลิกแถวเพื่อดูรายละเอียด</div>
          </div>
        </div>

        <div className="col-12">
          <div className="card">
            <table>
              <thead>
                <tr>
                  <th style={{width:160}}>เวลา</th>
                  <th style={{width:110}}>เหตุการณ์</th>
                  <th style={{width:100}}>คิว</th>
                  <th>รายละเอียด</th>
                  <th style={{width:80}}></th>
                </tr>
              </thead>
              <tbody>
                {logs.map(l=> (
                  <React.Fragment key={l.id}>
                    <tr onClick={()=>toggleExpand(l.id)} style={{cursor:'pointer'}}>
                      <td className="mono">{l.ts || ''}</td>
                      <td><span className={`pill ${l.event||''}`}>{l.event}</span></td>
                      <td>{l.queue_id || '-'}</td>
                      <td>{renderMessage(l.message)}</td>
                      <td><button className="btn secondary" onClick={(e)=>{e.stopPropagation(); toggleExpand(l.id)}}>{expanded[l.id] ? 'ซ่อน' : 'แสดง'}</button></td>
                    </tr>
                    {expanded[l.id] && (
                      <tr>
                        <td colSpan={5} style={{background:'#fbfdff'}}>
                          <pre className="mono" style={{whiteSpace:'pre-wrap',margin:0,padding:12}}>{typeof l.message==='string' ? l.message : JSON.stringify(l.message, null, 2)}</pre>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                ))}
              </tbody>
            </table>
          </div>
        </div>

      </div>

      <div className="footer">Smart Dispense — สถานะและบันทึก</div>
    </div>
  )
}
