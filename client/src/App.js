import React, { useState, useEffect } from 'react'
import './App.css'
import logo from './pages/embededlogo.png'
import DispenseManagement from './pages/DispenseManagement'
import QueueManagement from './pages/QueueManagement'
import Dashboard from './pages/Dashboard'
import CrudManagement from './pages/CrudManagement'
import { BrowserRouter as Router, Route, Routes, Link, useLocation } from 'react-router-dom'

function Header(){
  const location = useLocation()
  const path = location.pathname
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
        <Link to="/" className={`btn ${path==='/' ? 'active' : ''}`}>แดชบอร์ด</Link>
        <Link to="/dispense" className={`btn ${path==='/dispense' ? 'active' : ''}`} style={{marginLeft:8}}>จัดยา</Link>
        <Link to="/queue" className={`btn ${path==='/queue' ? 'active' : ''}`} style={{marginLeft:8}}>คิว</Link>
        <Link to="/crud" className={`btn ${path==='/crud' ? 'active' : ''}`} style={{marginLeft:8}}>CRUD</Link>
      </div>
    </div>
  )
}

function KeyGate({children}){
  const [key, setKey] = useState(localStorage.getItem('access_key')||'')
  const [input, setInput] = useState('')
  const [error, setError] = useState('')
  const requiredKey = 'gay' // สามารถเปลี่ยน key ที่นี่

  if(!key || key !== requiredKey){
    return (
      <div style={{display:'flex',flexDirection:'column',alignItems:'center',justifyContent:'center',height:'100vh'}}>
        <div className="card" style={{padding:32,minWidth:320}}>
          <div style={{fontSize:48,marginBottom:8}}>🔒</div>
          <h2>เข้าสู่ระบบเพื่อเข้าใช้งานแดชบอร์ด</h2>
          <input type="password" value={input} onChange={e=>setInput(e.target.value)} placeholder="กรอกรหัสผ่าน..." style={{margin:'16px 0',padding:8,width:'100%'}} />
          {error && <div style={{color:'red',marginBottom:8}}>{error}</div>}
          <button className="btn" onClick={()=>{
            if(input===requiredKey){
              localStorage.setItem('access_key',input)
              setKey(input)
              setError('')
            }else{
              setError('รหัสผ่านไม่ถูกต้อง')
            }
          }}>เข้าสู่ระบบ</button>
        </div>
      </div>
    )
  }
  return children
}

export default function App(){
  const [showNav, setShowNav] = useState(true)
  const [lastScroll, setLastScroll] = useState(window.scrollY)

  useEffect(() => {
    let ticking = false
    const onScroll = () => {
      if (!ticking) {
        window.requestAnimationFrame(() => {
          const curr = window.scrollY
          if (curr > lastScroll + 10) setShowNav(false)
          else if (curr < lastScroll - 10) setShowNav(true)
          setLastScroll(curr)
          ticking = false
        })
        ticking = true
      }
    }
    window.addEventListener('scroll', onScroll)
    return () => window.removeEventListener('scroll', onScroll)
  }, [lastScroll])

  return (
    <Router>
      <div className="app-container">
        <div className={showNav ? 'nav-visible' : 'nav-hidden'}>
          <Header />
        </div>
        <div style={{padding:8, borderBottom:'1px solid transparent'}}>
          {/* keep space for header if needed */}
        </div>
        <div className="main-content">
          <Routes>
            <Route path="/" element={<KeyGate><Dashboard /></KeyGate>} />
            <Route path="/queue" element={<QueueManagement />} />
            <Route path="/dispense" element={<DispenseManagement />} />
            <Route path="/crud" element={<CrudManagement />} />
          </Routes>
        </div>
      </div>
    </Router>
  )
}
