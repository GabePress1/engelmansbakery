# Master Scheduling v2.5 — Logic Map (Miro)

Board: https://miro.com/app/board/uXjVHiOiwa0=/

Documents `Master Scheduling - 09.19.26 Thur 09.25.26 Gabe Press Version v2.5 - Claude.xlsm`:
what is typed, what is pasted from Business Central, what is calculated, and where each
column feeds. The older "Operating Schedule" board (`uXjVHtxtiBg=`) documents v2.4 and was
left untouched.

## Rebuild

```sh
python3 extract.py "<workbook.xlsm>" formulas.json   # formulas + cached values, stdlib only
python3 build.py                                     # frame0.svg ... frame9.svg + manifest.json
python3 spec_content.py                              # specs.json (Logic Spec text + flowcharts)
python3 spec.py                                      # spec0.svg ... spec8.svg + spec_manifest.json
python3 verify.py "<workbook.xlsm>"                  # overlap check + 10 formulas vs raw sheet XML
```

Every formula on a card is taken from `formulas.json`, which reads the workbook's own
cell XML. Card wording, flowcharts and issues are written in `build.py`. The Logic Spec
text is written in `spec_content.py`, which quotes formulas through the same helpers and
asserts that every quoted fragment appears verbatim in the workbook formula it comes from.

`extract.py` re-anchors shared formulas: Excel stores one master formula for a filled
range and the other cells only point at it, so a child cell's A1 references must be
shifted by its offset from the master (Recon!F7 is `C7-E7`, not the master's `C5-E5`).

## Layout

Ten frames, left to right at y = 450, 400 px apart. Inside each frame (frame-relative):

| Element | Position |
|---|---|
| Title (67 px bold) / subtitle (22 px) | x 64, text boxes at y 53 / 162, frame width − 128 wide |
| Flowchart, Mermaid, 1600 × 900 | x 64…1664, y 240…1140 |
| Card stacks, one per table | from x 1728 (x 64 in frame 9), 352 apart |
| Stack heading (22 px bold, ≤ 23 characters) | text box 320 wide at y 240 |
| Cards, 320 × 88 | from y 288, 108 apart, at most 16 per column |
| Issues stack (red) | last column |

| # | Frame | x | Width | Cards | Frame id | Diagram id |
|---|---|---|---|---|---|---|
| 0 | Overview and legend | 800 | 3168 | 40 | 3458764685007732985 | 3458764685008008966 (in frame) |
| 1 | Master data | 4368 | 3872 | 46 | 3458764685008428612 | 3458764685008428677 (in frame) |
| 2 | Business Central exports | 8640 | 3872 | 31 | 3458764685004855392 | 3458764685004855435 |
| 3 | Inventory, Sunday to Friday | 12912 | 3168 | 31 | 3458764685005044059 | 3458764685005044108 |
| 4 | Daily Supply and Demand | 16480 | 3872 | 48 | 3458764685005179569 | 3458764685005179635 |
| 5 | DoughWeights | 20752 | 2816 | 18 | 3458764685005312292 | 3458764685005312324 |
| 6 | Mix-Slice-Oven | 23968 | 3872 | 58 | 3458764685005590032 | 3458764685005590121 |
| 7 | MCS and Breadline schedules | 28240 | 3168 | 24 | 3458764685005711509 | 3458764685005711545 |
| 8 | Recon | 31808 | 2464 | 19 | 3458764685005827237 | 3458764685005827259 |
| 9 | Known issues, ranked | 34672 | 1152 | 15 | 3458764685005827484 | — |

All frames sit at y = 450. 330 cards, 413 widgets in total. Deep link to a frame: `https://miro.com/app/board/uXjVHiOiwa0=/?moveToWidget=<frame id>`.

## Colour key

| Card | Mermaid fill | Meaning |
|---|---|---|
| Green `#00b86b` | `#B3E65F` | typed input (here or in the external `_BC.xlsm`) |
| Purple `#8b5cf6` | `#B8ACFB` | pasted Business Central export |
| Blue `#2d9bf0` | `#9CE6FF` | formula on this sheet |
| Orange `#ff8c00` | `#FFB575` | lookup from another sheet, table or file |
| Grey `#8c8c8c` | `#DDDDD8` | printed output, or not used |
| Red `#da0063` | `#FFC6C6` | known issue |
| Dark `#2d3142` | — | note, worked example or saved state |

## Recon table

Recon!A4:G15 is the Excel table **Recon** (made by hand in Excel). Section 8 and its spec name
its columns (Sheet, Array Cell, Array Rows, Adjacent Table, Table Rows, Difference
(Array − Table), Status) instead of letters. `build.py` derives the table formulas from the
workbook's row-5 formulas with `recon_ref()` (C5 → `[@[Array Rows]]`, E5 → `[@[Table Rows]]`)
and asserts the result. Array Rows and Table Rows name a different spill and table on each
row, so they are not calculated columns.

## Logic Spec row

A second row of nine frames at y = 2910, 400 px below the tallest main frame. Each spec sits
directly under its section, with the same x and width, and follows the "Operating Schedule —
Logic Spec" pattern: one step-by-step `flowchart TD` for a single SKU or run, plus four panels.

| Element | Position (frame-relative) |
|---|---|
| Title / subtitle | as in the main row |
| Flowchart, Mermaid TD, 1600 × 900 | x 64…1664, y 240…1140, nested in the frame |
| Panels: Inputs, Formula reference, Worked example, Open questions | from x 1728; 1–3 columns of about 672 px, filled shortest-column-first |

Panel heights are estimated from the text (18 px noto_sans, about 10.6 px a character, 26 px
lines). Every body text box was checked against its panel after placement; if one ever
overflows, put the measured body heights in `spec_measured.json` and run `spec.py --measured`.
Section 9 has no spec: it is already a ranked list.

| # | Spec frame | Frame id | Diagram id | Height |
|---|---|---|---|---|
| 0 | A planning week | 3458764685010249395 | 3458764685010249427 | 1574 |
| 1 | Master data | 3458764685010249396 | 3458764685010249428 | 1314 |
| 2 | Business Central exports | 3458764685010477419 | 3458764685010477453 | 1204 |
| 3 | Inventory, Sunday to Friday | 3458764685010477420 | 3458764685010477454 | 1262 |
| 4 | Daily Supply and Demand | 3458764685010737226 | 3458764685010737265 | 1288 |
| 5 | DoughWeights | 3458764685010737227 | 3458764685010737263 | 1862 |
| 6 | Mix-Slice-Oven | 3458764685011306340 | 3458764685011306377 | 1236 |
| 7 | MCS and Breadline schedules | 3458764685011306341 | 3458764685011306378 | 1392 |
| 8 | Recon | 3458764685010172627 | 3458764685010172645 | 1992 |

## Diagram placement

- A new diagram's x/y is its **top-left**, as the composer spec says. The first build assumed
  centre (from the older board) and every flowchart landed 800 px right and 450 px down, over
  the cards. Frames 2–9 were then moved by (+800, +450) so their flowcharts sit at (64, 240).
- A diagram can never be moved or deleted through the API, even when nested in a frame
  (x/y updates are skipped with "diagram does not support updates to: x/y"). One that is
  attached to a frame moves only with its frame, keeping its offset from the frame's top-left.
- `canvas_create_from_svg` may relocate a whole batch it thinks collides (section 0 was pushed
  4902 px down once, with nothing in the way). `canvas_update_from_svg` places new widgets
  exactly, so sections 0 and 1 and the whole Logic Spec row were placed through it.
- After the cleanup of the old copies, the main-row flowcharts of sections 0 and 1 were found
  off their spots: section 0's at frame-relative (-399, 321), hanging out of the frame's left
  edge, and section 1's at (-425, 259), crossing into frame 0. They have to be dragged back to
  (64, 240) by hand.

## Text boxes

Auto-sized `<text>` widgets are measured slightly narrow on this board and wrap: several
titles came out two lines tall (over the subtitle) and most stack headings wrapped too.
`data-rendered-bounds` in the create result still said one line; only a read-back showed the
stored height (188 instead of 94). Titles, subtitles and headings are therefore fixed-width
`textArea`s, and every one on the board was updated to those widths.
