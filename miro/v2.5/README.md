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

Ten frames, left to right at y = 0, 400 px apart. Inside each frame (frame-relative):

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
| 0 | Overview and legend | 0 | 3168 | 39 | 3458764685004170153 | 3458764685004170216 |
| 1 | Master data | 3568 | 3872 | 46 | 3458764685004524539 | 3458764685004524612 |
| 2 | Business Central exports | 7840 | 3872 | 31 | 3458764685004855392 | 3458764685004855435 |
| 3 | Inventory, Sunday to Friday | 12112 | 3168 | 31 | 3458764685005044059 | 3458764685005044108 |
| 4 | Daily Supply and Demand | 15680 | 3872 | 48 | 3458764685005179569 | 3458764685005179635 |
| 5 | DoughWeights | 19952 | 2816 | 18 | 3458764685005312292 | 3458764685005312324 |
| 6 | Mix-Slice-Oven | 23168 | 3872 | 58 | 3458764685005590032 | 3458764685005590121 |
| 7 | MCS and Breadline schedules | 27440 | 3168 | 24 | 3458764685005711509 | 3458764685005711545 |
| 8 | Recon | 31008 | 2464 | 16 | 3458764685005827237 | 3458764685005827259 |
| 9 | Known issues, ranked | 33872 | 1152 | 15 | 3458764685005827484 | — |

327 cards, 410 widgets in total. Deep link to a frame: `https://miro.com/app/board/uXjVHiOiwa0=/?moveToWidget=<frame id>`.

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

## Placement caveat

Flowcharts are placed outside their frame at absolute coordinates, because Miro reads a new
diagram's x/y as its **centre** (see `../board-layout.md`, behaviour 3). `build.py` therefore
authors each diagram at (frame x + 864, 690). The API echoes those numbers back unchanged,
so they cannot confirm the rendered position. If a flowchart sits over the cards instead of
to their left, the diagram was placed by its corner: drag it 800 px left and 450 px up in
the Miro UI. Diagrams cannot be moved or deleted through the API.
