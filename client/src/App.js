import React from 'react'
import './App.css'
import logo from './pages/embededlogo.png'
import DispenseManagement from './pages/DispenseManagement'
import QueueManagement from './pages/QueueManagement'
import Dashboard from './pages/Dashboard'
import CrudManagement from './pages/CrudManagement'

function Header({page, setPage}){
  return (
    <div className="header">
      <div className="brand">
        <img src={logo} alt="logo" className="logo" style={{objectFit:'cover'}} />
        <div>
          <h1>ระบบจ่ายยา</h1>
          <div className="meta">หน่วยงาน: โรงพยาบาลตัวอย่าง</div>
        </div>
      </div>
      <div className="nav">
        <button onClick={()=>setPage('dashboard')} className={`btn ${page==='dashboard' ? 'active' : ''}`} aria-pressed={page==='dashboard'}>แดชบอร์ด</button>
        <button onClick={()=>setPage('dispense')} className={`btn ${page==='dispense' ? 'active' : ''}`} style={{marginLeft:8}} aria-pressed={page==='dispense'}>จัดยา</button>
        <button onClick={()=>setPage('queue')} className={`btn ${page==='queue' ? 'active' : ''}`} style={{marginLeft:8}} aria-pressed={page==='queue'}>คิว</button>
        <button onClick={()=>setPage('crud')} className={`btn ${page==='crud' ? 'active' : ''}`} style={{marginLeft:8}} aria-pressed={page==='crud'}>CRUD</button>
      </div>
    </div>
  )
}

export default function App(){
  const [page, setPage] = React.useState('dashboard')

  return (
    <div>
      <Header page={page} setPage={setPage} />
      <div style={{padding:8, borderBottom:'1px solid transparent'}}>
        {/* keep space for header if needed */}
      </div>
      {page==='dashboard' && <Dashboard />}
      {page==='dispense' && <DispenseManagement />}
      {page==='queue' && <QueueManagement />}
      {page==='crud' && <CrudManagement />}
    </div>
  )
}
