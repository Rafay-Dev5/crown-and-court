import { useEffect, useState } from "react";
import { isMusicMuted, setMusicMuted, subscribeMusic, unlockAudio } from "../audio";

export default function MusicButton({ className = "" }: { className?: string }) {
  const [muted, setMuted] = useState(isMusicMuted);

  useEffect(() => subscribeMusic(() => setMuted(isMusicMuted())), []);

  return (
    <button
      type="button"
      className={`btn-outline text-xs py-1.5 px-3 ${className}`}
      title="Original royalty-free court music"
      onClick={() => {
        unlockAudio();
        setMusicMuted(!muted);
      }}
    >
      {muted ? "Music off" : "Music on"}
    </button>
  );
}
