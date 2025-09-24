import React from 'react'
import './App.css'
import DispenseManagement from './pages/DispenseManagement'
import QueueManagement from './pages/QueueManagement'
import Dashboard from './pages/Dashboard'
import CrudManagement from './pages/CrudManagement'

function Nav({page, setPage}){
  return (
    <div style={{padding:12, borderBottom:'1px solid #eee'}}>
      <button onClick={()=>setPage('dashboard')} className="btn" aria-pressed={page==='dashboard'}>Dashboard</button>
      <button onClick={()=>setPage('dispense')} className="btn" style={{marginLeft:8}} aria-pressed={page==='dispense'}>จัดยา</button>
      <button onClick={()=>setPage('queue')} className="btn" style={{marginLeft:8}} aria-pressed={page==='queue'}>คิว</button>
      <button onClick={()=>setPage('crud')} className="btn" style={{marginLeft:8}} aria-pressed={page==='crud'}>CRUD</button>
    </div>
  )
}

export default function App(){
  const [page, setPage] = React.useState('dashboard')

  return (
    <div>
      <Nav page={page} setPage={setPage} />
      {page==='dashboard' && <Dashboard />}
      {page==='dispense' && <DispenseManagement />}
      {page==='queue' && <QueueManagement />}
      {page==='crud' && <CrudManagement />}
    </div>
  )
}
