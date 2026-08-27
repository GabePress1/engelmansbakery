# Operating Schedule board — layout notes

Board: `https://miro.com/app/board/uXjVHtxtiBg=/`

## Layout — four sections, left to right

Each section is a horizontal band at y ≈ −500…3300, separated by a grey
divider bar. Within a section, reading left to right:

`flowchart → findings panel → spec doc → reference tables → divider`

Section origins are 5000 apart. Relative to a section origin `SX`:

| Element | x | y |
|---|---|---|
| Section title / subtitle | SX | −250 / −130 |
| Flowchart (1600 × 900) | SX … SX+1600 | 0 … 900 |
| Findings panel (540 wide) | SX+1700 | 0 |
| Panel text | SX+1730 | see height rule below |
| Spec doc (784 wide) | SX+2340 | 0 |
| Table 1 | SX+3220 | 0 |
| Table 2 | SX+3220 | 1000 |
| Divider bar (10 × 3800) | SX+4700 | −500 |

| Section | SX | Status |
|---|---|---|
| 1. Daily Inventory Reconciliation | 20000 | on board |
| 2. Daily Supply & Demand | 25000 | on board |
| 3. DoughWeights(WhereUsed-TopLvl) | 30000 | on board |
| 4. Breadline & MCS Schedule Templates | 35000 | on board |
| 5. Mix-Slice-Oven Sheet | 40000 | **staged, NOT SENT** — `section5-mix-slice-oven.svg` |

Section 5 differs slightly from the template: its findings panel is 2600 tall (nine
findings) and it carries three tables at y = 0 / 1400 / 2800 rather than two. Its
closing barrier goes at x = 45700. Barrier 4 (x = 39600) is its opening barrier.

Verified: **0 overlaps** across all 32 positioned items in the layout.

## Outstanding — four orphaned diagrams

The original four flowcharts still sit at the old coordinates below and must be
deleted by hand in the Miro UI. **Diagrams cannot be deleted through the API**
(`not deleted: diagrams cannot be deleted`), which is why they are still there.

| Old diagram | Position | Deep link suffix |
|---|---|---|
| Daily Inventory Reconciliation | x −910…690, y −1911…−1011 | `?moveToWidget=3458764681942472410` |
| Daily Supply & Demand | x 328…1928, y −1909…−1009 | `?moveToWidget=3458764681951525078` |
| DoughWeights | x −1710…−110, y 2390…3290 | `?moveToWidget=3458764681952459385` |
| Schedule Templates | x −1710…−110, y 5110…6010 | `?moveToWidget=3458764681955523174` |

## Hard-won API behaviour — read before editing this board

1. **Diagrams cannot be moved OR deleted via SVG.** A position-only stub is
   rejected (`the Mermaid body must not be empty`); resending an unchanged body
   is a no-op; `data-deleted="true"` returns `diagrams cannot be deleted`. The
   only way to reposition one is to create a replacement and delete the
   original by hand.

2. **Miro relocates compositions on create — but only when they collide.** A
   composition created into genuinely empty space keeps its authored
   coordinates exactly. One created over existing content gets translated
   wholesale (section 2 was moved by ~(+2038, −939) originally, which is what
   dropped its diagram onto section 1's). **Always build into empty space, then
   move things in.**

3. **On create, a diagram's x/y is its CENTRE**, not its top-left, despite the
   composer spec. `x=20800, y=450` yields a diagram spanning 20000…21600,
   0…900. Other widget types use top-left.

4. **`<text>` vs `<textArea>` matters on update.** Section titles are
   `textArea`. Sending them as `<text>` is *silently skipped* — absent from
   both `updated_ids` and `failed_items`. Always diff `updated_ids` against
   what you sent.

5. **Tall textAreas are positioned with a stale ~24px height.** The server sets
   the centre to roughly `authoredY + 12` regardless of real height, so a tall
   block ends up centred there and overflows above its panel. To land a block
   with top `T` and height `h`, author `y = T + h/2 − 12`.

6. **Doc position is a top-left anchor.** `board_list_items` reports a *centre*
   for items whose geometry it knows and converts using the width; docs report
   `geometry: null`, so it echoes the raw stored top-left. Do not read a doc's
   reported position as a centre.

7. **Doc updates report a false failure.** Every doc move returns
   `Failed to update doc …: Miro did not confirm whether doc update succeeded`
   while actually applying. To confirm, re-send the same position: `0 updated`
   with `success: true` means it is already there.

8. **`board_list_items` omits docs and tables** from the default listing and
   reports no geometry for them, so an overlap check built only on that listing
   silently ignores them.

## Caveat on content

All four specs are transcriptions of formula readings, not machine-verified
pulls. The n8n workflow meant to read the workbook directly
(`Operating Schedule – Read (v2)`, id `hu1wnKZ8KfPAIuTm`) has not yet completed
a successful run.
