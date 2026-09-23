/** Contract reverts and wallet failures, translated into next-step guidance. */

const RULES: Array<[RegExp, string]> = [
  [/escrow amount must be positive/i, "The escrow must be a positive amount. Send GEN with the deal."],
  [/terms: 1-/i, "The terms need 1 to 4000 characters and cannot be blank."],
  [/deadline must be at least one hour out/i, "The deadline must be at least one hour from now."],
  [/appeal bond below/i, "The appeal bond is below the 0.1 GEN minimum. Raise it or set it to zero."],
  [/appeal bond cannot exceed the escrow/i, "The appeal bond cannot exceed the escrow itself."],
  [/deal is not open for delivery/i, "This deal is no longer open: another seller already took it, or it closed."],
  [/deadline passed/i, "The deadline has passed. This deal can no longer be delivered."],
  [/url must be a public http url|url: 1-/i, "The deliverable URL must be a public http(s) page, 500 characters at most."],
  [/publicly reachable/i, "The URL must be publicly reachable: localhost and private addresses cannot be judged."],
  [/reason: max/i, "Keep the seller note under 500 characters."],
  [/no review pending/i, "This deal has no review pending. It already moved past that state."],
  [/appeal window closed/i, "The appeal window has closed on this deal."],
  [/review rounds exhausted/i, "The review rounds ran out. The deal should refund through expiry or finalize."],
  [/cooldown between reviews/i, "The reviewers are cooling down. Another review can run 5 minutes after the last one."],
  [/nothing to appeal/i, "Only a failed deal with the appeal window open can be appealed."],
  [/this deal carries no appeal bond/i, "This deal carries no appeal bond, so its failure is final. The buyer can finalize the refund."],
  [/only the seller can appeal/i, "Only the seller can stake the appeal bond."],
  [/send exactly the deal's appeal bond/i, "Send exactly the deal's appeal bond amount with the appeal."],
  [/only a failed or appealed deal can be finalized/i, "Finalize closes a failed or appealed deal whose window has passed."],
  [/appeal window still open/i, "The appeal window is still open. Finalize becomes possible once it closes."],
  [/only open deals can be canceled/i, "Only a deal nobody has delivered can be canceled."],
  [/only the buyer can cancel/i, "Only the buyer can cancel this deal."],
  [/deadline slack not elapsed/i, "The deadline plus its grace period has not elapsed yet."],
  [/deal not found/i, "That deal does not exist on this escrow."],
  [/bad pagination/i, "Bad pagination: 1 to 50 deals per page."],
  [/user rejected/i, "The request was rejected in the wallet."],
  [/insufficient funds/i, "The wallet does not cover the amount plus gas."],
  [/chain|network/i, "The wallet is on the wrong network. Switch to GenLayer StudioNet."],
];

export function describeError(e: unknown): string {
  const raw =
    typeof e === "string"
      ? e
      : ((e as any)?.message ?? (e as any)?.shortMessage ?? String(e));
  const text = String(raw);

  for (const [pattern, friendly] of RULES) {
    if (pattern.test(text)) return friendly;
  }

  if (/fetch|network|timeout/i.test(text)) {
    return "The network did not answer. Check the connection and try again.";
  }
  const match = text.match(/UserError[^"]*"([^"]{3,160})"/);
  if (match) return match[1];
  const quoted = text.match(/"([^"]{10,160})"/);
  if (quoted) return quoted[1];
  return text.slice(0, 200) || "Something went wrong. Try again.";
}
