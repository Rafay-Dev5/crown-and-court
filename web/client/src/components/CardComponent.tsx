import { useCallback, useEffect, useRef, useState } from "react";
import { describeCardSummary } from "../cardText";
import type { CardData } from "../store/gameStore";
import CardPreview from "./CardPreview";

type Props = {
  card: CardData;
  selected?: boolean;
  onClick?: () => void;
  faceDown?: boolean;
  small?: boolean;
  /** When false, no hover/tap preview (e.g. decorative backs). Default true for face-up. */
  previewable?: boolean;
};

const categoryColors: Record<string, string> = {
  economy: "border-emerald-600",
  alliance: "border-blue-600",
  betrayal: "border-red-700",
  disruption: "border-orange-600",
  protection: "border-purple-600",
  tempo: "border-cyan-600",
  information: "border-indigo-600",
  supercard: "border-yellow-600",
};

const HOVER_DELAY_MS = 180;
const LONG_PRESS_MS = 420;

export default function CardComponent({
  card,
  selected,
  onClick,
  faceDown,
  small,
  previewable = true,
}: Props) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const hoverTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pressTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const suppressClick = useRef(false);
  const [hovering, setHovering] = useState(false);
  const [pinned, setPinned] = useState(false);
  const [anchor, setAnchor] = useState<DOMRect | null>(null);

  const showPreview = previewable && !faceDown && (hovering || pinned);

  const clearHoverTimer = () => {
    if (hoverTimer.current) {
      clearTimeout(hoverTimer.current);
      hoverTimer.current = null;
    }
  };

  const clearPressTimer = () => {
    if (pressTimer.current) {
      clearTimeout(pressTimer.current);
      pressTimer.current = null;
    }
  };

  const measure = useCallback(() => {
    const el = wrapRef.current;
    if (el) setAnchor(el.getBoundingClientRect());
  }, []);

  const openHover = useCallback(() => {
    measure();
    setHovering(true);
  }, [measure]);

  const closeHover = useCallback(() => {
    clearHoverTimer();
    setHovering(false);
  }, []);

  const dismissPinned = useCallback(() => {
    setPinned(false);
    setHovering(false);
  }, []);

  useEffect(() => {
    if (!showPreview) return;
    const onScroll = () => measure();
    window.addEventListener("scroll", onScroll, true);
    window.addEventListener("resize", onScroll);
    return () => {
      window.removeEventListener("scroll", onScroll, true);
      window.removeEventListener("resize", onScroll);
    };
  }, [showPreview, measure]);

  useEffect(
    () => () => {
      clearHoverTimer();
      clearPressTimer();
    },
    []
  );

  if (faceDown) {
    return (
      <div
        className={`card-back flex-shrink-0 ${small ? "w-14 h-20" : "w-24 h-36"} flex items-center justify-center`}
      >
        <img src="/assets/card-back.svg" alt="" className="w-8 h-8 opacity-60" />
      </div>
    );
  }

  const borderClass = categoryColors[card.category ?? ""] ?? "border-royal-gold";

  const onMouseEnter = () => {
    if (window.matchMedia("(hover: hover)").matches === false) return;
    clearHoverTimer();
    hoverTimer.current = setTimeout(openHover, HOVER_DELAY_MS);
  };

  const onMouseLeave = () => {
    closeHover();
  };

  const onPointerDown = (e: React.PointerEvent) => {
    if (e.pointerType === "mouse") return;
    clearPressTimer();
    pressTimer.current = setTimeout(() => {
      suppressClick.current = true;
      measure();
      setPinned(true);
    }, LONG_PRESS_MS);
  };

  const onPointerUp = () => {
    clearPressTimer();
  };

  const onPointerCancel = () => {
    clearPressTimer();
  };

  const handleClick = () => {
    if (suppressClick.current) {
      suppressClick.current = false;
      return;
    }
    // Touch: second tap on same card while pinned dismisses; first tap still selects.
    if (pinned) {
      dismissPinned();
      return;
    }
    onClick?.();
  };

  return (
    <div
      ref={wrapRef}
      className="relative flex-shrink-0"
      onMouseEnter={previewable ? onMouseEnter : undefined}
      onMouseLeave={previewable ? onMouseLeave : undefined}
      onPointerDown={previewable ? onPointerDown : undefined}
      onPointerUp={previewable ? onPointerUp : undefined}
      onPointerCancel={previewable ? onPointerCancel : undefined}
      onContextMenu={previewable ? (e) => e.preventDefault() : undefined}
    >
      <button
        type="button"
        onClick={handleClick}
        className={`card-face flex-shrink-0 text-left transition-all duration-200 ${small ? "w-14 h-20 p-1" : "w-24 h-36 p-2"} ${borderClass} border-l-4 ${selected ? "ring-2 ring-royal-gold scale-105 -translate-y-2" : "hover:-translate-y-1"} ${onClick || previewable ? "cursor-pointer" : "cursor-default"}`}
      >
        {!small && (
          <>
            <p className="text-[10px] uppercase tracking-wide opacity-60">{card.category}</p>
            <p className="font-display text-xs font-bold leading-tight mt-1">{card.name}</p>
            <p className="text-[9px] mt-1 line-clamp-3 opacity-80">
              {describeCardSummary(card)}
            </p>
          </>
        )}
        {small && (
          <p className="text-[8px] font-bold truncate">{card.name}</p>
        )}
      </button>
      {showPreview && anchor && (
        <CardPreview
          card={card}
          anchor={anchor}
          pinned={pinned}
          onDismiss={dismissPinned}
        />
      )}
    </div>
  );
}
