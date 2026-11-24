import React from 'react';
import { BrowserRouter, Route, Routes } from 'react-router-dom';
import { Navbar } from './components/Navbar';
import { AuthProvider } from './context/AuthContext';
import { AdminDashboardPage } from './pages/AdminDashboardPage';
import { BookingPage } from './pages/BookingPage';
import { CheckoutPage } from './pages/CheckoutPage';
import { LoginPage } from './pages/LoginPage';
import { LookupPage, MyBookingsPage } from './pages/LookupAndHistoryPage';
import { RegisterPage } from './pages/RegisterPage';
import { StaffScannerPage } from './pages/StaffScannerPage';

export const App: React.FC = () => {
  return (
    <AuthProvider>
      <BrowserRouter>
        <div className="min-h-screen flex flex-col bg-slate-50">
          <Navbar />
          <main className="flex-1">
            <Routes>
              <Route path="/" element={<BookingPage />} />
              <Route path="/login" element={<LoginPage />} />
              <Route path="/register" element={<RegisterPage />} />
              <Route path="/checkout/:bookingCode" element={<CheckoutPage />} />
              <Route path="/lookup" element={<LookupPage />} />
              <Route path="/my-bookings" element={<MyBookingsPage />} />
              <Route path="/staff/scanner" element={<StaffScannerPage />} />
              <Route path="/admin" element={<AdminDashboardPage />} />
            </Routes>
          </main>
          <footer className="bg-white border-t border-slate-200 py-4 text-center text-xs text-slate-500">
            Pickleball SOA Arena • FastAPI Microservices + React + RabbitMQ + Redis + Prometheus & Grafana
          </footer>
        </div>
      </BrowserRouter>
    </AuthProvider>
  );
};

export default App;
