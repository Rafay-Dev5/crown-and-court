import { useState } from "react";
import { getStatusInfo, normalizeStatus, type StatusInfo } from "../statusInfo";

type Props = {
  status: StatusInfo | string;
};

export default function StatusBadge({ status }: Props) {
  const info = normalizeStatus(status);
  const help = getStatusInfo(info.name);
  const [open, setOpen] = useState(false);

  return (
    <span className="relative inline-block">
      <button
        type="button"
        className="text-[10px] bg-red-900/70 text-parchment px-1.5 py-0.5 rounded border border-red-500/40 cursor-help"
        title={`${help.label}: ${help.description}`}
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        onClick={(e) => {
          e.stopPropagation();
          setOpen((v) => !v);
        }}
      >
        {help.label}
        {info.remaining_rounds > 0 && (
          <span className="opacity-70"> · {info.remaining_rounds}r</span>
        )}
      </button>
      {open && (
        <span
          role="tooltip"
          className="absolute z-40 left-1/2 -translate-x-1/2 bottom-full mb-1 w-56 rounded-md bg-royal-darker border border-royal-gold/50 p-2 text-[11px] text-parchment shadow-xl leading-snug"
        >
          <strong className="text-royal-gold font-display">{help.label}</strong>
          <span className="block mt-1 text-parchment/85">{help.description}</span>
        </span>
      )}
    </span>
  );
}
