export type StatusInfo = {
  name: string;
  remaining_rounds: number;
};

export const STATUS_HELP: Record<string, { label: string; description: string }> = {
  oathbreaker: {
    label: "Oathbreaker",
    description:
      "You cannot propose a trade, and no one can propose a trade with you. Applied when a gold↔card deal gives you more than twice what the other side got (cards count as 40g each), when a card swap is too one-sided, or by some cards. Lasts the shown number of rounds.",
  },
  marked: {
    label: "Marked",
    description: "Any gold theft against you takes 20% more. A shield that is already up stops the whole amount, including the extra.",
  },
  corrupt: {
    label: "Corrupt",
    description:
      "At the end of each round, you lose 100 gold to the King (or as much as you have left). Lasts the shown number of rounds.",
  },
  discredited: {
    label: "Discredited",
    description: "Any card that forces you to discard makes you discard one extra card. If you do not have that many cards, you discard what you hold.",
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
