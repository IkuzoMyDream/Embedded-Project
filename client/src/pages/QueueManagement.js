import React, { useEffect, useState } from 'react'
import '../App.css'

const API = {
  getDashboard: () => fetch('/api/dashboard').then(r=>r.json()),
  deleteQueue: (id) => fetch(`/api/queues/${id}`, {method:'DELETE'}).then(r=>r.json())
}

export default function QueueManagement(){
  const [current, setCurrent] = useState(null)
  const [logs, setLogs] = useState([])

  function poll(){
    API.getDashboard().then(data=>{
      setCurrent(data.current)
      setLogs(data.logs || [])
    }).catch(e=>console.error(e))
  }

  useEffect(()=>{ poll(); const t=setInterval(poll,3000); return ()=>clearInterval(t) },[])

  return (
    <div className="wrap">
      <h1>จัดการคิว (React)</h1>
      <section>
        <h2>คิวปัจจุบัน</h2>
        {!current ? <div className="muted">ไม่มีคิวที่รออยู่</div> : (
          <div>คิว#: <b>{current.queue_number}</b> ผู้ป่วย: <b>{current.patient_name}</b> ห้อง: <b>{current.room}</b> สถานะ: <b>{current.status}</b></div>
        )}
      </section>

      <hr style={{margin:'24px 0'}} />

      <section>
        <h2>บันทึกเหตุการณ์ล่าสุด</h2>
        <table id="logsTbl">
          <thead><tr><th>ID</th><th>Queue</th><th>เวลา</th><th>เหตุการณ์</th><th>ข้อความ</th></tr></thead>
          <tbody>
            {logs.map(l=> (
              <tr key={l.id}><td>{l.id}</td><td>{l.queue_id}</td><td>{l.ts}</td><td>{l.event}</td><td>{l.message}</td></tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  )
}
