import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import './index.css'
import BillPage from './pages/BillPage'
import HomePage from './pages/HomePage'
import PayPage from './pages/PayPage'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/bill/:billId" element={<BillPage />} />
        <Route path="/pay/:shareId" element={<PayPage />} />
      </Routes>
    </BrowserRouter>
  </StrictMode>,
)
