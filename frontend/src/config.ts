export const NETWORK: "localnet" | "studionet" =
  (import.meta.env.VITE_NETWORK as "localnet" | "studionet") || "studionet";

export const RPC_URL = (import.meta.env.VITE_RPC_URL as string) || "";

/** Deployed PactLine escrow contract on GenLayer StudioNet. */
export const CONTRACT_ADDRESS =
  (import.meta.env.VITE_CONTRACT_ADDRESS as string) ||
  "0xD5Efa2b53B8C60AcB1A742e42f2cb22AC68ff953";

export const STUDIONET_CHAIN_ID = 777;
export const STUDIONET_CHAIN_ID_HEX = "0x309";

export const EXPLORER_TX = (hash: string) =>
  `https://explorer-studio.genlayer.com/tx/${hash}`;
export const EXPLORER_ADDR = (address: string) =>
  `https://explorer-studio.genlayer.com/address/${address}`;

export const GEN = 10n ** 18n;

/** PactLine's own economics, mirrored from the contract. */
export const MIN_APPEAL_BOND = GEN / 10n; // 0.1 GEN
export const FEE_NUM = 1n;
export const FEE_DEN = 200n; // 0.5% settlement fee
export const MAX_ROUNDS = 4;
export const REVIEW_COOLDOWN = 300; // seconds
export const APPEAL_WINDOW = 3 * 24 * 3600; // seconds
export const DEADLINE_SLACK = 6 * 3600; // seconds

export const REPO_URL = "https://github.com/DikaCream/pactline";
export const RAW_FIXTURE_URL =
  "https://raw.githubusercontent.com/DikaCream/pactline/main/contracts/pact_line.py";

export function toBigInt(value: bigint | number | string): bigint {
  try {
    return typeof value === "bigint" ? value : BigInt(value ?? 0);
  } catch {
    return 0n;
  }
}

/** GEN amounts stay legible, never a wall of zeros. */
export function formatGen(value: bigint | number | string, maxDecimals = 4): string {
  let wei = toBigInt(value);
  const negative = wei < 0n;
  if (negative) wei = -wei;

  const scale = 10n ** BigInt(maxDecimals);
  const whole = wei / GEN;
  const frac = ((wei % GEN) * scale) / GEN;
  const fracStr = frac.toString().padStart(maxDecimals, "0").replace(/0+$/, "");

  if (whole === 0n) {
    if (fracStr === "") {
      return wei === 0n ? "0" : `<0.${"0".repeat(maxDecimals - 1)}1`;
    }
    return `${negative ? "-" : ""}0.${fracStr}`;
  }
  return `${negative ? "-" : ""}${whole}${fracStr ? `.${fracStr}` : ""}`;
}

export function shortAddr(a: string): string {
  if (!a) return "";
  const hex = a.startsWith("addr#") ? "0x" + a.slice(5) : a;
  if (hex.length < 12) return hex;
  return `${hex.slice(0, 6)}…${hex.slice(-4)}`;
}

export function hexAddr(a: string): string {
  if (!a) return "";
  return a.startsWith("addr#") ? "0x" + a.slice(5) : a;
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

export function formatClock(unix: number): string {
  if (!unix) return "n/a";
  const d = new Date(unix * 1000);
  const pad = (n: number) => n.toString().padStart(2, "0");
  return `${MONTHS[d.getUTCMonth()]} ${d.getUTCDate()}, ${d.getUTCFullYear()} ${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())} UTC`;
}

export function untilClock(unix: number, nowSec = Math.floor(Date.now() / 1000)): string {
  const s = unix - nowSec;
  if (s <= 0) return "passed";
  const d = Math.floor(s / 86400);
  const h = Math.floor((s % 86400) / 3600);
  const m = Math.floor((s % 3600) / 60);
  if (d > 0) return `${d}d ${h}h left`;
  if (h > 0) return `${h}h ${m}m left`;
  return `${m}m left`;
}

export function hostOf(url: string): string {
  try {
    return new URL(url).host.replace(/^www\./, "");
  } catch {
    return url;
  }
}
