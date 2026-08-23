export type StatusInfo = {
  name: string;
  remaining_rounds: number;
};

export const STATUS_HELP: Record<string, { label: string; description: string }> = {
  oathbreaker: {
    label: "Oathbreaker",
    description:
      "Cannot receive gifted gold in trades. You get this when you accept a one-way gift (they pay you, you pay nothing), or from some cards. Lasts the shown number of rounds. Gifted gold still never counts toward becoming King.",
  },
  marked: {
    label: "Marked",
    description: "Some cards steal extra gold from marked players.",
  },
  corrupt: {
    label: "Corrupt",
    description: "You lose gold at the end of each round while this lasts.",
  },
  discredited: {
    label: "Discredited",
    description: "Some cards force you to discard or reveal your hand.",
  },
  block_succession: {
    label: "Loyal Hold",
    description: "The next succession check cannot change who is King.",
  },
  skip_next_play: {
    label: "Skip Play",
    description: "You play one fewer card in the next play phase.",
  },
  extra_play: {
    label: "Extra Play",
    description: "You play one extra card in the next play phase.",
  },
};

export function getStatusInfo(name: string): { label: string; description: string } {
  return (
    STATUS_HELP[name] ?? {
      label: name.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
      description: "A temporary tag from a card or trade. Hover cards and the Rules button for more.",
    }
  );
}

export function normalizeStatus(raw: StatusInfo | string): StatusInfo {
  if (typeof raw === "string") return { name: raw, remaining_rounds: 1 };
  return raw;
}
