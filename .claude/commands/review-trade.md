---
description: Generate post-trade review and classification for a specific trade
argument-hint: "<trade-id or filename>"
---

You are reviewing a completed trade from the Crypto Squid trading bot.

**Trade to review:** $ARGUMENTS

## Instructions

1. Read the raw trade journal entry from `journal/raw-trades/` matching the trade ID or date/symbol provided.
2. Read `strategy/core-rules.md` and `strategy/tunable-params.md` for context.
3. Read `strategy/regime-definitions.md` to classify the market regime at trade time.

## Analysis to perform

Answer each question:

1. **Was this a valid setup?** Did all entry conditions pass per core-rules.md?
2. **Rule compliance:** Did the trade follow all Layer 1 rules?
3. **Entry quality:** Early / on-time / late? Was the limit placement optimal?
4. **Exit quality:** Did TP or SL hit? Was the exit level appropriate?
5. **Signal quality:** How strong was the liquidation event (intensity, z-score if available)?
6. **Market behavior:** Did price behave as expected after the liquidation spike?
7. **Loss cause classification** (if a loss):
   - Bad process (rules broken)
   - Bad execution (right idea, wrong entry/exit)
   - Bad model (setup type wrong for regime)
   - Normal variance (valid loss, nothing to change)

## Classification (pick exactly one)
- Valid winner — correct setup, correct execution, won
- Valid loser — correct setup, correct execution, lost (normal variance)
- Invalid winner — wrong setup, won anyway (do NOT repeat)
- Invalid loser — wrong setup, lost (rules were broken)

## Output format

Update the journal markdown file with:
- Completed Classification section
- Completed Regime section
- Diagnosis paragraph
- One-sentence Lesson

Then output a summary to the user.
