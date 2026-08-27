# Operating Schedule board — layout notes

Board: `https://miro.com/app/board/uXjVHtxtiBg=/`

## Current layout

Four diagrams sit in a left column (fixed positions, see below). Each section's
panel, tables and spec doc sit to the right of x = 2150, clear of every diagram.

| Section | Diagram (fixed) | Panel | Spec doc | Tables |
|---|---|---|---|---|
| 1. Daily Inventory Reconciliation | x −910…690, y −1911…−1011 | 2150, −1910 | — | — |
| 2. Daily Supply & Demand | x 328…1928, y −1909…−1009 | 5300, −1860 | 6000, −1860 | 7000, −1860 / 7000, −1300 |
| 3. DoughWeights(WhereUsed-TopLvl) | x −1710…−110, y 2390…3290 | 2150, 2480 | 2810, 2480 | 3710, 2480 / 3710, 3480 |
| 4. Breadline & MCS Schedule Templates | x −1710…−110, y 5110…6010 | 2150, 5200 | 2810, 5200 | 3710, 5200 / 3710, 5900 |

## Known issue

The section 1 and section 2 diagrams overlap by 362 × 897 px. **This cannot be
fixed through the MCP API** — see below. It needs a manual drag in the Miro UI.

## Hard-won API behaviour (read before editing this board)

1. **Miro relocates compositions on create.** Authored coordinates in
   `canvas_create_from_svg` are not honoured when the board's auto-placement
   decides to move the composition. Section 2 was translated by roughly
   (+2038, −939) on create, which is what put its diagram on top of section 1's.
   Always re-read geometry after a create; never trust the authored numbers.

2. **Diagram widgets cannot be moved or deleted via SVG.** A position-only stub
   is rejected with `the Mermaid body must not be empty`, and resending an
   unchanged body is a no-op. Diagrams must be dragged by hand.

3. **`<text>` vs `<textArea>` matters on update.** The section titles are
   `textArea` widgets. Sending them as `<text>` is *silently skipped* — not
   reported in `updated_ids` and not in `failed_items` either. Always check
   `updated_ids` against what you sent.

4. **Tall textAreas are positioned with a stale ~24px height.** The server
   computes the centre as roughly `authoredY + 12` regardless of real height, so
   a tall block ends up centred on that point and overflows above its panel. To
   land a block with top T and height h, author `y = T + h/2 − 12`.

5. **Doc position is a top-left anchor.** `board_list_items` reports a *centre*
   for items whose geometry it knows and converts using the width; docs report
   `geometry: null`, so it echoes the raw stored top-left instead. Do not read a
   doc's reported position as a centre.

6. **Doc updates report a false failure.** Every doc move returns
   `Failed to update doc …: Miro did not confirm whether doc update succeeded`
   while actually applying. To confirm, re-send the same position: a response of
   `0 updated` with `success: true` means it is already there.

## Caveat on content

All four specs are transcriptions of formula readings, not machine-verified
pulls. The n8n workflow meant to read the workbook directly
(`Operating Schedule – Read (v2)`, id `hu1wnKZ8KfPAIuTm`) has not yet completed
a successful run.
