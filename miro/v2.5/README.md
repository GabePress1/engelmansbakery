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
python3 verify.py "<workbook.xlsm>"                  # overlap check + 10 formulas vs raw sheet XML
```

Every formula on a card is taken from `formulas.json`, which reads the workbook's own
cell XML. Card wording, flowcharts and issues are written in `build.py`.

`extract.py` re-anchors shared formulas: Excel stores one master formula for a filled
range and the other cells only point at it, so a child cell's A1 references must be
shifted by its offset from the master (Recon!F7 is `C7-E7`, not the master's `C5-E5`).

## Layout

Ten frames, left to right at y = 450, 400 px apart. Inside each frame (frame-relative):

| Element | Position |
|---|---|
| Title (67 px bold) / subtitle (22 px) | x 64, baselines y 120 / 184 |
| Flowchart, Mermaid, 1600 × 900 | x 64…1664, y 240…1140 |
| Card stacks, one per table | from x 1728 (x 64 in frame 9), 352 apart |
| Stack heading (22 px bold, ≤ 23 characters) | baseline y 262 |
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
| 8 | Recon | 31808 | 2464 | 16 | 3458764685005827237 | 3458764685005827259 |
| 9 | Known issues, ranked | 34672 | 1152 | 15 | 3458764685005827484 | — |

All frames sit at y = 450. 327 cards, 410 widgets in total. Deep link to a frame: `https://miro.com/app/board/uXjVHiOiwa0=/?moveToWidget=<frame id>`.

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

## Diagram placement

- A new diagram's x/y is its **top-left**, as the composer spec says. The first build assumed
  centre (from the older board) and every flowchart landed 800 px right and 450 px down, over
  the cards. Frames 2–9 were then moved by (+800, +450) so their flowcharts sit at (64, 240).
- A diagram can never be moved or deleted through the API. One that is attached to a frame
  moves only with its frame, keeping its offset from the frame's top-left corner.
- `canvas_create_from_svg` may relocate a whole batch it thinks collides (section 0 was pushed
  4902 px down once, with nothing in the way). `canvas_update_from_svg` places new widgets
  exactly, so sections 0 and 1 were rebuilt through it with the diagram nested in the frame.
- Leftovers to delete by hand: two frames titled "OLD COPY - delete this frame" at y 9000
  (deleting a frame removes its diagram too) and a stray copy of the section-0 flowchart at
  (864, 5592), id 3458764685007733034.
