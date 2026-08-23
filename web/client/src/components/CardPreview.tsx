import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { describeCardFull } from "../cardText";
import type { CardData } from "../store/gameStore";

type Props = {
  card: CardData;
  anchor: DOMRect;
  pinned?: boolean;
  onDismiss?: () => void;
};

const categoryColors: Record<string, string> = {
  economy: "border-emerald-700",
  alliance: "border-blue-700",
  betrayal: "border-red-800",
  disruption: "border-orange-700",
  protection: "border-purple-700",
  tempo: "border-cyan-700",
  information: "border-indigo-700",
  supercard: "border-yellow-700",
};

export default function CardPreview({ card, anchor, pinned, onDismiss }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState({ top: 0, left: 0 });

  const { sections } = describeCardFull(card as Parameters<typeof describeCardFull>[0]);
  const borderClass = categoryColors[card.category ?? ""] ?? "border-royal-gold";

  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const pad = 12;
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    const w = el.offsetWidth;
    const h = el.offsetHeight;

    let left = anchor.right + pad;
    let top = anchor.top;

    if (left + w > vw - pad) {
      left = anchor.left - w - pad;
    }
    if (left < pad) {
      left = Math.max(pad, Math.min(anchor.left + anchor.width / 2 - w / 2, vw - w - pad));
    }
    if (top + h > vh - pad) {
      top = Math.max(pad, vh - h - pad);
    }
    if (top < pad) top = pad;

    setPos({ top, left });
  }, [anchor]);

  useEffect(() => {
    if (!pinned || !onDismiss) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onDismiss();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [pinned, onDismiss]);

  return createPortal(
    <>
      {pinned && (
        <button
          type="button"
          aria-label="Dismiss card preview"
          className="fixed inset-0 z-[90] bg-royal-darker/40 cursor-default border-0"
          onClick={onDismiss}
        />
      )}
      <div
        ref={ref}
        role="dialog"
        aria-label={`${card.name} details`}
        className={`card-preview fixed z-[100] w-72 max-h-[min(80vh,32rem)] overflow-y-auto scrollbar-thin p-4 ${borderClass} border-l-4 ${pinned ? "pointer-events-auto" : "pointer-events-none"}`}
        style={{ top: pos.top, left: pos.left }}
      >
        <p className="text-[10px] uppercase tracking-[0.2em] text-royal-dark/55 font-display">
          {card.category ?? "card"}
          {card.rarity ? ` · ${card.rarity}` : ""}
        </p>
        <h3 className="font-display text-lg font-bold text-royal-dark leading-tight mt-1">
          {card.name}
        </h3>
        {sections.map((section) => (
          <div key={section.title} className="mt-3">
            <p className="text-[10px] uppercase tracking-wider text-royal-gold font-display font-semibold">
              {section.title}
            </p>
            <ul className="mt-1 space-y-1">
              {section.lines.map((line, i) => (
                <li key={i} className="text-xs text-royal-dark/85 leading-snug whitespace-pre-wrap">
                  {line}
                </li>
              ))}
            </ul>
          </div>
        ))}
        {card.flavor_text && (
          <p className="mt-4 pt-3 border-t border-royal-gold/40 text-xs italic text-royal-dark/70 leading-relaxed">
            “{card.flavor_text}”
          </p>
        )}
        {pinned && (
          <p className="mt-3 text-[10px] text-royal-dark/45 text-center">Tap outside to close</p>
        )}
      </div>
    </>,
    document.body
  );
}
