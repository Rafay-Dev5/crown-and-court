import { useEffect, useMemo, useRef, useState } from "react";
import type { PublicSeat, Whisper } from "../store/gameStore";

type Props = {
  seats: PublicSeat[];
  yourId: string;
  whispers: Whisper[];
  onSend: (to: string, text: string) => void;
};

export default function WhisperPanel({ seats, yourId, whispers, onSend }: Props) {
  const others = seats.filter((s) => s.player_id !== yourId);
  const [open, setOpen] = useState(false);
  const [peer, setPeer] = useState(others[0]?.player_id ?? "");
  const [text, setText] = useState("");
  const [seen, setSeen] = useState(0);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!peer && others[0]) setPeer(others[0].player_id);
  }, [others, peer]);

  const thread = useMemo(
    () => whispers.filter((w) => w.from_id === peer || w.to_id === peer),
    [whispers, peer]
  );
  const unread = Math.max(0, whispers.length - seen);

  useEffect(() => {
    if (open) {
      setSeen(whispers.length);
      endRef.current?.scrollIntoView({ block: "nearest" });
    }
  }, [open, whispers.length, thread.length]);

  const send = () => {
    const body = text.trim();
    if (!peer || !body) return;
    onSend(peer, body);
    setText("");
  };

  return (
    <>
      <button
        type="button"
        className="btn-outline text-[11px] sm:text-xs py-1 px-2 relative"
        onClick={() => setOpen((v) => !v)}
      >
        Whisper
        {unread > 0 && !open && (
          <span className="absolute -top-1.5 -right-1.5 min-w-4 h-4 px-1 rounded-full bg-red-700 text-[10px] leading-4 text-white">
            {unread}
          </span>
        )}
      </button>
      {open && (
        <div className="fixed z-40 bottom-[max(0.75rem,env(safe-area-inset-bottom))] right-2 sm:right-4 w-[min(22rem,calc(100vw-1rem))] panel-parchment p-3 shadow-xl">
          <div className="flex items-center justify-between gap-2 mb-2">
            <p className="font-display text-sm text-royal-dark">Private note</p>
            <button type="button" className="text-xs text-royal-dark/60" onClick={() => setOpen(false)}>
              Close
            </button>
          </div>
          <select
            className="w-full text-sm mb-2 bg-white/70 border border-royal-gold/40 rounded px-2 py-1 text-royal-dark"
            value={peer}
            onChange={(e) => setPeer(e.target.value)}
          >
            {others.map((s) => (
              <option key={s.player_id} value={s.player_id}>
                {s.player_name}
              </option>
            ))}
          </select>
          <div className="h-40 overflow-y-auto scrollbar-thin bg-royal-dark/5 rounded px-2 py-1 mb-2 space-y-1">
            {thread.length === 0 && (
              <p className="text-xs text-royal-dark/50 italic">Only the two of you can read this.</p>
            )}
            {thread.map((w) => {
              const mine = w.from_id === yourId;
              return (
                <p key={w.id} className={`text-xs leading-snug ${mine ? "text-right" : ""}`}>
                  <span className="text-royal-dark/50">{mine ? "You" : w.from_name}: </span>
                  <span className="text-royal-dark">{w.text}</span>
                </p>
              );
            })}
            <div ref={endRef} />
          </div>
          <form
            className="flex gap-1"
            onSubmit={(e) => {
              e.preventDefault();
              send();
            }}
          >
            <input
              className="flex-1 min-w-0 text-sm bg-white/80 border border-royal-gold/40 rounded px-2 py-1 text-royal-dark"
              maxLength={240}
              placeholder="Offer a deal…"
              value={text}
              onChange={(e) => setText(e.target.value)}
            />
            <button type="submit" className="btn-royal text-xs py-1 px-2" disabled={!text.trim() || !peer}>
              Send
            </button>
          </form>
        </div>
      )}
    </>
  );
}
