export type UserRole = 'CUSTOMER' | 'STAFF' | 'ADMIN';

export interface User {
  id: string;
  email: string;
  full_name: string;
  phone: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: User;
}

export interface LocationItem {
  id: string;
  branch_id: string;
  branch_number: number;
  branch_name: string;
  name: string;
  address: string;
  court_count: number;
  created_at: string;
}

export interface BranchItem {
  id: string;
  branch_number: number;
  title_note: string;
  display_name: string;
  locations: LocationItem[];
  created_at: string;
}

export interface Court {
  id: string;
  location_id: string | null;
  branch_id: string | null;
  branch_number: number | null;
  branch_name: string;
  location_name: string;
  location_address: string;
  name: string;
  court_type: 'INDOOR' | 'OUTDOOR';
  surface: string;
  status: 'ACTIVE' | 'MAINTENANCE';
  description: string;
  created_at: string;
}

export interface AvailabilitySlot {
  start_hour: number;
  end_hour: number;
  label: string;
  price: number;
  is_peak_hour: boolean;
  status: 'AVAILABLE' | 'LOCKED' | 'BOOKED' | 'MAINTENANCE' | 'PAST';
}

export interface CourtAvailability {
  court: Court;
  slots: AvailabilitySlot[];
}

export interface AvailabilityResponse {
  play_date: string;
  is_weekend: boolean;
  courts: CourtAvailability[];
}

export interface BookingSlot {
  start_hour: number;
  end_hour: number;
  slot_price: number;
  is_peak_hour: boolean;
  slot_status: string;
}

export interface BookingOrder {
  id: string;
  booking_code: string;
  user_id: string | null;
  customer_name: string;
  customer_phone: string;
  customer_email: string;
  court_id: string;
  court_name_snapshot: string;
  branch_name_snapshot: string;
  location_name_snapshot: string;
  location_address_snapshot: string;
  play_date: string;
  start_hour: number;
  end_hour: number;
  total_amount: number;
  status: 'PENDING_PAYMENT' | 'PAID' | 'CANCELLED' | 'EXPIRED';
  cancel_reason: string | null;
  expires_at: string;
  paid_at: string | null;
  created_at: string;
  slots: BookingSlot[];
}

export interface PaymentTransaction {
  id: string;
  booking_id: string;
  booking_code: string;
  amount: number;
  transfer_content: string;
  qr_image_url: string;
  bank_bin: string;
  bank_account_no: string;
  bank_account_name: string;
  provider: string;
  provider_tx_id: string | null;
  status: 'PENDING' | 'SUCCEEDED' | 'EXPIRED' | 'CANCELLED';
  reconciliation_status?: 'NONE' | 'COMPENSATION_REQUIRED';
  reconciliation_note?: string | null;
  expires_at: string;
  paid_at: string | null;
  created_at: string;
}

export interface CheckinTicket {
  id: string;
  booking_id: string;
  booking_code: string;
  customer_name: string;
  customer_email: string;
  customer_phone: string;
  court_name: string;
  branch_name: string;
  location_name: string;
  location_address: string;
  play_date: string;
  start_hour: number;
  end_hour: number;
  total_amount: number;
  qr_payload: string;
  status: 'VALID' | 'CHECKED_IN' | 'REVOKED';
  checked_in_by: string | null;
  checked_in_at: string | null;
  created_at: string;
  qr_image_base64: string | null;
}

export interface ScanQRResponse {
  valid: boolean;
  code: string;
  message: string;
  ticket: CheckinTicket | null;
}

export interface PricingRule {
  id: string;
  court_type: 'INDOOR' | 'OUTDOOR';
  start_hour: number;
  end_hour: number;
  is_weekend: boolean;
  is_peak_hour: boolean;
  price_per_hour: number;
}

export interface AdminStats {
  total_bookings: number;
  paid_bookings: number;
  pending_bookings: number;
  cancelled_or_expired: number;
  total_revenue: number;
  active_courts: number;
}

export interface NotificationLog {
  id: string;
  booking_code: string;
  recipient_email: string;
  subject: string;
  channel: string;
  status: string;
  retry_count: number;
  error_message: string | null;
  sent_at: string | null;
  created_at: string;
}
