import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { ThemeProvider } from './theme/ThemeContext.jsx';
import { SupportPage } from './pages/SupportPage.jsx';
import './styles/tokens.css';
import './styles/base.css';
import './styles/effects.css';
import './styles/ui.css';
import './styles/layout.css';

/** Customer-facing app: only the support pages, served on its own port. */
ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <ThemeProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/support" element={<SupportPage />} />
          <Route path="/support/:ticketId" element={<SupportPage />} />
          <Route path="*" element={<Navigate to="/support" replace />} />
        </Routes>
      </BrowserRouter>
    </ThemeProvider>
  </React.StrictMode>,
);
