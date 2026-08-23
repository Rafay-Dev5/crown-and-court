import { useEffect, useState } from "react";
import CardComponent from "./CardComponent";
import type { CardData } from "../store/gameStore";

type Props = {
  hand: CardData[];
  nPlay: number;
  onSubmit: (indices: number[]) => void;
};

export default function PlayPanel({ hand, nPlay, onSubmit }: Props) {
  const [selected, setSelected] = useState<number[]>([]);

  useEffect(() => {
    setSelected([]);
  }, [hand, nPlay]);

  const toggle = (idx: number) => {
    setSelected((prev) => {
      if (prev.includes(idx)) return prev.filter((i) => i !== idx);
      if (prev.length >= nPlay) return prev;
      return [...prev, idx];
    });
  };

  return (
    <div className="panel-parchment p-4">
      <p className="font-display text-sm mb-1">
        Select {nPlay} card{nPlay > 1 ? "s" : ""} ({selected.length}/{nPlay})
      </p>
      <p className="text-xs text-royal-dark/60 mb-3">
        Cards stay hidden until everyone has locked in. Then they reveal one by one — you will see
        what each card does and click Continue.
      </p>
      <div className="flex gap-2 flex-wrap justify-center mb-4">
        {hand.map((card, i) => (
          <CardComponent
            key={`${card.id}-${i}`}
            card={card}
            selected={selected.includes(i)}
            onClick={() => toggle(i)}
          />
        ))}
      </div>
      <button
        className="btn-royal w-full"
        disabled={selected.length !== nPlay}
        onClick={() => onSubmit(selected)}
      >
        Lock In
      </button>
    </div>
  );
}
