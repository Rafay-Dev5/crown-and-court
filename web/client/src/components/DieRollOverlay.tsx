import { useEffect, useState } from "react";
import { motion } from "framer-motion";

type Props = {
  roll: number;
  sides: number;
  targetMin: number;
  success: boolean;
  rollerName: string;
  onDone: () => void;
};

function facesNeeded(sides: number, targetMin: number): string {
  const faces: number[] = [];
  for (let n = targetMin; n <= sides; n += 1) faces.push(n);
  if (faces.length <= 1) return String(faces[0] ?? targetMin);
  if (faces.length === 2) return `${faces[0]} or ${faces[1]}`;
  return `${faces.slice(0, -1).join(", ")}, or ${faces[faces.length - 1]}`;
}

export default function DieRollOverlay({ roll, sides, targetMin, success, rollerName, onDone }: Props) {
  const [face, setFace] = useState(1);
  const [landed, setLanded] = useState(false);

  useEffect(() => {
    let ticks = 0;
    const spin = window.setInterval(() => {
      ticks += 1;
      setFace(1 + Math.floor(Math.random() * Math.max(1, sides)));
      if (ticks >= 14) {
        window.clearInterval(spin);
        setFace(roll);
        setLanded(true);
      }
    }, 90);
    const done = window.setTimeout(onDone, 2400);
    return () => {
      window.clearInterval(spin);
      window.clearTimeout(done);
    };
  }, [onDone, roll, sides]);

  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center bg-black/55 pointer-events-none">
      <div className="text-center">
        <motion.div
          className="mx-auto w-24 h-24 sm:w-28 sm:h-28 rounded-2xl border-4 border-royal-gold bg-parchment text-royal-dark flex items-center justify-center font-display text-5xl shadow-2xl"
          animate={
            landed
              ? { rotate: 0, scale: [1.15, 1] }
              : { rotate: [0, 18, -22, 14, -10, 8, 0], scale: [1, 1.06, 0.94, 1.08, 1] }
          }
          transition={landed ? { duration: 0.25 } : { duration: 0.45, repeat: Infinity }}
        >
          {face}
        </motion.div>
        <p className="mt-3 font-display text-parchment text-lg">
          {landed
            ? `${rollerName} rolled ${roll} — ${success ? "success" : "miss"}`
            : `${rollerName} rolls the die…`}
        </p>
        <p className="text-xs text-parchment/70 mt-1">Needed {facesNeeded(sides, targetMin)}</p>
      </div>
    </div>
  );
}
