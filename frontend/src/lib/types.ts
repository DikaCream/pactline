export type DealStatus =
  | "CREATED"
  | "DELIVERED"
  | "FAILED"
  | "APPEALED"
  | "SETTLED"
  | "REFUNDED"
  | "CANCELED"
  | "EXPIRED";

export interface Deal {
  id: number;
  buyer: string;
  seller: string;
  hasSeller: boolean;
  amount: bigint;
  terms: string;
  deliverableUrl: string;
  sellerReason: string;
  deadline: number;
  appealBond: bigint;
  status: DealStatus;
  verdict: string;
  reasoning: string;
  rounds: number;
  appealStaked: bigint;
  verdictAt: number;
  secondsToDeadline: number;
  secondsToAppealClose: number;
  isTerminal: boolean;
}

export interface DealSummary {
  id: number;
  amount: bigint;
  status: DealStatus;
  verdict: string;
  hasSeller: boolean;
  buyer: string;
  seller: string;
  deadline: number;
}

export interface Stats {
  deals: number;
  settledCount: number;
  settledAmount: bigint;
  fees: bigint;
  appeals: number;
  overturned: number;
  payouts: bigint;
  escrow: bigint;
}

function addr(v: unknown): string {
  if (v == null) return "";
  if (typeof v === "string") return v;
  if (typeof v === "object") {
    const anyV = v as Record<string, unknown>;
    if ("as_hex" in anyV) return String(anyV.as_hex);
    if ("_as_hex" in anyV) return String(anyV._as_hex);
    if ("hex" in anyV) return String(anyV.hex);
  }
  return String(v);
}

function big(v: unknown): bigint {
  try {
    if (typeof v === "bigint") return v;
    if (typeof v === "string") return v.startsWith("addr#") ? 0n : BigInt(v);
    if (typeof v === "number") return BigInt(v);
  } catch {
    /* keep 0 */
  }
  return 0n;
}

function num(v: unknown): number {
  return Number(big(v));
}

export function toDeal(v: any): Deal {
  return {
    id: num(v.id),
    buyer: addr(v.buyer),
    seller: addr(v.seller),
    hasSeller: Boolean(v.has_seller),
    amount: big(v.amount),
    terms: String(v.terms ?? ""),
    deliverableUrl: String(v.deliverable_url ?? ""),
    sellerReason: String(v.seller_reason ?? ""),
    deadline: num(v.deadline),
    appealBond: big(v.appeal_bond),
    status: (String(v.status ?? "CREATED") as DealStatus),
    verdict: String(v.verdict ?? ""),
    reasoning: String(v.reasoning ?? ""),
    rounds: num(v.rounds),
    appealStaked: big(v.appeal_staked),
    verdictAt: num(v.verdict_at),
    secondsToDeadline: num(v.seconds_to_deadline),
    secondsToAppealClose: num(v.seconds_to_appeal_close),
    isTerminal: Boolean(v.is_terminal),
  };
}

export function toDealSummary(v: any): DealSummary {
  return {
    id: num(v.id),
    amount: big(v.amount),
    status: (String(v.status ?? "CREATED") as DealStatus),
    verdict: String(v.verdict ?? ""),
    hasSeller: Boolean(v.has_seller),
    buyer: addr(v.buyer),
    seller: addr(v.seller),
    deadline: num(v.deadline),
  };
}

export function toStats(v: any): Stats {
  return {
    deals: num(v.deals),
    settledCount: num(v.settled_count),
    settledAmount: big(v.settled_amount),
    fees: big(v.fees),
    appeals: num(v.appeals),
    overturned: num(v.overturned),
    payouts: big(v.payouts),
    escrow: big(v.escrow),
  };
}

export const STATUS_LABEL: Record<string, string> = {
  CREATED: "open for a seller",
  DELIVERED: "delivered, awaiting review",
  FAILED: "failed, appeal window open",
  APPEALED: "appealed, re-review pending",
  SETTLED: "settled, seller paid",
  REFUNDED: "refunded to the buyer",
  CANCELED: "canceled by the buyer",
  EXPIRED: "expired, escrow returned",
};
