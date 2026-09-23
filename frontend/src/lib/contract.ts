import { CONTRACT_ADDRESS } from "../config";
import { Deal, DealSummary, Stats, toDeal, toDealSummary, toStats } from "./types";

export class PactLine {
  constructor(private client: any, private address: string = CONTRACT_ADDRESS) {}

  private async read(functionName: string, args: unknown[] = []): Promise<any> {
    return this.client.readContract({
      address: this.address as `0x${string}`,
      functionName,
      args,
    });
  }

  private async write(
    functionName: string,
    args: unknown[],
    value: bigint = 0n,
  ): Promise<string> {
    const txHash = await this.client.writeContract({
      address: this.address as `0x${string}`,
      functionName,
      args,
      value,
    });
    return txHash as string;
  }

  async waitForReceipt(txHash: string, retries = 70, interval = 3000): Promise<any> {
    return this.client.waitForTransactionReceipt({
      hash: txHash,
      status: "ACCEPTED" as any,
      retries,
      interval,
    });
  }

  // ---- reads ----------------------------------------------------------
  async getStats(): Promise<Stats> {
    return toStats(await this.read("get_stats"));
  }

  async getDeal(id: number): Promise<Deal | null> {
    try {
      const v = await this.read("get_deal", [id]);
      if (v == null) return null;
      return toDeal(v);
    } catch {
      return null;
    }
  }

  async listDeals(offset = 0, limit = 50, mineOnly = false): Promise<DealSummary[]> {
    const v = await this.read("list_deals", [offset, limit, mineOnly]);
    return Array.isArray(v) ? v.map(toDealSummary) : [];
  }

  // ---- writes ---------------------------------------------------------
  createDeal(terms: string, deadlineSec: number, appealBondWei: bigint, escrowWei: bigint) {
    return this.write("create_deal", [terms, deadlineSec, appealBondWei], escrowWei);
  }

  acceptAndDeliver(dealId: number, url: string, reason: string) {
    return this.write("accept_and_deliver", [dealId, url, reason]);
  }

  runReview(dealId: number) {
    return this.write("run_review", [dealId]);
  }

  appeal(dealId: number, bondWei: bigint) {
    return this.write("appeal", [dealId], bondWei);
  }

  finalize(dealId: number) {
    return this.write("finalize", [dealId]);
  }

  buyerCancel(dealId: number) {
    return this.write("buyer_cancel", [dealId]);
  }

  expire(dealId: number) {
    return this.write("expire", [dealId]);
  }
}
