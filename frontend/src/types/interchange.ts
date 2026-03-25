export type RuleType =
  | 'base_rate'
  | 'installment_adjustment'
  | 'cnp_adjustment'
  | 'contactless_adjustment'
  | 'prepaid_adjustment'
  | 'atm_adjustment';

export type CardFamily = 'credit' | 'debit' | 'prepaid' | 'cash_withdrawal';
export type Channel = 'cp' | 'cnp' | 'cp_contactless' | 'atm';
export type Audience = 'PF' | 'PJ' | 'ALL';

export interface InterchangeRule {
  id: string;
  network: string;
  region: string;
  rule_type: RuleType;
  audience: Audience;
  card_family: CardFamily | '—';
  product: string;
  merchant_group: string;
  channel: Channel | '—';
  installment_band: string;
  rate_pct: number | null;
  fixed_fee_amount: number | null;
  cap_amount: number | null;
  confidence_score: number;
}

export interface DashboardBootstrap {
  rules: InterchangeRule[];
  availableFilters: {
    networks: string[];
    cardFamilies: string[];
    ruleTypes: string[];
  };
}

export interface SimulationInput {
  network: string;
  region: string;
  audience: Audience;
  card_family: CardFamily;
  product?: string | null;
  merchant_group?: string | null;
  channel: Channel;
  installment_band?: string | null;
  transaction_amount?: number | null;
}

export interface SimulationResult {
  total_rate_pct: number;
  total_fixed_fee: number;
  estimated_fee_amount: number | null;
  matched_rules: InterchangeRule[];
  notes: string[];
}

export interface CompareNetworkResult {
  network: string;
  total_rate_pct: number;
  total_fixed_fee: number;
  estimated_fee_amount: number | null;
  applied_rules: number;
}
