export type Event = {
  id: string;
  type: string;
  title: string;
  detail: string;
  agent: string;
  status: string;
  created_at: string;
  data: Record<string, unknown>;
};
export type Segment = { segment: string; count: number; color: string };
export type Campaign = {
  id: string;
  name: string;
  target_segment: string;
  offer_amount: number;
  minimum_bill: number;
  start_date: string;
  end_date: string;
  budget: number;
  max_customers: number;
  language: string;
  ab_test: boolean;
  status: string;
  created_at: string;
  variants: {
    id: string;
    name: string;
    offer_amount: number;
    minimum_bill: number;
  }[];
  stats: {
    allocated: number;
    redeemed: number;
    returning_customers: number;
    discount_expense: number;
    conversion_rate: number;
    incremental_gross_profit: number | null;
    control_conversion_rate: number;
    treatment_conversion_rate: number;
    preliminary: boolean;
  };
  assignments: { customer_token: string; variant: string; redeemed: boolean }[];
};
export type Summary = {
  merchant: { id: string; name: string; location: string; category: string };
  period_days: number;
  metrics: {
    revenue: number;
    previous_revenue: number;
    revenue_change: number;
    returning_customers: number;
    at_risk_customers: number;
    average_basket: number;
    transactions: number;
    bulk_orders: number;
    campaign_redemptions: number;
    discount_expense: number;
    incremental_gross_profit: number;
    active_agents: number;
  };
  revenue_trend: { date: string; revenue: number; transactions: number }[];
  retention_trend: { week: string; returning: number; new: number }[];
  segments: Segment[];
  category_revenue: { category: string; revenue: number }[];
  cohorts: { cohort: string; size?: number; values: (number | null)[] }[];
  campaigns: Campaign[];
  recent_events: Event[];
  recommendation: {
    title: string;
    description: string;
    offer_amount: number;
    minimum_bill: number;
    eligible_customers: number;
    projected_gross_profit: number;
    projection: true;
  };
  provider: { mode: string; configured: boolean };
  security: { blocked: number; eligible: number };
  bulk_performance: { month: string; orders: number; total: number }[];
};
export type Customer = {
  customer_token: string;
  total_transactions: number;
  lifetime_spend: number;
  average_transaction_value: number;
  last_transaction_date: string;
  first_transaction_date: string;
  average_intervisit_interval: number | null;
  previous_30_day_spend: number;
  current_30_day_spend: number;
  customer_segment: string;
  risk_score: number;
  estimated_lost_revenue: number;
  recency_days: number;
  frequency: number;
  monetary: number;
};
export type Product = {
  id: string;
  name: string;
  category: string;
  unit: string;
  selling_price: number;
  available_stock: number;
  purchase_price: number;
  minimum_selling_price: number;
  supplier: string;
  updated_at: string;
};
export type Quote = {
  seller_id: string;
  seller_name: string;
  products: {
    product_id: string;
    name: string;
    quantity: number;
    unit_price: number;
    total: number;
  }[];
  subtotal: number;
  delivery_cost: number;
  discounts: number;
  total_amount: number;
  delivery_date: string;
  validity: string;
  round_number: number;
  status: string;
  summary: string;
};
export type Session = {
  id: string;
  status: string;
  round_number: number;
  budget: number;
  requirement: string;
  items: { product_id: string; name: string; quantity: number; unit: string }[];
  quotes: Quote[];
  rounds: { round_number: number; quotes: Quote[]; summary: string }[];
  best_deal: Quote | null;
  provider: string;
  events: Event[];
  optimization_explanation?: string;
  explanation_provider?: string;
};
export type Decision = {
  id: string;
  status: string;
  allowed: boolean;
  reasons: string[];
  rules: { rule: string; passed: boolean }[];
  amount: number;
  budget: number;
  created_at: string;
};
export type Health = {
  status: string;
  demo_mode: boolean;
  database: string;
  redis: string;
  sarvam: {
    configured: boolean;
    chat_model: string;
    stt_model: string;
    tts_model: string;
  };
  payment_provider: string;
};
export type Agent = {
  id: string;
  name: string;
  status: string;
  current_task: string;
  last_action: string;
  duration_ms: number;
  tool_calls: number;
};
export type Order = {
  id: string;
  status: string;
  total_amount: number;
  total?: number;
  seller_name?: string;
  seller_id?: string;
  payment_state?: string;
  payment?: { state: string };
  created_at: string;
  items: Quote["products"];
  [key: string]: unknown;
};
export type VoiceMessage = { role: string; content: string };
export type VoiceResult = {
  session_id: string;
  transcript: string;
  response: string;
  proposal: {
    id: string;
    action: string;
    parameters: Record<string, unknown>;
    status: string;
  } | null;
  provider: string;
  demo: boolean;
  error?: string;
};
export type Page<T> = {
  items: T[];
  total: number;
  page: number;
  page_size: number;
};

export type CustomerDetail = {
  customer: Customer;
  transactions: {
    id: string;
    customer_token: string;
    amount: number;
    category: string;
    created_at: string;
    campaign_id: string | null;
    simulated: boolean;
  }[];
  spend_trend: { date: string; amount: number }[];
  insights: {
    cadence_status: "within_cadence" | "overdue" | "insufficient_history";
    spend_change_percent: number | null;
    description: string;
    expected_interval_days: number | null;
    inactivity_threshold_days: number | null;
  };
  rfm: { recency_days: number; frequency: number; monetary: number };
  synthetic: true;
};
export type ParsedBuyerRequest = {
  requirement: string;
  items: { product_id: string; name: string; quantity: number; unit: string }[];
  budget: number | null;
  delivery_date: string | null;
  provider: string;
  demo: boolean;
  error?: string | null;
  review_required: true;
  status: "parsed" | "partial" | "unavailable";
  unmatched_items: { name: string; reason: string }[];
  missing_fields: string[];
};
