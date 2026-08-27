# Miro board payloads — Operating Schedule

Canvas Composer DSL (SVG) payloads for the Miro board **Operating Schedule**
(`https://miro.com/app/board/uXjVHtxtiBg=/`), documenting the Engelman's Master
Scheduling Template workbook.

Each payload is sent with the Miro MCP tool `canvas_create_from_svg`. These are
not plain SVG images and cannot be pasted into Miro directly.

## Sections on the board

| Section | Status | Diagram origin |
|---|---|---|
| 1. Daily Inventory Reconciliation | on board (pre-existing) | x −910, y −1911 |
| 2. Daily Supply & Demand | on board | x −910, y −520 |
| 3. DoughWeights(WhereUsed-TopLvl) | on board | x −910, y 2840 |
| 4. Breadline & MCS Schedule Templates | **NOT YET SENT** | x −910, y 5560 |

Sections stack vertically; all flowcharts share the x = −910 left edge so they
read top to bottom in one column.

## Section 4 placement (verified collision-free)

Checked against all 12 existing board items using oversized estimates for the
auto-expanding widgets (tables and docs size themselves on render).

| Widget | x | y |
|---|---|---|
| Flowchart | −910 → 690 | 5560 → 6460 |
| Findings panel | 760 → 1300 | 5560 → 7010 |
| Spec doc | 1400 → 2190 | 5560 → 8160 |
| Differences table | −910 → 400 | 6540 → 7060 |
| Mix-size table | −910 → 400 | 7200 → 7620 |

Lowest previously occupied y was 5236.

## Caveat

All four specs are transcriptions of formula readings, not machine-verified
pulls from the workbook. The n8n workflow intended to read the sheet directly
(`Operating Schedule – Read (v2)`, id `hu1wnKZ8KfPAIuTm`) has not yet completed
a successful run.
