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
| 4. Breadline & MCS Schedule Templates | on board | x −1710…−110, y 5110…6010 |

Sections stack vertically; all flowcharts share the x = −910 left edge so they
read top to bottom in one column.

## Layout

See `board-layout.md` for the current positions of every item and for the
Miro API behaviours that make this board awkward to edit programmatically.
