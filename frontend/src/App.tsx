import React, { Suspense, lazy } from 'react';
import { BrowserRouter, Route, Routes } from 'react-router-dom';
import { Footer } from './components/Footer';
import { Navbar } from './components/Navbar';
import { LoadingSkeleton } from './components/ui/FeedbackStates';
import { AuthProvider } from './context/AuthContext';
import { BookingPage } from './pages/BookingPage';
import { LandingPage } from './pages/LandingPage';
import { LoginPage } from './pages/LoginPage';
import { LookupPage, MyBookingsPage } from './pages/LookupAndHistoryPage';
import { NotFoundPage } from './pages/NotFoundPage';
import { RegisterPage } from './pages/RegisterPage';

const CheckoutPage = lazy(() =>
  import('./pages/CheckoutPage').then((m) => ({ default: m.CheckoutPage }))
);
const StaffScannerPage = lazy(() =>
  import('./pages/StaffScannerPage').then((m) => ({ default: m.StaffScannerPage }))
);
const AdminDashboardPage = lazy(() =>
  import('./pages/AdminDashboardPage').then((m) => ({ default: m.AdminDashboardPage }))
);

const RouteFallback: React.FC = () => (
  <div className="max-w-5xl mx-auto px-4 py-10">
    <LoadingSkeleton rows={4} />
  </div>
);

export const App: React.FC = () => {
  return (
    <AuthProvider>
      <BrowserRouter>
        <div className="min-h-screen flex flex-col bg-warm-white text-charcoal">
          <Navbar />
          <main className="flex-1">
            <Suspense fallback={<RouteFallback />}>
              <Routes>
                <Route path="/" element={<LandingPage />} />
                <Route path="/book" element={<BookingPage />} />
                <Route path="/booking" element={<BookingPage />} />
                <Route path="/login" element={<LoginPage />} />
                <Route path="/register" element={<RegisterPage />} />
                <Route path="/checkout/:bookingCode" element={<CheckoutPage />} />
                <Route path="/lookup" element={<LookupPage />} />
                <Route path="/my-bookings" element={<MyBookingsPage />} />
                <Route path="/staff/scanner" element={<StaffScannerPage />} />
                <Route path="/admin" element={<AdminDashboardPage />} />
                <Route path="*" element={<NotFoundPage />} />
              </Routes>
            </Suspense>
          </main>
          <Footer />
        </div>
      </BrowserRouter>
    </AuthProvider>
  );
};

export default App;
