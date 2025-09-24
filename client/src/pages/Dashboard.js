import React, { useEffect, useState } from 'react'
import '../App.css'

const API = { getDashboard: () => fetch('/api/dashboard').then(r=>r.json()) }

export default function Dashboard(){
  const [current, setCurrent] = useState(null)
  const [success, setSuccess] = useState(0)
  const [logs, setLogs] = useState([])

  function poll(){
    API.getDashboard().then(d=>{
      setCurrent(d.current)
      setLogs(d.logs||[])
      setSuccess(d.success_count||0)
    }).catch(console.error)
  }

  useEffect(()=>{ poll(); const t=setInterval(poll,3000); return ()=>clearInterval(t) },[])

  return (
    <div className="wrap">
      <h1>Dashboard</h1>
      <div className="row">
        <div className="card" style={{flex:1}}>
          <h3>Current Queue</h3>
          <div id="current">{current ? `${current.queue_number} — ${current.patient_name}` : 'loading…'}</div>
        </div>
        <div className="card" style={{flex:1}}>
          <h3>Success Count</h3>
          <div id="success">{success}</div>
        </div>
      </div>

      <div className="card" style={{marginTop:12}}>
        <h3>Logs (latest 50)</h3>
        <pre className="mono" style={{whiteSpace:'pre-wrap'}}>{logs.map(l=>`${l.ts} [${l.event}] ${l.message}`).join('\n')}</pre>
      </div>
    </div>
  )
}
