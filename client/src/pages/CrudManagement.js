import React from 'react'
import '../App.css'

const API = { deleteQueue: (id)=> fetch(`/api/queues/${id}`, {method:'DELETE'}).then(r=>r.json()) }

export default function CrudManagement(){
  const [qid, setQid] = React.useState('')
  const [msg, setMsg] = React.useState('')
  async function del(){
    if(!qid) return setMsg('ระบุ id')
    const r = await API.deleteQueue(qid)
    setMsg(r.ok? 'Deleted' : JSON.stringify(r))
  }
  return (
    <div className="wrap">
      <h1>CRUD (patients / pills / queues)</h1>
      <p>Template placeholder — extend as needed. For quick demo, delete a queue by ID:</p>
      <div className="card">
        <input value={qid} onChange={e=>setQid(e.target.value)} placeholder="queue id" />
        <button className="btn" onClick={del}>Delete Queue</button>
        <div style={{marginTop:8}}>{msg}</div>
      </div>
    </div>
  )
}
