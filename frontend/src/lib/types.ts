/** Contratos da API. Espelham os serializers do Django. */

export type Role = "ORGANIZER" | "CUSTOMER" | "GATE";

export type User = {
  id: number;
  email: string;
  full_name: string;
  role: Role;
};

export type LoginResponse = {
  access: string;
  refresh: string;
  user: User;
};

export type EventKind = "GA" | "SEATED";
export type EventStatus = "DRAFT" | "PUBLISHED";
export type Source = "TMDB" | "TICKETMASTER";

/** O que a vitrine pública recebe. */
export type PublicEvent = {
  id: number;
  title: string;
  description: string;
  image_url: string;
  venue: string;
  starts_at: string;
  kind: EventKind;
  price: string;
  available: number;
  organizer_name: string;
  source: Source;
};

/** O que o organizador recebe — inclui rascunho e estoque. */
export type OrganizerEvent = PublicEvent & {
  external_id: string;
  status: EventStatus;
  capacity: number;
  sold_count: number;
  created_at: string;
};

export type CatalogItem = {
  source: Source;
  external_id: string;
  title: string;
  description: string;
  image_url: string;
  venue: string;
  starts_at: string | null;
};

export type SeatStatus = "AVAILABLE" | "SOLD";

export type Seat = {
  id: number;
  section: string;
  row: string;
  number: number;
  price: string;
  status: SeatStatus;
};

/** Entrada do gerador de mapa (só o organizador manda isto). */
export type SeatSection = {
  name: string;
  rows: string[];
  seats_per_row: number;
  price: string;
};

export type TicketStatus = "VALID" | "USED";

export type Ticket = {
  id: number;
  code: string;
  status: TicketStatus;
  used_at: string | null;
  qr_payload: string;
  share_token: string;
  event: number;
  event_title: string;
  event_starts_at: string;
  venue: string;
  seat_label: string | null;
};

export type SharedTicket = {
  status: TicketStatus;
  event_title: string;
  event_starts_at: string;
  venue: string;
  customer_name: string;
  seat_label: string | null;
};

export type ReservationStatus = "PENDING" | "PAID" | "REFUSED" | "CANCELLED";

export type Payment = {
  id: number;
  status: "CONFIRMED" | "REFUSED";
  reason: string;
  created_at: string;
};

export type Reservation = {
  id: number;
  event: number;
  event_title: string;
  event_starts_at: string;
  status: ReservationStatus;
  quantity: number;
  total_price: string;
  created_at: string;
  tickets: Ticket[];
  payments: Payment[];
};

export type PayResponse = {
  payment: Payment;
  tickets: Ticket[];
};

/** Painel de vendas do organizador. */
export type Sale = {
  id: number;
  customer_name: string;
  customer_email: string;
  status: ReservationStatus;
  quantity: number;
  total_price: string;
  created_at: string;
  tickets_used: number;
  tickets_total: number;
  seats: string[];
};

export type SalesResponse = {
  summary: {
    event_id: number;
    event_title: string;
    capacity: number;
    sold_count: number;
    available: number;
    /** String, não número: dinheiro nunca trafega como float. */
    revenue: string;
    paid_reservations: number;
    tickets_issued: number;
    tickets_used: number;
  };
  sales: Sale[];
};

export type GateResult = "VALID" | "INVALID" | "ALREADY_USED" | "WRONG_EVENT";

export type GateResponse = {
  result: GateResult;
  detail: string;
  ticket?: {
    customer_name: string;
    event_title: string;
    seat_label: string | null;
  };
};

export type GateEvent = {
  id: number;
  title: string;
  venue: string;
  starts_at: string;
};

/** A paginação padrão do DRF (PageNumberPagination). */
export type Page<T> = {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
};
