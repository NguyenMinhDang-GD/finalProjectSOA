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
  status: 'PENDING_PAYMENT' | 'PAID' | 'CANCELLED' | 'EXPIRED' | 'NO_SHOW' | 'COMPLETED';
  booking_source?: 'ONLINE' | 'WALK_IN';
  booking_revision?: number;
  admission_status?: 'NONE' | 'ADMITTED';
  checked_in_at?: string | null;
  checked_in_by?: string | null;
  no_show_at?: string | null;
  no_show_by?: string | null;
  completed_at?: string | null;
  completed_by?: string | null;
  cancel_reason: string | null;
  expires_at: string;
  paid_at: string | null;
  created_at: string;
  slots: BookingSlot[];
  guest_access_token?: string | null;
}

export interface PaymentTransaction {
  id: string;
  booking_id: string;
  booking_code: string;
  amount: number;
  expected_amount: number;
  received_amount: number;
  refunded_amount: number;
  currency: string;
  payment_mode: string;
  simulation_notice: string;
  transfer_content: string;
  qr_image_url: string;
  bank_bin: string;
  bank_account_no: string;
  bank_account_name: string;
  provider: string;
  payment_method?: string;
  booking_revision?: number;
  collected_by?: string | null;
  collected_at?: string | null;
  provider_tx_id: string | null;
  status: 'PENDING' | 'PROCESSING' | 'SUCCEEDED' | 'FAILED' | 'EXPIRED' | 'CANCELLED';
  attempt_count: number;
  failure_reason?: string | null;
  last_attempt_at?: string | null;
  reconciliation_status?: 'NONE' | 'OPEN' | 'IN_REVIEW' | 'RESOLVED' | 'COMPENSATION_REQUIRED';
  reconciliation_note?: string | null;
  expires_at: string;
  paid_at: string | null;
  created_at: string;
}

export interface PaymentAttempt {
  id: string;
  payment_id: string;
  booking_code: string;
  attempt_number: number;
  provider: string;
  payment_method?: string;
  booking_revision?: number;
  collected_by?: string | null;
  collected_at?: string | null;
  provider_tx_id: string | null;
  outcome: string;
  expected_amount: number;
  received_amount: number;
  failure_reason: string | null;
  initiated_by: string;
  created_at: string;
}

export interface ReconciliationCase {
  id: string;
  payment_id: string | null;
  booking_code: string;
  case_type: string;
  status: 'OPEN' | 'IN_REVIEW' | 'RESOLVED';
  expected_amount: number;
  received_amount: number;
  discrepancy_amount: number;
  provider_tx_id: string | null;
  resolution_action: string | null;
  resolution_note: string | null;
  resolved_by: string | null;
  resolved_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface RefundTransaction {
  id: string;
  payment_id: string;
  booking_id: string;
  booking_code: string;
  refund_code: string;
  original_paid_amount: number;
  requested_amount: number;
  approved_amount: number;
  refunded_amount: number;
  policy_tier: string;
  policy_percent: number;
  status: 'REQUESTED' | 'APPROVED' | 'PROCESSING' | 'SUCCEEDED' | 'FAILED' | 'REJECTED';
  reason: string;
  rejection_reason: string | null;
  admin_override_reason: string | null;
  failure_reason: string | null;
  provider: string;
  provider_refund_id: string | null;
  retry_count: number;
  requested_by: string;
  approved_by: string | null;
  processed_by: string | null;
  created_at: string;
  approved_at: string | null;
  completed_at: string | null;
  updated_at: string;
}

export interface FinancialAuditLog {
  id: string;
  entity_type: string;
  entity_id: string;
  booking_code: string;
  action: string;
  actor: string;
  actor_role: string;
  previous_state: string | null;
  new_state: string | null;
  amount_vnd: number;
  reason: string | null;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface CancellationQuote {
  booking_code: string;
  status: string;
  eligible: boolean;
  is_checked_in: boolean;
  hours_until_play: number;
  policy_tier: string;
  refund_percent: number;
  total_amount: number;
  estimated_refund_amount: number;
  message: string;
}

export interface RescheduleQuote {
  booking_code: string;
  eligible: boolean;
  reason: string | null;
  current_amount: number;
  new_amount: number;
  same_price: boolean;
  hours_until_current_start: number;
}

export interface MaintenanceBlock {
  id: string;
  court_id: string;
  court_name_snapshot: string;
  play_date: string;
  start_hour: number;
  end_hour: number;
  reason: string;
  status: 'SCHEDULED' | 'CANCELLED' | 'COMPLETED';
  created_by: string;
  cancelled_by: string | null;
  cancelled_at: string | null;
  created_at: string;
}

export interface OperationalAuditLog {
  id: string;
  entity_type: string;
  entity_id: string;
  action: string;
  actor: string;
  actor_role: string;
  previous_state: string | null;
  new_state: string | null;
  reason: string | null;
  correlation_id: string | null;
  metadata_json: Record<string, unknown>;
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
