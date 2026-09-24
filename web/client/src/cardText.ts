/**
 * Converts card JSON effects into plain-language text for lay readers.
 */

import { cardNoun, roundNoun, sentence } from "./copy";

type EffectBlock = {
  primitive?: string;
  params?: Record<string, unknown>;
  secondary_effect?: EffectBlock;
};

type ChoiceOption = { id: string; label: string };

const TARGET_LABELS: Record<string, string> = {
  self: "you",
  target: "your chosen opponent",
  king: "the King",
};

function targetLabel(raw: unknown): string {
  if (typeof raw !== "string") return "a player";
  return TARGET_LABELS[raw] ?? raw;
}

function thirdPerson(who: string): boolean {
  return who !== "you";
}

function goldPhrase(amount: unknown, target: unknown, verb: "gain" | "lose" | "steal"): string {
  const n = Number(amount) || 0;
  const who = targetLabel(target);
  if (verb === "gain") return `${who} ${thirdPerson(who) ? "gains" : "gain"} ${n} gold`;
  if (verb === "lose") return `${who} ${thirdPerson(who) ? "loses" : "lose"} ${n} gold`;
  return `${n} gold is taken from ${who === "you" ? "an opponent" : who}`;
}

function successFaces(sides: number, targetMin: number): string {
  const faces: number[] = [];
  for (let n = targetMin; n <= sides; n += 1) faces.push(n);
  if (faces.length === 0) return "no number";
  if (faces.length === 1) return String(faces[0]);
  if (faces.length === 2) return `${faces[0]} or ${faces[1]}`;
  return `${faces.slice(0, -1).join(", ")}, or ${faces[faces.length - 1]}`;
}

function describeDie(sides: number, targetMin: number): string {
  return `Roll a ${sides}-sided die. Success on ${successFaces(sides, targetMin)}.`;
}

function shieldBlurb(p: Record<string, unknown>): [string, string] {
  const blocks = String(p.blocks ?? "gold_theft");
  if (blocks === "force_discard") {
    return [
      "a shield against a forced discard",
      "While it is up, it stops a forced discard revealed after this card. It does not protect gold, and it does not undo a discard revealed before it. A hit keeps the shield. A miss removes it.",
    ];
  }
  const label = blocks.replace(/_/g, " ");
  return [
    `a shield for up to ${p.amount ?? "?"} gold`,
    `While it is up, it can stop a ${label} revealed after this card. It does not undo anything revealed before it. A hit keeps the shield. A miss removes the unused shield.`,
  ];
}

function deferredProtectionLines(what: string, hitWhen: string, outcome: string): string[] {
  return [
    `When this card is revealed, ${what} goes up immediately and stays up through the rest of the reveals.`,
    `The guess is not scored then. It is checked after every card has been revealed, before succession. It hits if ${hitWhen}.`,
    outcome,
  ];
}

function describeTrigger(trigger: Record<string, unknown>): string {
  const t = trigger.type as string;
  if (t === "attacked_this_phase") {
    const atk = trigger.attack_type ? String(trigger.attack_type).replace(/_/g, " ") : "";
    return atk
      ? `you suffered a ${atk} during this round's reveals`
      : `you were attacked in any way during this round's reveals`;
  }
  if (t === "attacker_is") return `that attacker targeted you during this round's reveals`;
  if (t === "succession_imminent") return `a Noble has more gold than the King`;
  if (t === "always") return `always`;
  return t.replace(/_/g, " ");
}

function describeCondition(cond: Record<string, unknown>): string {
  if (cond.prior_choice) {
    const choice = humanizeChoiceId(String(cond.prior_choice));
    const within = cond.within_rounds ? ` in the last ${cond.within_rounds} rounds` : "";
    return `they previously chose “${choice}”${within}`;
  }
  if (cond.target_prior_choice) {
    const choice = humanizeChoiceId(String(cond.target_prior_choice));
    const within = cond.within_rounds ? ` in the last ${cond.within_rounds} rounds` : "";
    return `your target previously chose “${choice}”${within}`;
  }
  if (cond.dice_failed) {
    const within = cond.within_rounds ? ` in the last ${cond.within_rounds} rounds` : "";
    return `they failed a dice roll on a prior card${within}`;
  }
  if (cond.has_status) return `they have the “${cond.has_status}” status`;
  if (cond.alliance_declared_with_target) return `you have a declared alliance with your target`;
  return "a special condition is met";
}

function humanizeChoiceId(id: string): string {
  return id
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

function describeEffectBlock(block: EffectBlock | undefined, depth = 0): string[] {
  if (!block?.primitive) return [];
  const p = block.params ?? {};
  const lines: string[] = [];

  switch (block.primitive) {
    case "gold_gain":
      lines.push(goldPhrase(p.amount, p.target ?? "self", "gain") + ".");
      break;
    case "gold_loss":
      if (p.fraction_of_wealth != null) {
        const pct = Math.round(Number(p.fraction_of_wealth) * 100);
        const who = targetLabel(p.target ?? "self");
        const possessive = who === "you" ? "your" : "their";
        lines.push(`${who} ${thirdPerson(who) ? "loses" : "lose"} ${pct}% of ${possessive} current gold.`);
      } else {
        lines.push(goldPhrase(p.amount, p.target ?? "self", "lose") + ".");
      }
      break;
    case "gold_transfer":
      lines.push(
        `${Number(p.amount) || 0} gold moves from ${targetLabel(p.from ?? "target")} to ${targetLabel(p.to ?? "self")}.`
      );
      break;
    case "steal_card": {
      const thief = targetLabel(p.to ?? "self");
      lines.push(
        `${thief} ${thirdPerson(thief) ? "steals" : "steal"} ${cardNoun(p.count ?? 1)} from ${targetLabel(p.from ?? "target")}.`
      );
      break;
    }
    case "force_discard": {
      const who = targetLabel(p.target ?? "target");
      lines.push(
        `${who} ${thirdPerson(who) ? "chooses" : "choose"} ${cardNoun(p.count ?? 1)} to discard.`
      );
      break;
    }
    case "draw_extra": {
      const who = targetLabel(p.target ?? "self");
      lines.push(`${who} ${thirdPerson(who) ? "draws" : "draw"} ${cardNoun(p.count ?? 1)}.`);
      break;
    }
    case "peek_card": {
      const who = targetLabel(p.target ?? "target");
      lines.push(`You peek at one card in ${who === "you" ? "your" : who + "'s"} hand.`);
      break;
    }
    case "reveal_hand":
      lines.push(`${targetLabel(p.target ?? "target")}'s hand is revealed to everyone.`);
      break;
    case "block_succession":
      if (p.trigger) {
        lines.push(
          ...deferredProtectionLines(
            "the succession block",
            describeTrigger(p.trigger as Record<string, unknown>),
            "A hit keeps the block, so the succession check that follows can be stopped. A miss removes the block before that check."
          )
        );
      } else {
        lines.push("The next succession check is blocked.");
      }
      break;
    case "protect_gold":
      if (p.trigger) {
        const [what, outcome] = shieldBlurb(p);
        lines.push(...deferredProtectionLines(what, describeTrigger(p.trigger as Record<string, unknown>), outcome));
      } else {
        lines.push(`Protect up to ${p.amount ?? "?"} gold for ${roundNoun(p.duration_rounds ?? 1)}.`);
      }
      break;
    case "mark_status": {
      const who = targetLabel(p.target ?? "self");
      lines.push(
        `${who} ${thirdPerson(who) ? "receives" : "receive"} the “${p.status_name}” status for ${roundNoun(p.duration_rounds ?? 2)}.`
      );
      break;
    }
    case "alliance_bonus":
      lines.push(
        `You and the player you target each gain ${p.amount ?? 50} gold, but only if you are allied with them when this resolves. If you are not, the card does nothing.`
      );
      break;
    case "skip_next_play": {
      const who = targetLabel(p.target ?? "target");
      lines.push(`${who} ${thirdPerson(who) ? "plays" : "play"} one fewer card next round.`);
      break;
    }
    case "extra_play": {
      const who = targetLabel(p.target ?? "self");
      lines.push(`${who} may play an extra card next round.`);
      break;
    }
    case "gain_legitimacy":
      lines.push(`${targetLabel(p.target ?? "self")} gain ${p.amount ?? 1} legitimacy.`);
      break;
    case "swap_hands":
      lines.push("Two players swap hands.");
      break;
    case "dice_swing": {
      const choices = (p.choices as ChoiceOption[]) ?? [];
      if (choices.length) {
        lines.push("When revealed, choose one path:");
        for (const c of choices) {
          lines.push(`  • ${c.label}`);
        }
      }
      const branches = (p.branches as Record<string, Record<string, unknown>>) ?? {};
      for (const [choiceId, branch] of Object.entries(branches)) {
        const label = choices.find((c) => c.id === choiceId)?.label ?? humanizeChoiceId(choiceId);
        const die = branch.die as { sides?: number; target_min?: number } | undefined;
        if (die) {
          const sides = die.sides ?? 6;
          const need = die.target_min ?? 4;
          lines.push(`If you chose “${label}”: ${describeDie(sides, need)}`);
        } else {
          lines.push(`If you chose “${label}”:`);
        }
        if (branch.on_success) {
          lines.push(`  Success: ${describeEffectBlock(branch.on_success as EffectBlock).join(" ")}`);
        }
        if (branch.on_failure) {
          lines.push(`  Failure: ${describeEffectBlock(branch.on_failure as EffectBlock).join(" ")}`);
        }
        if (branch.on_failure_status) {
          const st = branch.on_failure_status as Record<string, unknown>;
          lines.push(
            `  On failure you also get “${st.status_name}” for ${roundNoun(st.duration_rounds ?? 2)}.`
          );
        }
      }
      break;
    }
    case "conditional_swing": {
      const cond = p.condition as Record<string, unknown> | undefined;
      if (cond) {
        lines.push(`If ${describeCondition(cond)}:`);
        if (p.effect_if_true) {
          lines.push(`  Then: ${describeEffectBlock(p.effect_if_true as EffectBlock).join(" ")}`);
        }
        if (p.effect_if_false) {
          lines.push(`  Otherwise: ${describeEffectBlock(p.effect_if_false as EffectBlock).join(" ")}`);
        }
      }
      break;
    }
    case "prompt_choice": {
      const options = (p.options as ChoiceOption[]) ?? [];
      lines.push("Choose one:");
      for (const o of options) lines.push(`  • ${o.label}`);
      break;
    }
    case "roll_die": {
      const sides = Number(p.sides) || 6;
      const need = Number(p.target_min) || 4;
      lines.push(describeDie(sides, need));
      break;
    }
    case "conditional_on_status": {
      const who = targetLabel(p.target ?? "target");
      lines.push(`If ${who} has the “${p.status_name}” status:`);
      if (p.effect_if_present) {
        lines.push(`  Then: ${describeEffectBlock(p.effect_if_present as EffectBlock).join(" ")}`);
      }
      if (p.effect_if_absent) {
        lines.push(`  Otherwise: ${describeEffectBlock(p.effect_if_absent as EffectBlock).join(" ")}`);
      }
      break;
    }
    case "conditional_on_choice": {
      const who = targetLabel(p.target ?? "target");
      const choice = humanizeChoiceId(String(p.choice_id ?? "a path"));
      const within = p.within_rounds ? ` in the last ${p.within_rounds} rounds` : "";
      lines.push(`If ${who} previously chose “${choice}”${within}:`);
      if (p.effect_if_match) {
        lines.push(`  Then: ${describeEffectBlock(p.effect_if_match as EffectBlock).join(" ")}`);
      }
      if (p.effect_if_no_match) {
        lines.push(`  Otherwise: ${describeEffectBlock(p.effect_if_no_match as EffectBlock).join(" ")}`);
      }
      break;
    }
    default:
      lines.push(`${block.primitive.replace(/_/g, " ")} (see technical details).`);
  }

  if (block.secondary_effect) {
    lines.push("Then: " + describeEffectBlock(block.secondary_effect, depth + 1).join(" "));
  }

  return lines.map((line) => {
    if (line.startsWith("  ") || line.startsWith("Then:") || line.startsWith("If ")) return line;
    return sentence(line);
  });
}

export function describeRequiresState(req: Record<string, unknown> | undefined): string[] {
  if (!req) return [];
  const lines: string[] = ["Can only be played if:"];
  if (req.alliance_declared_with_target) {
    lines.push("  • You have a declared alliance with your target.");
  }
  if (req.prior_choice) {
    lines.push(`  • You previously chose “${humanizeChoiceId(String(req.prior_choice))}”.`);
  }
  if (req.target_prior_choice) {
    const within = req.within_rounds ? ` (within ${req.within_rounds} rounds)` : "";
    lines.push(
      `  • Your target previously chose “${humanizeChoiceId(String(req.target_prior_choice))}”${within}.`
    );
  }
  return lines;
}

export function describeWhiffPenalty(block: EffectBlock | undefined): string[] {
  if (!block) return [];
  return [
    "If the guess misses:",
    ...describeEffectBlock(block).map((l) => `  ${l}`),
  ];
}

export function describeTiming(timing: string): string {
  const map: Record<string, string> = {
    on_reveal: "Resolves when this card is revealed in play order.",
    reactive:
      "Played face-down. It arms when revealed and stays up. The guess is scored after every card has been revealed, before succession.",
    end_of_round: "Resolves at the end of the round.",
    negotiation_only: "Only usable during the negotiation phase.",
  };
  return map[timing] ?? timing;
}

export function describeCardSummary(card: {
  effect?: EffectBlock;
  category?: string;
}): string {
  const lines = describeEffectBlock(card.effect);
  if (lines.length === 0) return "See card details.";
  const first = sentence(lines[0]);
  return first.length > 140 ? first.slice(0, 137) + "…" : first;
}

export function describeCardFull(card: {
  effect?: EffectBlock;
  on_whiff_penalty?: EffectBlock;
  requires_state?: Record<string, unknown>;
  timing?: string;
  category?: string;
  copies_in_deck?: number;
  owner_type?: string;
}): { sections: { title: string; lines: string[] }[] } {
  const sections: { title: string; lines: string[] }[] = [];

  sections.push({
    title: "When it fires",
    lines: [describeTiming(card.timing ?? "on_reveal")],
  });

  const req = describeRequiresState(card.requires_state);
  if (req.length > 1) sections.push({ title: "Requirements", lines: req.slice(1) });

  const effectLines = describeEffectBlock(card.effect);
  if (effectLines.length) sections.push({ title: "What it does", lines: effectLines });

  const whiff = describeWhiffPenalty(card.on_whiff_penalty);
  if (whiff.length) sections.push({ title: "If you guessed wrong", lines: whiff.slice(1) });

  if (card.category === "protection" && !card.on_whiff_penalty) {
    sections.push({
      title: "Note",
      lines: ["This protection card has no miss penalty defined yet."],
    });
  }

  const warnings = cardWarnings(card);
  if (warnings.length) sections.push({ title: "Warning", lines: warnings });

  return { sections };
}

export function cardWarnings(card: {
  category?: string;
  effect?: EffectBlock;
  requires_state?: Record<string, unknown>;
}): string[] {
  const lines: string[] = [];
  const needsAlliance =
    card.category === "alliance" ||
    card.effect?.primitive === "alliance_bonus" ||
    Boolean(card.requires_state?.alliance_declared_with_target);
  if (card.category === "betrayal") {
    lines.push(
      "Betrayal. You still suffer this card's extra cost if a shield blocks the theft."
    );
  }
  if (needsAlliance) {
    lines.push(
      "Needs an alliance with your target. Otherwise this card does nothing."
    );
  }
  return lines;
}
