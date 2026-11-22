// The viewer's say on a flag (S2): "Correcto", "Injusto" with a reason, or "Matizar" with a comment, on the card over
// the video and in an open row of the panel. Nothing is sent before the viewer agrees once; the answer is kept in
// browser storage. "Injusto" sends a mark and a flag comment naming the flag's rule; "Matizar" sends a flag comment only.
// The design is the brand's feedback on a flag (spec §19.6): the delta colours on the glyph only, never a verdict mark.
import { useEffect, useRef, useState } from "react";
import { post, PRIVACY, REASON, sendComment, sendMark, share, shared, TEXT_MAX, type Verdict } from "../../shared/feedback";
import type { Flag } from "./marks";
import type { Texts } from "./texts";

type Kind = Verdict | "nuance";
/** How a send ended: sent, refused by the daily stop, failed, or not sent because the viewer chose not to share. */
export type Sent = "ok" | "closed" | "failed" | "declined";

/** The viewer's consent, asked once before the first send: `agreed` waits for the answer, `question` is its dialog. */
export function useConsent(t: Texts) {
  const [asking, setAsking] = useState<((yes: boolean) => void) | null>(null);
  // One question for every send, also those given while it waits.
  const waiting = useRef<Promise<boolean> | null>(null);
  const agreed = () => {
    const answer = shared();
    if (answer !== null) return Promise.resolve(answer);
    return (waiting.current ??= new Promise<boolean>((done) => setAsking(() => (yes: boolean) => {
      share(yes);
      setAsking(null);
      waiting.current = null;
      done(yes);
    })));
  };
  const question = asking && (
    <div role="dialog" aria-label={t.say.title} className="sheet consent">
      <span className="sheet-title">{t.say.title}</span>
      <p>{t.say.ask}</p>
      <div className="answers">
        <a href={PRIVACY} target="_blank" rel="noopener">{t.say.privacy}</a>
        <button type="button" className="ghost" onClick={() => asking(false)}>{t.say.no}</button>
        <button type="button" className="act hi" onClick={() => asking(true)}>{t.say.yes}</button>
      </div>
    </div>
  );
  return { agreed, question };
}

/** What the viewer said on this video: their mark of each flag, the question while it waits, the daily stop. */
export function useFeedback(videoId: string, version: string | null | undefined, t: Texts) {
  const [mine, setMine] = useState<Record<string, Kind>>({});
  const [closed, setClosed] = useState(false);
  const { agreed, question } = useConsent(t);
  const more = version ? { version } : {};

  const mark = async (f: Flag, verdict: Verdict, reason = ""): Promise<Sent> => {
    const before = mine[f.id];
    setMine((m) => ({ ...m, [f.id]: verdict }));
    if (!(await agreed())) return "declined";
    try {
      if (!(await sendMark(videoId, f, verdict, reason))) {
        setClosed(true);
        return "closed";
      }
      // A flag marked unfair names its rule: the prompts rule whose id is the flag's label.
      if (verdict === "unfair") {
        const res = await sendComment(videoId, f.id, reason, { rule: f.label, ...more });
        if (!res.ok && res.status !== 429) throw res;
      }
      return "ok";
    } catch {
      setMine((m) => ({ ...m, [f.id]: before }));
      return "failed";
    }
  };
  /** Sends a "Matizar" comment. */
  const comment = async (f: Flag, text: string): Promise<Sent> => {
    if (!(await agreed())) return "declined";
    const res = await sendComment(videoId, f.id, text, more).catch(() => null);
    if (res?.ok) setMine((m) => ({ ...m, [f.id]: m[f.id] ?? "nuance" }));
    return res?.ok ? "ok" : res?.status === 429 ? "closed" : "failed";
  };

  return { mine, closed, mark, comment, question };
}
export type Say = ReturnType<typeof useFeedback>;

/** A comment on the method (S6): on a component of the prompts `version`, and on a rule of it and the exact words
 * quoted, if given. It waits for the same consent as a mark. */
export function usePromptComment(version: string | null | undefined, t: Texts) {
  const { agreed, question } = useConsent(t);
  const send = async (component: string, text: string, more: { rule?: string; quote?: string } = {}): Promise<Sent> => {
    if (!version) return "failed";
    if (!(await agreed())) return "declined";
    const res = await post("/api/feedback", { kind: "prompt", version, component, ...more, text: text.slice(0, TEXT_MAX) }).catch(() => null);
    return res?.ok ? "ok" : res?.status === 429 ? "closed" : "failed";
  };
  return { send, question };
}

const PATHS: Record<Kind, string> = {
  correct: "M3 7.5l2.5 2.5L11 4.5",
  unfair: "M3.5 3.5l7 7M10.5 3.5l-7 7",
  nuance: "M2.5 5.5c1.5-1.2 3-1.2 4.5 0s3 1.2 4.5 0M2.5 9c1.5-1.2 3-1.2 4.5 0s3 1.2 4.5 0",
};
const Glyph = ({ kind }: { kind: Kind }) => (
  <svg aria-hidden="true" width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5"
    strokeLinecap="round" strokeLinejoin="round" className={`glyph g-${kind}`}><path d={PATHS[kind]} /></svg>
);

/** The three actions on one flag, and the reason or comment box that "Injusto" and "Matizar" open; `onOpen` runs when
 * a box opens, and `onClose` when it closes, sent or not. Once marked, they fold into one line with "Cambiar". */
export function Actions({ f, t, say, onOpen, onClose }: { f: Flag; t: Texts; say: Say; onOpen?: () => void; onClose?: () => void }) {
  const [box, setBox] = useState<"unfair" | "nuance" | null>(null);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState<Kind | null>(null);
  const [failed, setFailed] = useState<(() => void) | null>(null);
  const [status, setStatus] = useState("");
  const [changing, setChanging] = useState(false);
  const area = useRef<HTMLTextAreaElement>(null);
  const mine = say.mine[f.id];
  const limit = box === "unfair" ? REASON : TEXT_MAX;

  useEffect(() => {
    // jsdom has no scrollIntoView.
    if (box) area.current!.closest(".say")!.scrollIntoView?.({ block: "nearest" });
  }, [box]);

  const clear = () => {
    setBox(null);
    setText("");
    setStatus("");
    setFailed(null);
  };
  const close = () => {
    if (box) onClose?.();
    clear();
  };
  const done = (kind: Kind, sent: Sent, retry: () => void) => {
    setBusy(null);
    if (sent === "failed") return setFailed(() => retry);
    if (kind === "nuance" && sent !== "ok") return setStatus(sent === "closed" ? t.say.commentsClosed : t.say.notSent);
    close();
    setChanging(false);
  };
  const correct = async () => {
    close();
    setBusy("correct");
    done("correct", await say.mark(f, "correct"), correct);
  };
  const submit = async () => {
    const kind = box!;
    const said = text.trim();
    if (kind === "nuance" && !said) return;
    setFailed(null);
    setStatus("");
    setBusy(kind);
    done(kind, kind === "unfair" ? await say.mark(f, "unfair", said) : await say.comment(f, said), submit);
  };
  const toggle = (kind: "unfair" | "nuance") => {
    if (box === kind) return close();
    if (!box) onOpen?.();
    clear();
    setBox(kind);
  };
  const grow = (el: HTMLTextAreaElement) => {
    el.style.height = "auto";
    el.style.height = `${el.scrollHeight + el.offsetHeight - el.clientHeight}px`;
  };

  if (mine && !busy && !box && !changing) {
    return (
      <div className="say">
        <p className="mine">
          {t.say.yours} <Glyph kind={mine} /><span className="mine-word">{t.say.marked[mine]}</span>{" · "}
          <button type="button" className="change" onClick={() => setChanging(true)}>{t.say.change}</button>
        </p>
        {say.closed && <p className="small dim">{t.say.marksClosed}</p>}
      </div>
    );
  }

  const pill = (kind: Kind, onClick: () => void) => (
    <button type="button" className="act" disabled={!!busy} onClick={onClick}
      aria-pressed={box === kind || mine === kind} {...(kind !== "correct" && { "aria-expanded": box === kind })}>
      <Glyph kind={kind} />{busy === kind && kind === "correct" ? <span className="faint">{t.say.sending}</span> : t.say[kind]}
    </button>
  );
  const error = failed && (
    <p className="say-error"><span aria-hidden="true">!</span> {t.say.failed} · <button type="button" className="change" onClick={failed}>{t.say.retry}</button></p>
  );

  return (
    <div className="say">
      <div role="group" aria-label={t.say.group} aria-busy={!!busy} className="acts">
        {pill("correct", correct)}
        {pill("unfair", () => toggle("unfair"))}
        {pill("nuance", () => toggle("nuance"))}
      </div>
      {box && (
        <div className="say-box">
          <div className="field">
            <textarea ref={area} autoFocus rows={3} maxLength={limit} value={text} readOnly={!!busy}
              aria-label={t.say[box === "unfair" ? "reason" : "comment"]} placeholder={t.say[box === "unfair" ? "reason" : "comment"]}
              onChange={(e) => { setText(e.target.value); grow(e.target); }}
              onKeyDown={(e) => {
                if (e.key === "Escape") close();
                if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) submit();
              }} />
            <span className={`counter${text.length >= limit ? " full" : ""}`}>{text.length} / {limit}</span>
          </div>
          <div className="foot">
            <button type="button" className="ghost" disabled={!!busy} onClick={close}>{t.say.cancel}</button>
            <button type="button" className="act hi" disabled={!!busy || box === "nuance" && !text.trim()} onClick={submit}>
              {busy ? t.say.sending : box === "unfair" ? t.say.save : t.say.send}
            </button>
          </div>
          {error}
        </div>
      )}
      {!box && error}
      {say.closed && <p className="small dim">{t.say.marksClosed}</p>}
      {status && <p className="small dim">{status}</p>}
    </div>
  );
}
