import { useState, useEffect } from 'react'
import { BrowserRouter, Routes, Route, NavLink, Link, useLocation } from 'react-router-dom'
import { Toaster } from 'react-hot-toast'
import Search from './pages/Search'
import LotDetail from './pages/LotDetail'
import Admin from './pages/Admin'
import Watchlist from './pages/Watchlist'
import Archive from './pages/Archive'
import AnimatedBackground from './components/AnimatedBackground'
import './App.css'

function Navbar() {
  const [open, setOpen] = useState(false)
  const location = useLocation()

  useEffect(() => setOpen(false), [location])

  return (
    <>
      <nav className="navbar">
        <Link to="/" className="navbar-brand">
          <span className="brand-icon">🏎</span>
          <span className="brand-name">JapanAuction</span>
          <span className="brand-tag">Intelligence</span>
        </Link>

        {/* Desktop nav */}
        <div className="navbar-links desktop-nav">
          <NavLink to="/" end className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>Search</NavLink>
          <NavLink to="/watchlist" className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>Watchlist</NavLink>
          <NavLink to="/archive" className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>Archive</NavLink>
          <NavLink to="/admin" className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>Admin</NavLink>
        </div>

        <div className="navbar-right">
          {/* Hamburger */}
          <button className="hamburger" onClick={() => setOpen(o => !o)} aria-label="Menu">
            <span className={`ham-line ${open ? 'open' : ''}`} />
            <span className={`ham-line ${open ? 'open' : ''}`} />
            <span className={`ham-line ${open ? 'open' : ''}`} />
          </button>
        </div>
      </nav>

      {/* Mobile dropdown */}
      {open && (
        <div className="mobile-nav">
          <NavLink to="/" end className={({ isActive }) => isActive ? 'mobile-link active' : 'mobile-link'}>Search</NavLink>
          <NavLink to="/watchlist" className={({ isActive }) => isActive ? 'mobile-link active' : 'mobile-link'}>Watchlist</NavLink>
          <NavLink to="/archive" className={({ isActive }) => isActive ? 'mobile-link active' : 'mobile-link'}>Archive</NavLink>
          <NavLink to="/admin" className={({ isActive }) => isActive ? 'mobile-link active' : 'mobile-link'}>Admin</NavLink>
        </div>
      )}
    </>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <AnimatedBackground />
      <Toaster
        position="top-center"
        toastOptions={{
          style: {
            background: 'rgba(234,232,242,0.85)',
            backdropFilter: 'blur(10px)',
            color: 'var(--text-1)',
            boxShadow: 'var(--neu-raised)',
            border: '1px solid rgba(255,255,255,0.4)',
            fontSize: '13px',
          },
        }}
      />
      <Navbar />
      <main className="main-content">
        <Routes>
          <Route path="/" element={<Search />} />
          <Route path="/lot/:id" element={<LotDetail />} />
          <Route path="/watchlist" element={<Watchlist />} />
          <Route path="/archive" element={<Archive />} />
          <Route path="/admin" element={<Admin />} />
        </Routes>
      </main>
    </BrowserRouter>
  )
}
