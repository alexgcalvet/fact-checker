// The feedback of a viewer on the public web: one anonymous id and one consent answer in browser storage, on the
// collector's origin. A mark goes to POST /marks and a
// comment on a flag to POST /api/feedback, the collector's existing contracts.

export const PRIVACY = "https://github.com/alexgcalvet/fact-checker/blob/main/PRIVACY.md";
const ID_KEY = "fc-web-id";
const SHARE_KEY = "fc-share";
const QUOTE = 1000; // the collector's limits on a mark
export const REASON = 500;
export const TEXT_MAX = 1000; // the collector's limit on a feedback text and quote

// Browser storage, or this page's memory when the browser refuses storage (private mode, blocked site data).
const memory = new Map<string, string>();
const stored = {
  get: (key: string) => { try { return localStorage.getItem(key); } catch { return memory.get(key) ?? null; } },
  set: (key: string, value: string) => { try { localStorage.setItem(key, value); } catch { memory.set(key, value); } },
};

/** The viewer's answer to "share?", or null before they answer. */
export const shared = (): boolean | null => {
  const answer = stored.get(SHARE_KEY);
  return answer ? answer === "yes" : null;
};
export const share = (yes: boolean) => stored.set(SHARE_KEY, yes ? "yes" : "no");

/** Posts `body` to the collector under the browser's anonymous web id. */
export function post(path: string, body: object): Promise<Response> {
  let id = stored.get(ID_KEY);
  if (!id) {
    id = crypto.randomUUID();
    stored.set(ID_KEY, id);
  }
  return fetch(path, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ...body, install_id: id }),
  });
}

/** The fields of a flag that a mark carries. */
export interface Marked { id: string; t: number; type: string; label: string; quote: string; confidence: number }
export type Verdict = "correct" | "unfair";

/** Sends one mark; false when the collector's daily stop refuses it. */
export async function sendMark(videoId: string, flag: Marked, verdict: Verdict, reason: string): Promise<boolean> {
  const mark = {
    video_id: videoId, flag_id: flag.id, t: flag.t, type: flag.type, label: flag.label, quote: flag.quote.slice(0, QUOTE),
    confidence: flag.confidence, verdict, reason: reason.slice(0, REASON), provider: null, model: null,
  };
  return (await post("/marks", { helper_version: "web", marks: [mark] })).status !== 429;
}

/** Sends a comment on a flag; `rule` names the prompts rule it disputes, `version` the prompts version. */
export const sendComment = (videoId: string, flagId: string, text: string, more: { rule?: string; version?: string } = {}) =>
  post("/api/feedback", { kind: "flag", video_id: videoId, flag_id: flagId, ...more, text: text.slice(0, TEXT_MAX) });
