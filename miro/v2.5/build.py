"""Build the Miro payloads for the Master Scheduling v2.5 logic map.

Reads formulas.json (made by extract.py from the workbook) so that every formula on a
card is the workbook's own text, not a retyping. Card wording, flowcharts and issues
are authored below, one FRAME per board section. Writes frame0.svg ... frame9.svg.

Layout (per frame, frame-relative):
  title / one-line subtitle: fixed-width text boxes, tops at y 53 / 162
  flowchart 1600x900 at (64, 240), nested in the frame <g> so it moves with the frame
      (its x/y is the diagram's top-left, as the composer spec says). A diagram can never be
      moved through the API on its own. Send each frame with canvas_update_from_svg, which
      places exactly; canvas_create_from_svg may relocate a batch it thinks collides.
  card stacks from x 1728 (or 64 with no flowchart), 352 apart; heading box 320 wide at y 240,
      cards 320x88 from y 288 on a 108 pitch, at most MAXC cards per column
Frames sit side by side from (FRAME_X0, FRAME_Y0) with a 400px gutter. The board's frames
were moved to (800, 450) after the first build, when the diagrams turned out to be placed by
their top-left corner; these origins reproduce the board as it now stands.
"""
import json
import os
import re
import sys
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
D = json.load(open(os.path.join(HERE, 'formulas.json')))

MAXC = 16
CARD_W, CARD_H, PITCH, COLW = 320, 88, 108, 352
PAD, TOP, GUTTER = 64, 240, 400
FRAME_X0, FRAME_Y0 = 800, 450
DIA_W, DIA_H = 1600, 900

COLOR = {'input': '#00b86b', 'export': '#8b5cf6', 'calc': '#2d9bf0', 'lookup': '#ff8c00',
         'output': '#8c8c8c', 'unused': '#8c8c8c', 'issue': '#da0063', 'note': '#2d3142'}
LABEL = {'input': 'INPUT (typed)', 'export': 'BC EXPORT (pasted)', 'calc': 'FORMULA (this sheet)',
         'lookup': 'LOOKUP (other sheet or table)', 'output': 'OUTPUT', 'unused': 'NOT USED',
         'issue': 'ISSUE', 'note': 'NOTE'}
CLASSDEF = """    classDef input fill:#B3E65F,stroke:#6E9A24,color:#2F440B
    classDef export fill:#B8ACFB,stroke:#8A7BE0,color:#231266
    classDef calc fill:#9CE6FF,stroke:#2C97BB,color:#1C4657
    classDef lookup fill:#FFB575,stroke:#CC7830,color:#542700
    classDef output fill:#DDDDD8,stroke:#8A8A7E,color:#434339
    classDef issue fill:#FFC6C6,stroke:#BD0A0A,color:#5C0A0A
"""


def T(table, name):
    """Formula of a representative data-row cell in table column `name`."""
    for c in D['tables'][table]['cols']:
        if c['name'] == name:
            f = (c.get('cell') or [None])[0]
            if f is None:
                raise KeyError(f'{table}[{name}] has no formula')
            return '=' + f
    raise KeyError(f'{table}[{name}] not found')


def X(ref):
    f = D['cells'][ref][0]
    if f is None:
        raise KeyError(f'{ref} has no formula')
    return '=' + f


def V(ref):
    return D['cells'][ref][1]


def card(title, kind, text):
    return {'title': title, 'kind': kind, 'text': text}


def esc(s):
    return (s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            .replace('"', '&quot;'))


def esc_body(s):
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


FRAMES = []

# ---------------------------------------------------------------- 0 Overview
FRAMES.append({
    'title': '0. Overview and legend',
    'subtitle': 'How data moves through Master Scheduling v2.5, left to right. Colour tells you where every value comes from.',
    'mermaid': r"""flowchart LR
{classdef}
    EXT["_BC.xlsm on SharePoint&lt;br/&gt;day inventory tabs&lt;br/&gt;floor count is typed here"]:::input
    PROD["Products"]:::input
    DOUGH["Dough"]:::input
    UD["Unique Dough"]:::input
    PANS["Pans"]:::input
    CLI["Critical Lookup Information"]:::input
    CTRL["Control cells&lt;br/&gt;H2 anchor date, C5 buffer 1.2&lt;br/&gt;K4 day selector, E4 start times"]:::input
    SH["Sales History"]:::export
    SO["Open Sales Lines"]:::export
    BOM["BOMQty"]:::export
    DAYS["Sunday to Friday&lt;br/&gt;inventory tables"]:::lookup
    DSD["DSD_DSnD&lt;br/&gt;275 pack SKUs"]:::calc
    DIST["Dist_DSnD&lt;br/&gt;120 case SKUs"]:::calc
    DW["DoughWeight&lt;br/&gt;lb of dough per day"]:::calc
    MSO["Mix_Slice_Oven&lt;br/&gt;bags, planned, minutes"]:::calc
    OVEN["Oven_Info&lt;br/&gt;pans to set out"]:::calc
    MCS["MCS Schedule"]:::output
    BL["Breadline Schedule"]:::output
    PIV["Dist Shipping Schedule pivot"]:::output
    REC{{"Recon&lt;br/&gt;row-count check"}}:::calc
    EXT --> DAYS
    PROD --> DAYS
    DAYS -->|"Total"| DSD
    DAYS -->|"Total"| DIST
    SH -->|"4-week average"| DSD
    EXT -->|"case demand"| DIST
    SO -->|"order grids"| DIST
    SO --> PIV
    CTRL --> DSD
    DSD -->|"Production"| DW
    DIST -->|"Production"| DW
    BOM --> DOUGH
    DOUGH -->|"lb per bag"| MSO
    DW --> MSO
    CTRL -->|"K4"| MSO
    UD --> MSO
    MSO --> OVEN
    PANS --> OVEN
    MSO --> MCS
    MSO --> BL
    CLI --> MCS
    CLI --> BL
    OVEN --> MCS
    MSO -.->|"bags and hours"| DSD
    REC -.-> DAYS
    REC -.-> MSO
""",
    'stacks': [
        ('Legend', [
            card('Green: manual input', 'input', 'Typed by a person, either in this workbook or in the external _BC.xlsm file. Change these and everything downstream moves.'),
            card('Purple: Business Central export', 'export', 'Pasted in from a Business Central report. Refreshed by the planner, never calculated.'),
            card('Blue: formula on this sheet', 'calc', 'Calculated from cells on the same sheet or table.'),
            card('Orange: lookup from another sheet', 'lookup', 'Pulled from another sheet, table, or the external _BC.xlsm file (XLOOKUP, SUMIFS, VLOOKUP).'),
            card('Grey: printed output or not used', 'output', 'A printed run sheet or pivot, or a column no formula reads.'),
            card('Red: known issue', 'issue', 'Something that gives a wrong or missing number today. The most important are ranked in section 9.'),
            card('Dark: note', 'note', 'Explanation, worked example or saved state. Not a cell in the workbook.'),
            card('How to read this board', 'note', 'Sections run left to right in data-flow order. In each: the flowchart on the left, then one card stack per table in column order, then a red Issues stack. Open a card to read the full formula and what it feeds.'),
            card('What v2.5 fixed since v2.4', 'note', 'Line totals are now one SUMIFS on Asset (the 14 hand-typed total chains that disagreed are gone). Dough rows roll up by SUMIFS (the 16 missing SUM formulas are gone). Master data moved into Excel tables with structured references.'),
        ]),
        ('Sheets 1/2', [
            card('Products', 'input', 'Table Products, 478 items. Master item list: line (Asset), dough, unique dough, weight, scrap, pans. Section 1.'),
            card('Dough', 'input', 'Table Dough, 63 D-codes. Weight (lb per bag) is a SUMIFS on BOMQty. Section 1.'),
            card('Unique Dough', 'input', 'Table UniqueDough, 139 mixing runs: schedule placement, bags per mix, minutes per mix. Section 1.'),
            card('Pans', 'input', 'Table Pans, 41 pans and boxes: pieces per pan, trays per bag. Feeds Oven_Info. Section 1.'),
            card('Critical Lookup Information', 'input', 'Still live. The schedules read run notes, attributes and bag-mix run times from its D:O copy, not from Unique Dough. Also pallet by customer and packs per case. Section 1.'),
            card('Sales History', 'export', 'Table SalesHistory, 203,445 posted invoice lines (5/2 to 9/23/2026). Only No., Posting Date and Quantity are used. Section 2.'),
            card('Open Sales Lines', 'export', 'Table SalesOrders, 1,438 open order lines. Feeds the Dist_DSnD order grids and the Dist Shipping pivot. Section 2.'),
            card('Business Central Items List', 'unused', 'Table14, 1,244 items. No live formula reads it. Section 2.'),
            card('Sunday', 'lookup', 'Table Sunday. Inventory day tab: every count is an XLOOKUP into the external _BC.xlsm file. Section 3.'),
            card('Monday', 'lookup', 'Table Monday. Initial Inventory = Sunday Final Inventory; counts from _BC.xlsm. Section 3.'),
            card('Tuesday', 'lookup', 'Table Tuesday. Same pattern as Monday. Section 3.'),
            card('Wednesday', 'lookup', 'Table Wednesday. Same pattern as Monday. Section 3.'),
        ]),
        ('Sheets 2/2', [
            card('Thursday', 'lookup', 'Table Thursday. Same pattern as Monday. Section 3.'),
            card('Friday', 'lookup', 'Table Friday. Same pattern as Monday. Section 3.'),
            card('Daily Supply & Demand', 'calc', 'Tables DSD_DSnD (packs) and Dist_DSnD (cases): demand, balance, production per day. Section 4.'),
            card('Dist Shipping Schedule', 'output', 'PivotTable on Open Sales Lines, DIST lines only. Last refreshed 2026-09-18. Section 4.'),
            card('DoughWeights', 'calc', 'Table DoughWeight: pounds of dough needed per day. Also holds the pasted BOMQty export in O:AJ. Section 5.'),
            card('Mix-Slice-Oven', 'calc', 'Tables Mix_Slice_Oven and Oven_Info: bags, planned bags, minutes, slice sheet, pans to set out. K4 picks the day. Section 6.'),
            card('MCS Schedule', 'output', 'Printed mixer run sheet for MCS LINE, built by one dynamic-array formula in A5. Section 7.'),
            card('Breadline Schedule', 'output', 'Printed mixer run sheet for Breadline and Breadline/Artisan, built by A5. Section 7.'),
            card('Recon', 'calc', 'Compares each spill-array row count with its table row count. Section 8.'),
            card('Session Log', 'unused', 'Static notes. Nothing reads it and it reads nothing.'),
            card('Mix Order Backup', 'unused', 'Static backup of an old mix order. Nothing reads it.'),
        ]),
        ('Control cells (typed)', [
            card("'Daily Supply & Demand'!H2 anchor date", 'input', f"Typed Sunday of the week being planned: 2026-09-20. H3:M3 sample dates start at H2-6. Sheet note: update this date in every new template. Feeds: every demand average, DoughWeights F2."),
            card("'Daily Supply & Demand'!C5 buffer", 'input', f"Typed safety buffer = {V('Daily Supply & Demand!C5')}. Every DSD _Demand = ROUNDUP(average x C5). Dist_DSnD demand gets no buffer."),
            card("'Mix-Slice-Oven'!K4 day selector", 'input', f"Typed dropdown = {V('Mix-Slice-Oven!K4')}. Picks the day for Planned Total, the slice sheet, Oven_Info and both schedules, while every header prints TODAY() = {V('Mix-Slice-Oven!R3')}."),
            card('Sunday!B1 week date', 'input', f"Typed date 2026-08-30. Monday to Friday B1 add one day each. Feeds only the Julian Date column."),
            card('Schedule E4 start times', 'input', 'Typed first-mix start: MCS 6:45, Breadline 7:50. Printed only; no finish times are calculated from it.'),
            card("Freeze columns (_Freeze)", 'input', 'Typed per day on DSD_DSnD and Dist_DSnD. All blank today. Floor already includes Freezer, so typing here would double count.'),
            card('Planned Total override', 'input', "Mix_Slice_Oven[Planned Total] = Optimal Total until a person types a number over it. None are overridden today."),
            card('Extra Bread (Runout)', 'issue', 'Mix_Slice_Oven column X is meant for typed runouts, but no formula reads it. Typing a runout changes nothing.'),
        ]),
    ],
})

# ---------------------------------------------------------------- 1 Master data
FRAMES.append({
    'title': '1. Master data',
    'subtitle': 'Products, Dough, Unique Dough, Pans and Critical Lookup Information: the typed lists every other sheet looks up.',
    'mermaid': r"""erDiagram
    classDef input fill:#B3E65F,stroke:#6E9A24,color:#2F440B
    classDef export fill:#B8ACFB,stroke:#8A7BE0,color:#231266
    classDef calc fill:#9CE6FF,stroke:#2C97BB,color:#1C4657
    Products {
        text No PK "item, F5 = case"
        text Gen_Prod_Posting_Group "FG, FG-DIST, OBS"
        text Asset "production line"
        num Weight "lb dough per pack"
        text Unique_Dough FK
        text Dough FK
        num Scrap_Factor
        text Pans_Boxes FK
        num Asset_Rank "formula"
    }
    Dough {
        text No PK "D-code"
        text Description
        num Weight "SUMIFS BOMQty = lb per bag"
    }
    UniqueDough {
        text Dough PK "mixing run name"
        num Placement_On_Scedule "schedule order"
        num Optimal_Bag "bags per mix"
        num Optimal_Time "minutes per mix"
        text Dough_Sku "formula"
    }
    Pans {
        text Pans_Boxes PK
        num Pieces_Per_Pan
        num Trays_Per_1_bag_Mix
    }
    BOMQty {
        text No_Item FK "dough D-code"
        num BOMQty "component lb"
    }
    CriticalLookup {
        text Run_name PK "column D"
        text Notes_and_attributes "E to O"
        num Packs_per_case "Q to S"
    }
    DSD_DSnD {
        text Sku FK
        text Asset "from Products"
    }
    DoughWeight {
        text Sku FK
        num Weight "from Products"
    }
    Mix_Slice_Oven {
        text Sku FK
        num optimal_bags_per_mix "from UniqueDough"
        num Run_Time "from UniqueDough"
    }
    Oven_Info {
        text Finished_Product FK
        num Pieces_Per_Pan "from Pans"
    }
    Schedules {
        text Run FK
        text Attributes "from CriticalLookup"
    }
    Products }o--|| Dough : "Dough"
    Products }o--o| UniqueDough : "Unique Dough"
    Products }o--o| Pans : "Pans/Boxes"
    Dough ||--o{ BOMQty : "No_Item"
    UniqueDough ||--o| CriticalLookup : "duplicate copy"
    Products ||--o{ DSD_DSnD : "No."
    Products ||--o{ DoughWeight : "No."
    Products ||--o{ Mix_Slice_Oven : "No."
    UniqueDough ||--o{ Mix_Slice_Oven : "Dough"
    Pans ||--o{ Oven_Info : "Pans/Boxes"
    UniqueDough ||--o{ Schedules : "placement, bags, time"
    CriticalLookup ||--o{ Schedules : "N to S, D4"
    class Products input
    class Dough input
    class UniqueDough input
    class Pans input
    class CriticalLookup input
    class BOMQty export
    class DSD_DSnD calc
    class DoughWeight calc
    class Mix_Slice_Oven calc
    class Oven_Info calc
    class Schedules calc
""",
    'stacks': [
        ('Products (478 rows)', [
            card('No. (A)', 'input', 'Item number. F5xxxx is the case version of Fxxxx. The key for every lookup in the workbook. Feeds: row lists of Sunday to Friday (A3), DSD_DSnD (A8), Dist_DSnD (A287), DoughWeights (A4), Mix-Slice-Oven (A6), Oven_Info (A410).'),
            card('Description (B)', 'input', 'Item name. Feeds: every Description and _Desc column, UniqueDough List of Count. Also searched for the text OBS by the DoughWeights row list (see issue).'),
            card('Gen. Prod. Posting Group (F)', 'input', 'FG (277 packs), FG-DIST (122 cases), OBS (79 obsolete). Feeds: the row lists (day tables FG + FG-DIST, DSD_DSnD FG, Dist_DSnD FG-DIST, Mix-Slice-Oven and Oven_Info skip OBS), DSD_DSnD Gen. Prod., schedule Bag Count DSD vs DIST split.'),
            card('Asset (G)', 'input', 'Production line: Breadline, Breadline/Artisan, MCS LINE, 3rd Party, 3rd Party - Bake, Third Party - Repack, Charges / Fees. Feeds: Asset Rank, DSD_DSnD Asset (3rd-party demand branch, Thursday rule), Mix_Slice_Oven Asset (line totals, schedule filters), Oven_Info Pans. Row lists drop Charges / Fees.'),
            card('Weight (H)', 'input', 'Pounds of dough in one pack. Feeds: DoughWeight Weight (lb = packs short x Weight), DSD_DSnD Dough Weights (display).'),
            card('Unique Dough (I)', 'input', 'The mixing run the item belongs to. Feeds: Mix_Slice_Oven Unique Dough (bags are summed per run), Oven_Info, UniqueDough Count and List of Count, Mix-Slice-Oven A6 sort.'),
            card('Packs Per Tray/Case (J)', 'input', 'Feeds: Mix_Slice_Oven Units per case/Tray, then #of Trays/Cases Needed on the slice sheet.'),
            card('Pieces Per Tray/Case (K)', 'input', 'Feeds: Oven_Info # of pieces per tray/box, then # of Pans/Boxes to set out.'),
            card('Dough (L)', 'input', 'Dough D-code. Feeds: Dough Description, DoughWeights A4 grouping (each dough followed by its products), Mix_Slice_Oven Dough (the Dough[Weight] divisor), Mix-Slice-Oven A6.'),
            card('Dough Description (M)', 'lookup', f"Formula: {T('Products', 'Dough Description')}. Feeds: DoughWeight Dough Desc, the key dough rows are summed on."),
            card('Scrap Factor (N)', 'input', 'Multiplier for waste, for example 1.1. Feeds: Mix_Slice_Oven Scrap Factor (bags x scrap).'),
            card('Asset Rank (P)', 'calc', f"Formula: {T('Products', 'Asset Rank')}. 1 Breadline, 2 Breadline/Artisan, 3 MCS LINE, 4 to 6 third party, 99 anything else. Feeds: Mix-Slice-Oven A6 keeps rank 1 to 3 and sorts by it."),
            card('Pans/Boxes (Q)', 'input', 'Pan or box the item is baked or packed in. Feeds: Oven_Info A410 row list and # of Pans/Boxes to set out.'),
            card('Non Case Sku (R)', 'calc', f"Formula: {T('Products', 'Non Case Sku')}. F53070 becomes F3070. Feeds: Mix_Slice_Oven Notes (flags Case Total)."),
            card('Not used: 5 columns', 'unused', 'Production BOM No. (C), Unit Cost (D), Unit Price (E), Batch Size (O), Topping (S). No formula reads them.'),
        ]),
        ('Dough (63 rows)', [
            card('No. (A)', 'input', 'Dough D-code. Feeds: DoughWeights A4 (one block per dough), the Dough Weight SUMIFS key, Products Dough Description.'),
            card('Description (B)', 'input', 'Feeds: Products Dough Description, DoughWeight and Mix_Slice_Oven Description on dough rows, UniqueDough Dough Desc.'),
            card('Weight (I)', 'lookup', f"Pounds in one bag (batch) of dough. Formula: {T('Dough', 'Weight')}. Feeds: Mix_Slice_Oven Weight, Dough Weight (L) and every _Bags column: bags = lb / this. See issue: multi-level BOMs are double counted."),
            card('Uni Dou # (J)', 'calc', f"Formula: {T('Dough', 'Uni Dou #')}. Number of mixing runs that use this dough. Display only."),
            card('Uni Dou Desc (K)', 'calc', f"Formula: {T('Dough', 'Uni Dou Desc')}. Display only."),
            card('Not used: 6 columns', 'unused', 'Type, Item Tracking Code, Production BOM No., Unit Cost, Unit Price, Gen. Prod. Posting Group.'),
        ]),
        ('Unique Dough (139 rows)', [
            card('Dough (A)', 'input', 'Mixing run name; must match Products Unique Dough exactly. Feeds: Mix_Slice_Oven bags-per-mix and run-time lookups, Oven_Info, the schedule A5 lookups.'),
            card('Placement On Scedule (C)', 'input', 'Order of the run on the day. Feeds: schedule A5 SORTBY; MCS Changeover rows sit at the placement above + 0.5. Text or blank sorts last (9999).'),
            card('Optimal Bag (D)', 'input', 'Bags per mix. Feeds: Mix_Slice_Oven optimal bags per mix (CEILING step), Oven_Info Daily Bags Per Mix, schedule mixes per run = ROUNDUP(bags / this).'),
            card('Optimal Time (E)', 'input', 'Minutes per mix. Feeds: Mix_Slice_Oven Run Time Per Mix, every _Minutes column, the schedule time column. 7 runs are blank.'),
            card('Count (P)', 'calc', f"Formula: {T('UniqueDough', 'Count')}. Display only."),
            card('List of Count (Q)', 'calc', f"Formula: {T('UniqueDough', 'List of Count')}. Display only."),
            card('Dough Sku (R)', 'lookup', f"Finds the dough header row above this run on Mix-Slice-Oven. Formula: {T('UniqueDough', 'Dough Sku')}. Feeds: Dough Uni Dou # and Uni Dou Desc."),
            card('Dough Desc (S)', 'lookup', f"Formula: {T('UniqueDough', 'Dough Desc')}. Display only."),
            card('Not read by any formula: 11 columns', 'unused', 'Pan Constraints, 4 Bag Mix, 3 Bag Mix, 2 Bag Mix, 1 Bag Mix, 1.5 Bag Mix, Dough Color, Steamed?, Schedule Notes, Schedule Notes2, Notes. The schedules show these from Critical Lookup Information instead.'),
        ]),
        ('Pans (41 rows)', [
            card('Pans/Boxes (B)', 'input', 'Pan or box name. Feeds: Oven_Info A410 (one block per pan), Oven_Info Pans = Pan test, Trays and Pieces lookups, Mix-Slice-Oven Y1 count and CA500 listing.'),
            card('Pieces Per Pan (C)', 'input', 'Feeds: Oven_Info Pieces Per Pan, the divisor for # of Pans/Boxes to set out.'),
            card('Trays Per 1 bag Mix (D)', 'input', 'Feeds: Oven_Info Trays per 1 Bag Mix (display).'),
            card('Unique Dough (E)', 'unused', 'No formula reads it.'),
        ]),
        ('Critical Lookup Info', [
            card('Customer to pallet (A:B)', 'input', 'Pallet type per customer. Feeds: Dist Shipping Schedule C2 (for example Chep).'),
            card('Run notes and attributes (D:O)', 'input', "A second copy of the Unique Dough list. D run name, E notes (for example 12 bags max in a single run), then attributes and 4/3/2/1/1.5 bag-mix run times. Feeds: schedule N:S columns and D4. Editing Unique Dough does not change what the schedules print."),
            card('Packs per case (Q:S)', 'input', 'Feeds: Dist_DSnD Column3, cases that can be made from spare DSD packs.'),
            card('Inventory tab by weekday (U:V)', 'calc', f"V10 {X('Critical Lookup Information!V10')} gives today's tab name ({V('Critical Lookup Information!V10')})."),
        ]),
        ('Issues', [
            card('Dough Weight double counts BOM levels', 'issue', 'SUMIFS adds every BOMQty line for the dough, including an intermediate (Liquid Levain 60 lb) and its own flour 30 + water 30. D10057 sums 273.25 lb against a real 213.25, so about 22% too few bags. 11 doughs affected: D10020, D10024, D10025, D10051, D10055 to D10059, D10063, D10064.'),
            card('Two hardcoded Dough weights', 'issue', 'D10004 = 241.8 and D10061 = 236.1 are typed over the SUMIFS, so BOM changes never reach them.'),
            card('OBS filter matches Lobster', 'issue', 'DoughWeights A4 drops any item whose Description contains OBS. Lobster Roll 12pk (F3310) and Cs. LobsterRoll (F53310), both active MCS LINE, never get dough or bags.'),
            card('Schedules ignore Unique Dough edits', 'issue', 'Schedule attributes, notes and D4 run times come from Critical Lookup Information D:O, a separate copy. Update both or retire one.'),
            card('#N/A typed into Products', 'issue', 'Constant #N/A values: Asset 75, Weight 92, Unique Dough 101, Scrap Factor 116, Packs Per Tray/Case 92, Batch Size 238 rows.'),
            card('5 unknown Unique Dough names', 'issue', 'Products uses run names missing from Unique Dough: Gourmet Hawaiian Bun, 8" Philly Roll, 6" Philly Roll, Bread Stick, 0. Their lookups return blank.'),
            card('7 runs have no Optimal Time', 'issue', '2# Sour Dough Batard, 3 LB. Braided, 1.5# Artisan Ciabatta, 1.5# Ciabatta Garlic & Rose, Multigrain Batard, 2# PAL Batard, 1.75# PAL Batard: 0 minutes on the schedule.'),
            card('Stray spaces in 4 run names', 'issue', "'Cntry Wheat Lg Pullman ', 'Country Wheat Hearth ', ' Multigrain Lg Pullman', '22\"19oz Steak Crouton '. Exact-match lookups against Products can miss."),
        ]),
    ],
})

# ---------------------------------------------------------------- 2 Exports
FRAMES.append({
    'title': '2. Business Central exports',
    'subtitle': 'Pasted, never calculated. Only a few columns of each export are used; the rest are shown grey.',
    'mermaid': r"""flowchart LR
{classdef}
    SH["Sales History&lt;br/&gt;posted invoice lines&lt;br/&gt;203,445 rows"]:::export
    SO["Open Sales Lines&lt;br/&gt;open order lines&lt;br/&gt;1,438 rows"]:::export
    BOM["BOMQty&lt;br/&gt;Quantity Explosion of BOM&lt;br/&gt;15,118 rows, as of 03/24/26"]:::export
    IL["Business Central Items List&lt;br/&gt;Table14, 1,244 rows"]:::output
    DSD["DSD_DSnD H:M&lt;br/&gt;4-week same-weekday average"]:::calc
    GRID["Dist_DSnD order grids&lt;br/&gt;0_, 1_, 2_"]:::calc
    PIV["Dist Shipping Schedule&lt;br/&gt;PivotTable, DIST only"]:::output
    DW["Dough Weight&lt;br/&gt;lb per bag"]:::lookup
    MSO["Mix_Slice_Oven&lt;br/&gt;bags = lb / Dough Weight"]:::calc
    NONE["no live formula"]:::issue
    SH -->|"No., Posting Date, Quantity"| DSD
    SO -->|"No., Quantity, Shipment Date"| GRID
    SO -->|"Outstanding Qty by customer and date"| PIV
    BOM -->|"No_Item, BOMQty"| DW
    DW --> MSO
    IL -.-> NONE
""",
    'stacks': [
        ('Sales History', [
            card('SalesHistory table', 'export', 'Sheet Sales History. BC Posted Sales Invoice Lines, 203,445 rows, posting dates 5/2 to 9/23/2026. About 145 MB, roughly 91% of the file. Only about 20% of the rows fall inside the 4-week window.'),
            card('No. (E)', 'export', 'Item number. Feeds: DSD_DSnD Sun/Mon to Fri/Sat, the SUMIFS item criterion.'),
            card('Posting Date (G)', 'export', "Feeds: the same SUMIFS, matched to the sample dates in 'Daily Supply & Demand'!H3:M3 minus 0, 7, 14 and 21 days."),
            card('Quantity (L)', 'export', 'Packs sold. Summed by the DSD_DSnD demand formulas.'),
            card('Not used: 14 columns', 'unused', 'Document No., Sell-to Customer No., Sell-to Customer Name, Type, Description, Gen. Bus. Posting Group, Gen. Prod. Posting Group, Pc Code, Dept Code, Unit of Measure Code, Unit Price Excl. Tax, Amount, Amount Including Tax, Line Discount %.'),
        ]),
        ('Open Sales Lines', [
            card('SalesOrders table', 'export', 'Sheet Open Sales Lines. BC Sales Lines (open orders), 1,438 rows, shipment dates 9/22 to 9/24.'),
            card('No. (F)', 'export', 'Feeds: Dist_DSnD order grids (SUMIFS item), DSD or DIST, pivot rows.'),
            card('Quantity (J)', 'export', 'Feeds: Dist_DSnD order grids 0_Sun to 2_Sat.'),
            card('Shipment Date (N)', 'export', 'Feeds: order grids (matched to the row 284 dates), pivot columns.'),
            card('Outstanding Quantity (O)', 'export', 'Feeds: the Dist Shipping Schedule pivot values.'),
            card('Customer, Document No., Description', 'export', 'Sell-to Customer Name (D), Document No. (B), Description (G) are pivot row and column fields only.'),
            card('DSD or DIST (P)', 'calc', f"Formula: {T('SalesOrders', 'DSD or DIST')}. Feeds: the pivot page filter (DIST)."),
            card('Not used: 8 columns', 'unused', 'Document Type, Sell-to Customer No., Type, Location Code, Reserve, Reserved Qty. (Base), Unit of Measure Code, Line Amount Excl. Tax.'),
        ]),
        ('BOMQty export', [
            card('BOMQty table', 'export', "Sheet DoughWeights, columns O:AJ. BC Quantity Explosion of BOM report, 15,118 rows. Header says As of 03/24/26."),
            card('No_Item (T)', 'export', 'Dough D-code the exploded line belongs to. Feeds: Dough Weight SUMIFS criterion.'),
            card('BOMQty (AF)', 'export', 'Pounds of each component line, every BOM level. Summed into Dough Weight (lb per bag).'),
            card('Not used: 20 columns', 'unused', 'AsOfCalcDate, CompanyName, TodayFormatted, ItemTableCaptionFilter, ItemFilter, Desc_Item, the caption columns, BomCompLevelNo, BomCompLevelDesc, FormatLevel, BomCompLevelQty, BomCompLevelUOMCode, Column1.'),
            card('Stray cell ZZ7', 'calc', f"'Mix-Slice-Oven'!ZZ7 {X('Mix-Slice-Oven!ZZ7')} reads BOMQty by whole column. Scratch work; nothing reads it."),
        ]),
        ('Other pasted sheets', [
            card('Table14 (Items List)', 'unused', "Business Central Items List, 16 columns, 1,244 rows. No live formula reads it. Only DSD_DSnD Gen. Prod.'s stored table formula points here, so it would come back if that column were refilled."),
            card('Session Log', 'unused', 'Static text, unreferenced.'),
            card('Mix Order Backup', 'unused', 'Static values, unreferenced.'),
        ]),
        ('Weekly routine', [
            card('1. Paste Sales History', 'input', 'At least 21 days before the anchor week plus the sample week, so all four same-weekday samples exist.'),
            card("2. Set 'Daily Supply & Demand'!H2", 'input', 'Type the new planning Sunday. H3:M3 and every demand average follow.'),
            card('3. Paste Open Sales Lines', 'input', 'Then refresh the Dist Shipping Schedule pivot.'),
            card('4. Retype order-grid dates', 'input', "Row 284 dates above each 0_/1_/2_ grid. They must be real dates, not text."),
            card('5. Refresh BOMQty when BOMs change', 'input', 'Paste the Quantity Explosion of BOM into DoughWeights O:AJ; Dough Weight recalculates.'),
            card('6. Set K4 and check Recon', 'input', 'Pick the production day on Mix-Slice-Oven K4, then confirm Recon shows no Array longer.'),
        ]),
        ('Issues', [
            card('BOMQty is six months old', 'issue', 'As of 03/24/26. Any BOM change since then is missing from Dough Weight and every bag count.'),
            card('BOMQty headers shifted', 'issue', 'The last labels sit one column off the data: BomCompLevelQty holds a dot, BomCompLevelUOMCode holds the quantity and Column1 holds the unit (LB). The BOMQty column itself is correct.'),
            card('Labor Day inside the sample', 'issue', 'Sun/Mon samples 9/14, 9/7, 8/31, 8/24. 9/7 was Labor Day with near-zero sales, pulling the Monday average down by up to a quarter.'),
            card('Sales History is 91% of the file', 'issue', '145 MB of rows, 80% of them outside the window. Trim to the last 5 weeks before pasting.'),
        ]),
    ],
})

# ---------------------------------------------------------------- 3 Inventory
FRAMES.append({
    'title': '3. Inventory, Sunday to Friday',
    'subtitle': 'Nobody types inventory in this workbook: every count is an XLOOKUP into the external _BC.xlsm file on SharePoint.',
    'mermaid': r"""flowchart LR
{classdef}
    EXT["_BC.xlsm on SharePoint&lt;br/&gt;tabs Sunday - Inventory ... Friday-Inventory&lt;br/&gt;floor count typed here"]:::input
    PROD["Products&lt;br/&gt;A3 row list: FG + FG-DIST&lt;br/&gt;395 SKUs"]:::input
    SUN["Sunday&lt;br/&gt;Initial = external column C"]:::lookup
    MON["Monday"]:::lookup
    TUE["Tuesday"]:::lookup
    WED["Wednesday"]:::lookup
    THU["Thursday"]:::lookup
    FRI["Friday"]:::lookup
    TOT["Total = Freezer + Floor&lt;br/&gt;- Late/Day Orders - Inv. Discounts"]:::calc
    FIN["Final Inventory =&lt;br/&gt;Total + Wrapped - Order"]:::calc
    DIF["Diferencias =&lt;br/&gt;Initial - (Freezer + Floor)"]:::calc
    DSD["DSD_DSnD _Floor"]:::calc
    DIST["Dist_DSnD 0_Inventory"]:::calc
    PROD --> SUN
    EXT -->|"Freezer, Floor, Late/Day,&lt;br/&gt;Wrapped, Order, Discounts"| SUN
    EXT --> MON
    EXT --> TUE
    EXT --> WED
    EXT --> THU
    EXT --> FRI
    SUN -->|"Final to Initial"| MON
    MON -->|"Final to Initial"| TUE
    TUE -->|"Final to Initial"| WED
    WED -->|"Final to Initial"| THU
    THU -->|"Final to Initial"| FRI
    FRI -. each day .-> TOT
    TOT --> FIN
    TOT --> DIF
    TOT -->|"that day"| DSD
    TOT -->|"today"| DIST
""",
    'stacks': [
        ('Sunday table (395 rows)', [
            card('Row list (A3 spill)', 'lookup', f"Formula: {X('Sunday!A3')}. 275 FG packs then 120 FG-DIST cases. Same formula on every day sheet."),
            card('Code (B)', 'calc', f"Formula: {T('Sunday', 'Code')}. Feeds: every lookup on the row, DSD_DSnD and Dist_DSnD SUMIFS/XLOOKUP key."),
            card('Description (C)', 'lookup', f"Formula: {T('Sunday', 'Description')}."),
            card('Initial Inventory (D)', 'lookup', f"Opening stock. Sunday only reads the external file: {T('Sunday', 'Initial Inventory')}. Monday to Friday use the previous day's Final Inventory."),
            card('Freezer (Day Before) (E)', 'input', 'Blank on Sunday. Monday to Friday calculate it (see right). Nothing reads it.'),
            card('Diferencias (F)', 'calc', f"Count check: what the chain says we had against what was counted. Formula: {T('Sunday', 'Diferencias')}. Display only."),
            card('Freezer (G)', 'lookup', f"Formula: {T('Sunday', 'Freezer')}. Column F of the external tab."),
            card('Floor (H)', 'lookup', 'External column G, same XLOOKUP pattern.'),
            card('Late/Day Orders (I)', 'lookup', 'External column H. Already promised, so subtracted from Total.'),
            card('Total (J)', 'calc', f"Stock on hand. Formula: {T('Sunday', 'Total')}. Feeds: DSD_DSnD S_Floor (SUMIFS), Dist_DSnD 0_/1_/2_Inventory when today is Sunday."),
            card('Wrapped (K)', 'lookup', 'External column J: baked and wrapped today.'),
            card('Order (L)', 'lookup', 'External column K: shipped today.'),
            card('Final Inventory (M)', 'calc', f"Closing stock. Formula: {T('Sunday', 'Final Inventory')}. Feeds: Monday Initial Inventory."),
            card('Inv. Discounts (N)', 'lookup', 'External column M. Subtracted from Total.'),
            card('QC columns (O:T)', 'input', 'Notes, Temp, Weight, Color Lok, Bag Lot, New Bag Lot. Typed on the sheet, all blank, nothing reads them.'),
            card('Julian Date (U)', 'calc', f"Formula: {T('Sunday', 'Julian Date')}. Uses the typed Sunday!B1 date."),
        ]),
        ('Monday to Friday', [
            card('Week date (B1)', 'calc', f"Monday!B1 {X('Monday!B1')}; each later day adds one."),
            card('Initial Inventory (D)', 'lookup', f"Formula: {T('Monday', 'Initial Inventory')}. Tuesday reads Monday, and so on."),
            card('Freezer (Day Before) (E)', 'lookup', f"Formula: {T('Monday', 'Freezer (Day Before)')}. Informational; nothing reads it."),
            card('Counts (G, H, I, K, L, N)', 'lookup', "Same XLOOKUP as Sunday against that day's external tab: 'Monday - Inventory', 'Tuesday -Inventory', 'Wednesday - Inventory', 'Thursday - Inventory', 'Friday-Inventory'."),
            card('Total, Final, Diferencias', 'calc', 'Same formulas as Sunday.'),
        ]),
        ('Purpose and state', [
            card('Why the day tables exist', 'note', 'They turn the floor count into stock on hand (Total). Supply and Demand nets that against expected demand, Final Inventory rolls to the next morning, and Diferencias shows where the count and the chain disagree.'),
            card('Chain balances as saved', 'note', 'Sunday Final 90,429 = Monday Initial 90,429, and so on through the week.'),
            card('Where the week stands', 'note', 'Thursday is partly entered. Friday is not counted yet (Freezer, Floor, Total = 0), which is why Friday production is negative for most items.'),
            card('Worked example: F1000 Rye 1/2"', 'note', 'Sunday: Freezer 79, Order 27, Final 52. Monday: Initial 52, Freezer (Day Before) 79 - 27 = 52, Wrapped 96, Order 9, Final 139.'),
        ]),
        ('Issues', [
            card('Sunday!B1 is three weeks behind', 'issue', 'B1 = 2026-08-30 but the planning anchor is 2026-09-20. Julian dates print 242 to 247 instead of 263 to 268.'),
            card('Tables longer than their row list', 'issue', 'Tuesday +3 rows, Wednesday to Friday +52 rows of #N/A below the spill. Harmless for totals, but untidy (see Recon).'),
            card('SKUs missing from the external tabs', 'issue', 'F6214, F52550, F53220 (and F52540) are not on the _BC.xlsm tabs, so their counts return #N/A.'),
            card('Inconsistent external tab names', 'issue', "'Tuesday -Inventory' and 'Friday-Inventory' break the 'Day - Inventory' pattern. Renaming a tab breaks the link."),
            card('Everything depends on one linked file', 'issue', 'If _BC.xlsm moves or the link breaks, every day table and all distribution demand freeze at their last values.'),
            card('Sheet protection is off', 'issue', 'Protection is defined but not switched on, so formula columns can be typed over.'),
        ]),
    ],
})

# ---------------------------------------------------------------- 4 Supply & Demand
TODAY_BAL = "Today's Balance (correlating DSD item)"
TODAYS_DATE = "Today's Date"
DAYMAP_DSD = 'Sun Q:W, Mon X:AD, Tue AE:AK, Wed AL:AR, Thu AS:AY, Fri AZ:BF'
FRAMES.append({
    'title': '4. Daily Supply and Demand',
    'subtitle': 'DSD_DSnD (packs) and Dist_DSnD (cases): average demand, minus stock on hand, gives what to bake each day.',
    'mermaid': r"""flowchart LR
{classdef}
    SH["Sales History"]:::export
    H2["H2 anchor date&lt;br/&gt;H3:M3 sample dates"]:::input
    AVG["Demand H:M&lt;br/&gt;average of 4 same weekdays&lt;br/&gt;3rd party: 1 week only"]:::calc
    C5["C5 buffer 1.2"]:::input
    DEM["_Demand = ROUNDUP(avg x 1.2)&lt;br/&gt;Thursday non-MCS adds Fri/Sat"]:::calc
    DAYS["Sunday to Friday Total"]:::lookup
    FLOOR["_Floor"]:::lookup
    FRZ["_Freeze&lt;br/&gt;typed, blank"]:::input
    BAL["_Balance =&lt;br/&gt;Freeze + Floor - Demand"]:::calc
    PRD["_Production = Balance&lt;br/&gt;negative = bake this many"]:::calc
    EXTD["_BC.xlsm Daily Supply and Demand&lt;br/&gt;E249:L374"]:::input
    DDEM["Dist demand H:M&lt;br/&gt;no buffer"]:::lookup
    DPRD["Dist _Production = - Demand"]:::calc
    SO["Open Sales Lines"]:::export
    GRID["Order grids 0_ 1_ 2_"]:::calc
    CLI["Critical Lookup&lt;br/&gt;packs per case"]:::input
    BR["Case to pack bridge&lt;br/&gt;spare DSD packs / packs per case"]:::calc
    OUT["DoughWeights, Mix-Slice-Oven,&lt;br/&gt;Oven_Info"]:::calc
    MSO["Mix-Slice-Oven rows 1-2&lt;br/&gt;bags and hours"]:::lookup
    SH --> AVG
    H2 --> AVG
    AVG --> DEM
    C5 --> DEM
    DAYS --> FLOOR
    FLOOR --> BAL
    FRZ --> BAL
    DEM --> BAL
    BAL --> PRD
    PRD --> OUT
    EXTD --> DDEM
    DDEM --> DPRD
    DPRD --> OUT
    SO --> GRID
    DAYS -->|"today"| GRID
    BAL -->|"today, DT2"| BR
    CLI --> BR
    MSO -.->|"W1:W4 per day"| PRD
""",
    'stacks': [
        ('Control cells', [
            card('B1 today', 'calc', f"{X('Daily Supply & Demand!B1')}. Display."),
            card('H2 anchor date', 'input', 'Typed planning Sunday, 2026-09-20. Sheet note: update this date in every new template.'),
            card('H3:M3 sample dates', 'calc', f"H3 {X('Daily Supply & Demand!H3')} = 9/14, then one day per column to 9/19. The demand formulas step back 0, 7, 14, 21 days from these."),
            card('C5 buffer', 'input', 'Typed 1.2. Multiplies every DSD _Demand.'),
            card('DT2 weekday index', 'calc', f"{X('Daily Supply & Demand!DT2')} = {V('Daily Supply & Demand!DT2')} (Friday). Saturday counts as 1. Feeds: Dist_DSnD bridge columns DC:DE."),
            card('W1:W4 over each day', 'lookup', f"Planned bags and hours read back from Mix-Slice-Oven. Sunday: W1 {X('Daily Supply & Demand!W1')} = {V('Daily Supply & Demand!W1')} Breadline bags, W2 {X('Daily Supply & Demand!W2')} = {V('Daily Supply & Demand!W2')} h, W3 MCS bags {V('Daily Supply & Demand!W3')}, W4 MCS hours 16.08."),
            card('H283:M285 case totals by line', 'calc', f"H283 {X('Daily Supply & Demand!H283')} = {V('Daily Supply & Demand!H283')}; H284 MCS LINE = {V('Daily Supply & Demand!H284')}; H285 total = {V('Daily Supply & Demand!H285')} (Sun/Mon cases)."),
        ]),
        ('DSD_DSnD 1/2: packs', [
            card('Row list (A8 spill)', 'lookup', f"Formula: {X('Daily Supply & Demand!A8')}. FG only."),
            card('Sku (F)', 'calc', f"Formula: {T('DSD_DSnD', 'Sku')}."),
            card('Asset (B)', 'lookup', f"Formula: {T('DSD_DSnD', 'Asset')}. Feeds: 3rd-party demand branch, Thursday rule."),
            card('Gen. Prod. (C)', 'lookup', f"Formula: {T('DSD_DSnD', 'Gen. Prod.')}. Display."),
            card('Mixing Sheet (D)', 'lookup', f"Formula: {T('DSD_DSnD', 'Mixing Sheet')}. Presence check: #N/A means the item is not on Mix-Slice-Oven (third party)."),
            card('Dough Weights (E)', 'lookup', f"Formula: {T('DSD_DSnD', 'Dough Weights')}. Display."),
            card('Avg of Previous 4 Same Weekdays (G)', 'lookup', f"Despite the name, it holds the description: {T('DSD_DSnD', 'Avg of Previous 4 Same Weekdays')}. Feeds: Dist_DSnD bridge description."),
            card('Demand engine: Sun/Mon to Fri/Sat (H:M)', 'lookup', f"Average packs sold on the same weekday over 4 weeks; 3rd Party and 3rd Party - Bake use the sample week only. Sun/Mon: {T('DSD_DSnD', 'Sun/Mon')}. Columns: H Sun/Mon (sample Mon 9/14) to M Fri/Sat (Sat 9/19)."),
            card('Week 0, Week 1, Week 2 (N:P)', 'unused', 'Week 0 and Week 1 are blank. Week 2 holds typed numbers (for example 280). No formula reads them.'),
        ]),
        ('DSD_DSnD 2/2: per day', [
            card('_Sku, _Desc', 'lookup', f"Repeated per day block ({DAYMAP_DSD}). S_Sku {T('DSD_DSnD', 'S_Sku')}; M_Desc {T('DSD_DSnD', 'M_Desc')}."),
            card('_Freeze', 'input', 'Typed per day. All blank. Floor already includes the freezer count, so typing here double counts.'),
            card('_Floor', 'lookup', f"That day's stock on hand. Sunday: {T('DSD_DSnD', 'S_Floor')}; Monday reads Monday[Total], and so on."),
            card('_Demand', 'calc', f"Sunday: {T('DSD_DSnD', 'S_Demand')}. Mon uses Mon/Tue, Tue uses Tue/Wed, Wed uses Wed/Thur, Fri uses Fri/Sat."),
            card('TH_Demand (Thursday rule)', 'calc', f"{T('DSD_DSnD', 'TH_Demand')}. Lines other than MCS also bake Friday's (Fri/Sat) demand on Thursday."),
            card('_Balance', 'calc', f"{T('DSD_DSnD', 'S_Balanace')} (Sunday column is spelled S_Balanace)."),
            card('_Production', 'calc', f"{T('DSD_DSnD', 'S_Production')}. Negative = packs to bake. Feeds: DoughWeight Sun to Fri, Mix_Slice_Oven K and _Needed, Oven_Info Demand."),
            card('Worked example: F1000 Rye 1/2"', 'note', 'Sun/Mon avg 17.5: S_Demand ROUNDUP(21.0) = 21, Floor 79, Balance 58, nothing to bake. Thursday: ROUNDUP(27.75 x 1.2 + 9.5 x 1.2) = 45. Friday: Floor 0, Demand 12, Production -12, bake 12.'),
        ]),
        ('Dist_DSnD 1/2: cases', [
            card('Row list (A287 spill)', 'lookup', f"Formula: {X('Daily Supply & Demand!A287')}. FG-DIST only."),
            card('Sku (F), Asset (B)', 'lookup', f"Sku {T('Dist_DSnD', 'Sku')}. Asset {T('Dist_DSnD', 'Asset')} (from Mix-Slice-Oven, not Products)."),
            card('TOTAL Cases (G)', 'lookup', f"Holds the description: {T('Dist_DSnD', 'TOTAL Cases')}."),
            card('Demand Sun/Mon to Fri/Sat (H:M)', 'lookup', f"Imported from the external file's own Supply and Demand sheet: {T('Dist_DSnD', 'Sun/Mon')} (column 3 to 8). No buffer, no 4-week average here."),
            card('Week 0, Week 1, Week 2 (N:P)', 'calc', f"{T('Dist_DSnD', 'Week 0')}, then 1_StillNeeded and 2_StillNeeded."),
            card('Per-day block (Q:BF)', 'calc', f"Same layout as DSD ({DAYMAP_DSD}). _Freeze and _Floor are never filled, so _Demand {T('Dist_DSnD', 'S_Demand')}, _Balance = -Demand and _Production = -Demand. Feeds DoughWeight for F5 SKUs."),
        ]),
        ('Dist_DSnD 2/2: orders', [
            card('Order grid 0_ (BG:BU)', 'lookup', f"0_Sun to 0_Sat: {T('Dist_DSnD', '0_Sun')}. The dates are row 284."),
            card('0_TotalOrders, 0_Inventory', 'lookup', f"Total {T('Dist_DSnD', '0_TotalOrders')}. Inventory = today's day-table Total: {T('Dist_DSnD', '0_Inventory')}"),
            card('0_StillNeeded, 0_Today', 'calc', f"{T('Dist_DSnD', '0_StillNeeded')}. Today {T('Dist_DSnD', '0_Today')}. 0_1stShift and 0_2ndShift are blank typed columns."),
            card('Grids 1_ (BV:CJ) and 2_ (CK:CY)', 'calc', f"Meant for the next two weeks, but they still read the 0_ SKU and 0_ totals: 1_Sun {T('Dist_DSnD', '1_Sun')}; 1_TotalOrders {T('Dist_DSnD', '1_TotalOrders')}."),
            card('Pack code and description (CZ:DA)', 'calc', f"CZ {T('Dist_DSnD', 'Correlating DSD Pack Code')}. DA looks the pack up on DSD_DSnD, then Dist_DSnD."),
            card("Today's DSD balance, next 2 days' demand (DC:DE)", 'lookup', f"DC {T('Dist_DSnD', TODAY_BAL)}. DD and DE read _Demand for the next two days (MOD on DT2)."),
            card('Spare packs and cases (C:E)', 'calc', f"Column1 {T('Dist_DSnD', 'Column1')}. Column2 {T('Dist_DSnD', 'Column2')}. Column3 {X('Daily Supply & Demand!E287')}"),
            card('Dist Shipping Schedule', 'output', f"PivotTable on SalesOrders, filtered to DIST: items down, shipment date, customer and order across, Outstanding Quantity summed. Last refreshed 2026-09-18. C2 pallet: {X('Dist Shipping Schedule!C2')}."),
        ]),
        ('Issues', [
            card('Stored table formulas differ from the cells', 'issue', "DSD_DSnD Asset, Gen. Prod., Dough Weights and the six demand columns: the table's stored formula is older (points at Mix-Slice-Oven, the Items List, or drops the 3rd-party branch). Extending or refilling the table brings the old logic back."),
            card('Columns with no stored formula', 'issue', 'DSD_DSnD Avg of Previous 4, S_Sku, S_Desc, T_Sku, T_Desc; Dist_DSnD Column3; Mix_Slice_Oven Unique Dough, Asset, Scrap Factor, Sku, Description, Planned Total, T_Optimal; Oven_Info Daily Bags Per Mix, Finished Product. New rows come in blank.'),
            card('Row 264 typed over (F6502)', 'issue', 'Sku and all six demand averages (H264:M264 = 48) are typed numbers, not formulas.'),
            card('Thursday counts Fri/Sat twice', 'issue', 'For lines other than MCS, TH_Demand includes Fri/Sat and F_Demand includes it again.'),
            card('Order grids are all zero', 'issue', 'Row 284 dates are text (for example 8/31/2026), so SUMIFS never matches a Shipment Date. Distribution order visibility is zero.'),
            card('1_ and 2_ grids copy grid 0_', 'issue', 'They sum SalesOrders for 0_Sku against their own dates, and TotalOrders, Inventory and StillNeeded point at the 0_ columns.'),
            card('Freeze would double count', 'issue', "_Floor is the day table's Total, which already includes the freezer count."),
            card('Dist has no buffer and no stock', 'issue', 'Dist demand skips C5, and Dist _Freeze and _Floor are never filled, so every case in demand is baked again even when cases are on hand.'),
            card('Mislabelled columns', 'issue', "'Avg of Previous 4 Same Weekdays' and 'TOTAL Cases' hold descriptions; Week 2 holds constants; Column1 to Column4 are unnamed; S_Balanace is misspelled."),
            card('Dist Shipping Schedule stale', 'issue', 'Pivot last refreshed 2026-09-18 and row 3 is #REF! (C3 points at a deleted range).'),
        ]),
    ],
})

# ---------------------------------------------------------------- 5 DoughWeights
FRAMES.append({
    'title': '5. DoughWeights',
    'subtitle': 'Turns packs short into pounds of dough per day: only a negative production balance creates dough demand.',
    'mermaid': r"""flowchart LR
{classdef}
    ROWS["A4 row list&lt;br/&gt;each dough, then its products&lt;br/&gt;skips OBS in description and Z codes"]:::calc
    DSDP["DSD_DSnD _Production&lt;br/&gt;pack SKUs"]:::lookup
    DISTP["Dist_DSnD _Production&lt;br/&gt;F5 case SKUs"]:::lookup
    GATE{"Production&lt;br/&gt;below 0?"}:::calc
    W["Products Weight&lt;br/&gt;lb per pack"]:::input
    LB["lb = ABS(Production) x Weight"]:::calc
    ZERO["0 lb"]:::calc
    ROLL["Dough row = SUMIFS of its&lt;br/&gt;product rows by Dough Desc"]:::calc
    DWT["Dough Weight&lt;br/&gt;lb per bag, from BOMQty"]:::lookup
    MSO["Mix_Slice_Oven&lt;br/&gt;bags = lb / Dough Weight x Scrap"]:::calc
    ROWS --> GATE
    DSDP --> GATE
    DISTP --> GATE
    GATE -->|"yes"| LB
    GATE -->|"no"| ZERO
    W --> LB
    LB --> ROLL
    LB --> MSO
    ROLL -->|"display"| MSO
    DWT --> MSO
""",
    'stacks': [
        ('DoughWeight (452 rows)', [
            card('Row list (A4 spill)', 'lookup', f"Formula: {X('DoughWeights!A4')}. 453 rows: each of the 63 doughs followed by its products."),
            card('F2 anchor date', 'lookup', f"{X('DoughWeights!F2')}. Display."),
            card('Sku (B)', 'calc', f"Formula: {T('DoughWeight', 'Sku')} (the row's own A cell)."),
            card('Desciption (C)', 'lookup', f"Formula: {T('DoughWeight', 'Desciption')}."),
            card('Dough Desc (D)', 'lookup', f"Formula: {T('DoughWeight', 'Dough Desc')}. The key dough rows are summed on."),
            card('Weight (E)', 'lookup', f"Formula: {T('DoughWeight', 'Weight')}. lb of dough per pack."),
            card('Sun to Fri (F:K)', 'lookup', f"Pounds of dough needed that day. Sun: {T('DoughWeight', 'Sun')}. F Sun reads S_Production, G Mon M_, H Tue T_, I Wed W_, J Thur TH_, K Fri F_."),
            card('Feeds', 'note', 'Mix_Slice_Oven Dough Weight (L, for the K4 day) and _Bags for every day, each divided by Dough Weight (lb per bag).'),
        ]),
        ('How the numbers read', [
            card('The shortfall gate', 'note', 'Only a negative _Production creates dough. A product with stock left over contributes 0 lb, even if other days are short.'),
            card('Case SKUs', 'note', 'F5 codes read Dist_DSnD _Production, which is always minus demand (no stock is netted for cases).'),
            card('Dough rows', 'note', 'D-code rows add up their products by Dough Desc. Mix_Slice_Oven sums product rows itself, so dough rows are for reading only.'),
            card('Worked example: D10001 Challah', 'note', 'Dough row: Sun 454, Mon 965, Tue 1,176, Wed 402.5, Thu 1,074, Fri 1,220.25 lb. F1127 Challah 3-Braid 21oz, Friday: 36 packs short x 1.3125 lb = 47.25 lb.'),
            card('Column L legacy check', 'unused', "VLOOKUP($C4,'Mix-Slice-Oven'!H:H,1,FALSE) on each row. Broken (444 #N/A, drifting references, #REF!). Nothing reads it."),
            card('BOMQty lives here too', 'export', 'Columns O:AJ hold the pasted BOMQty export. See section 2.'),
        ]),
        ('Issues', [
            card('OBS filter by description', 'issue', 'SEARCH("OBS", Description) drops active Lobster rolls (F3310, F53310). Items in the OBS posting group whose description lacks OBS get through.'),
            card('Array one row longer than the table', 'issue', 'The spill has 453 rows, the table 452, so the last SKU (F2562) has no formulas. Recon shows Array longer.'),
            card('BOM double count flows through here', 'issue', 'Pounds are right, but they are divided by an inflated Dough Weight downstream. See section 1.'),
            card('F6214 #N/A spreads', 'issue', 'F6214 is missing from the external tabs, so its #N/A reaches the D10059 dough row on all six days.'),
        ]),
    ],
})

# ---------------------------------------------------------------- 6 Mix-Slice-Oven
DAYMAP_MSO = 'Sun Z:AD, Mon AE:AI, Tue AJ:AN, Wed AO:AS, Thu AT:AX, Fri AY:BC; minutes BD:BI'
FRAMES.append({
    'title': '6. Mix-Slice-Oven',
    'subtitle': 'Pounds become bags, bags round up to whole mixes, mixes become minutes. K4 picks the day for the printed plan.',
    'mermaid': r"""flowchart LR
{classdef}
    K4["K4 day selector&lt;br/&gt;Tuesday"]:::input
    DW["DoughWeight lb&lt;br/&gt;for the K4 day"]:::lookup
    DWT["Dough Weight&lt;br/&gt;lb per bag"]:::lookup
    L["L Dough Weight&lt;br/&gt;ROUND(lb / lb per bag, 2) x Scrap"]:::calc
    M["M Bags By Unique Dough&lt;br/&gt;run total, first row only"]:::calc
    UD["Unique Dough&lt;br/&gt;Optimal Bag, Optimal Time"]:::input
    N["N Optimal Total&lt;br/&gt;CEILING to bags per mix&lt;br/&gt;Marble x 2.5"]:::calc
    O["O Planned Total = Optimal&lt;br/&gt;type here to override"]:::calc
    TOT["O1 Breadline, O2 MCS&lt;br/&gt;T2 total bags"]:::calc
    SCH["MCS and Breadline&lt;br/&gt;schedules"]:::output
    K["K packs short&lt;br/&gt;DSD or Dist"]:::lookup
    SL["Slice sheet P:W&lt;br/&gt;trays or cases"]:::output
    DAY["Per day: _Bags, _Raw,&lt;br/&gt;_Optimal, _Planned"]:::calc
    MIN["_Minutes =&lt;br/&gt;Planned / bags per mix x time"]:::calc
    HRS["Rows 1-2: bags and hours&lt;br/&gt;per line per day"]:::calc
    DSD["Daily Supply and Demand&lt;br/&gt;W1:W4"]:::lookup
    OD["Oven_Info Demand"]:::lookup
    PANS["Pans&lt;br/&gt;pieces per pan"]:::input
    OP["Pans/Boxes to set out"]:::calc
    F29["MCS F29 pan list"]:::output
    XB["X Extra Bread (Runout)&lt;br/&gt;read by nothing"]:::issue
    K4 --> L
    K4 --> K
    DW --> L
    DWT --> L
    L --> M
    M --> N
    UD --> N
    N --> O
    O --> TOT
    O --> SCH
    K --> SL
    DW --> DAY
    DAY --> MIN
    UD --> MIN
    MIN --> HRS
    HRS --> DSD
    K4 --> OD
    OD --> OP
    PANS --> OP
    OP --> F29
""",
    'stacks': [
        ('Controls and totals', [
            card('K4 day selector', 'input', f"Typed dropdown = {V('Mix-Slice-Oven!K4')}. Feeds: K, L (so M, N, O Planned Total), Oven_Info Demand and pans, and both schedules through Planned Total."),
            card('Q3, R3 header date', 'calc', f"Q3 {X('Mix-Slice-Oven!Q3')}, R3 {X('Mix-Slice-Oven!R3')} = {V('Mix-Slice-Oven!R3')}. Printed only; does not pick the day."),
            card('O1 Breadline bags', 'calc', f"{X('Mix-Slice-Oven!O1')} = {V('Mix-Slice-Oven!O1')}. Feeds: Breadline Schedule H2."),
            card('O2 MCS bags, T2 total', 'calc', f"O2 {X('Mix-Slice-Oven!O2')} = {V('Mix-Slice-Oven!O2')}. T2 {X('Mix-Slice-Oven!T2')} = 234.5. Feeds: MCS Schedule H2."),
            card('Rows 1-2 per day', 'calc', f"Sunday: AD1 {X('Mix-Slice-Oven!AD1')} = {V('Mix-Slice-Oven!AD1')} bags; BD1 {X('Mix-Slice-Oven!BD1')} = 8.5 h; AD2, BD2 the same for MCS LINE ({V('Mix-Slice-Oven!AD2')} bags, 16.08 h). Feed Daily Supply and Demand W1:W4."),
            card('Y1 pan count', 'calc', f"{X('Mix-Slice-Oven!Y1')} = {V('Mix-Slice-Oven!Y1')}."),
            card('Row list (A6 spill)', 'lookup', f"In-house lines only (Asset Rank 1 to 3), not OBS, sorted by rank, dough, unique dough, SKU, with a dough header row above each block. {X('Mix-Slice-Oven!A6')}"),
        ]),
        ('Mix_Slice_Oven: setup', [
            card('Sku (H)', 'calc', f"{T('Mix_Slice_Oven', 'Sku')}. D-codes are dough header rows."),
            card('Dough (B)', 'lookup', f"{T('Mix_Slice_Oven', 'Dough')}."),
            card('Unique Dough (C)', 'lookup', f"{T('Mix_Slice_Oven', 'Unique Dough')}. Groups rows into mixing runs."),
            card('Asset (D)', 'lookup', f"{T('Mix_Slice_Oven', 'Asset')}. Line totals and schedule filters."),
            card('Weight (E)', 'lookup', f"{T('Mix_Slice_Oven', 'Weight')}. Filled on dough header rows (lb per bag)."),
            card('optimal bags per mix (F)', 'lookup', f"{T('Mix_Slice_Oven', 'optimal bags per mix')}."),
            card('Scrap Factor (G)', 'lookup', f"{T('Mix_Slice_Oven', 'Scrap Factor')}."),
            card('Description (I)', 'lookup', f"{T('Mix_Slice_Oven', 'Description')}."),
            card('Units per case/Tray (J)', 'lookup', f"{T('Mix_Slice_Oven', 'Units per case/Tray')}."),
            card('Run Time Per Mix (min) (Y)', 'lookup', f"{T('Mix_Slice_Oven', 'Run Time Per Mix (min)')}."),
        ]),
        ('Mix_Slice_Oven: K4 day', [
            card('K Individual Packaged Units Needed', 'lookup', f"Packs (or cases) short on the K4 day, as a positive number. {T('Mix_Slice_Oven', 'Number of  Individual Packaged Units Needed')}"),
            card('L Dough Weight (bags)', 'lookup', f"Bags for this SKU: {T('Mix_Slice_Oven', 'Dough Weight')}"),
            card('M Bags By Unique Dough', 'calc', f"Run total on the first row of each run, blank on the rest: {T('Mix_Slice_Oven', 'Bags By Unique Dough')}"),
            card('N Optimal Total', 'calc', f"Rounds up to whole mixes; Marble x 2.5; dough rows sum their products: {T('Mix_Slice_Oven', 'Optimal Total')}"),
            card('O Planned Total', 'calc', f"{T('Mix_Slice_Oven', 'Planned Total')}. The one place to override the plan by typing. None are overridden today. Feeds: O1, O2, both schedules."),
            card('Slice sheet (P:V)', 'calc', f"P {T('Mix_Slice_Oven', 'Dough Desc')}, Q = Planned Total, R = Sku, S = Description, T = K. U {T('Mix_Slice_Oven', '#of Trays/Cases Needed')}. V Tray or Case."),
            card('W Notes', 'calc', f"Flags Case Total when a case is needed but its pack is not: {T('Mix_Slice_Oven', 'Notes')}"),
            card('X Extra Bread (Runout)', 'issue', 'Typed column meant for runouts. No formula reads it.'),
            card('Worked example: Challah 3 Braided', 'note', 'Tuesday (K4): run total M = 1.298 bags, bags per mix 1, Optimal CEILING = 2, Planned 2, T_Minutes 2 / 1 x 30 = 60.'),
        ]),
        ('Mix_Slice_Oven: by day', [
            card('_Needed', 'lookup', f"{DAYMAP_MSO}. Sunday: {T('Mix_Slice_Oven', 'S_Needed')}. Reads DSD_DSnD only."),
            card('_Bags', 'lookup', f"Sunday: {T('Mix_Slice_Oven', 'S_Bags')}. Rounds after scrap; L rounds before."),
            card('_Raw', 'calc', f"Run total per day: {T('Mix_Slice_Oven', 'S_Raw')}"),
            card('_Optimal', 'calc', f"{T('Mix_Slice_Oven', 'S_Optimal')}. T_Optimal holds the same formula in every cell."),
            card('_Planned', 'calc', f"{T('Mix_Slice_Oven', 'S_Planned')}. Feeds: rows 1-2 totals."),
            card('_Minutes', 'calc', f"Sunday: {T('Mix_Slice_Oven', 'S_Minutes')}. Rows 1-2 divide by 60 for hours."),
            card('Worked example: F1127, Friday', 'note', 'F_Needed 36 packs. F_Bags ROUND(47.25 / 177.27 x 1.1, 2) = 0.29. F_Raw 0.29, F_Optimal CEILING(0.29, 1) = 1, F_Minutes 1 / 1 x 30 = 30.'),
        ]),
        ('Oven_Info (86 rows)', [
            card('Row list (A410 spill)', 'lookup', f"One block per pan: the pan name, then every non-OBS product whose Pans/Boxes is that pan. {X('Mix-Slice-Oven!A410')}"),
            card('Finished Product (E)', 'calc', f"{T('Oven_Info', 'Finished Product')}."),
            card('Pans (B)', 'lookup', f"{T('Oven_Info', 'Pans')}"),
            card('Unique Dough (C), Daily Bags Per Mix (D)', 'lookup', f"C {T('Oven_Info', 'Unique Dough')}. D {T('Oven_Info', 'Daily Bags Per Mix')}."),
            card('Finished Product Description (F)', 'lookup', f"{T('Oven_Info', 'Finished Product Description')}."),
            card('Trays per 1 Bag Mix (G)', 'lookup', f"{T('Oven_Info', 'Trays per 1 Bag Mix')}. Filled on pan rows."),
            card('Demand (H)', 'lookup', 'Packs short on the K4 day: the same formula as Mix_Slice_Oven K.'),
            card('Sku (I), Today\'s Date (N)', 'calc', f"Mislabelled copies: Sku {T('Oven_Info', 'Sku')}, Today's Date {T('Oven_Info', TODAYS_DATE)}. Both just repeat Finished Product."),
            card('#N/A (J)', 'unused', 'A column literally named #N/A holding a copy of Demand. Nothing reads it.'),
            card('# of pieces per tray/box (K)', 'lookup', f"{T('Oven_Info', '# of pieces per tray/box')}."),
            card('Pieces Per Pan (L)', 'lookup', f"{T('Oven_Info', 'Pieces Per Pan')}. Filled on pan rows."),
            card('Pans / Boxes (O)', 'calc', f"{T('Oven_Info', 'Pans / Boxes')}."),
            card('# of Pans/Boxes to set out (P)', 'calc', f"On pan rows: pieces needed by every product on that pan, divided by pieces per pan, rounded up. {T('Oven_Info', '# of Pans/Boxes to set out')} Feeds: MCS Schedule F29."),
            card('Column4 (M), Notes/ Comments (Q)', 'unused', 'Blank. Nothing reads them.'),
            card('CA500 pan listing', 'calc', f"Text list of each pan and its products: {X('Mix-Slice-Oven!CA500')}"),
        ]),
        ('Issues', [
            card('K4 says Tuesday, sheets say Friday', 'issue', 'Planned Total, the slice sheet, Oven_Info and both schedules show Tuesday quantities under a Friday date. Nothing ties K4 to TODAY().'),
            card('Extra Bread (Runout) wired to nothing', 'issue', 'Typing a runout in X changes no bag, minute or schedule.'),
            card('_Needed ignores cases', 'issue', 'Per-day _Needed reads DSD_DSnD only, so case rows show 0 packs needed even though their _Bags are counted.'),
            card('Two rounding orders', 'issue', 'L rounds bags before scrap; the _Bags columns round after scrap, so the K4 column and the same day block can differ by 0.01 bag per SKU.'),
            card('Runs with no mix time', 'issue', 'Runs with a blank Optimal Time (5 artisan doughs among them) get 0 minutes, so line hours are understated.'),
            card('3 LB. Braided Optimal Bag = dne', 'issue', 'Text in a number column: CEILING fails and the run gets no Optimal Total.'),
            card('BK1 hardcoded', 'issue', f"BK1 {X('Mix-Slice-Oven!BK1')}: a typed minutes figure, not a formula."),
            card('Numbers stored as text', 'issue', 'K, _Needed and Demand return the text "0" when nothing is short, which SUM ignores and lookups treat as text.'),
            card('Print area cuts off Oven_Info', 'issue', 'Rows 453 to 477 fall outside the print area.'),
            card('Tables longer than the row list', 'issue', 'Mix_Slice_Oven +1 row, Oven_Info +18 rows (see Recon).'),
        ]),
    ],
})

# ---------------------------------------------------------------- 7 Schedules
FRAMES.append({
    'title': '7. MCS and Breadline schedules',
    'subtitle': 'Each run sheet is one dynamic-array formula in A5 that turns Planned Total into one printed row per mix.',
    'mermaid': r"""flowchart TD
{classdef}
    MSO["Mix_Slice_Oven&lt;br/&gt;Planned Total, Asset, Unique Dough"]:::lookup
    UD["Unique Dough&lt;br/&gt;Placement, Optimal Bag, Optimal Time"]:::input
    S1["1 Keep runs with Planned above 0&lt;br/&gt;on this line"]:::calc
    MB["Breadline only: Marble becomes&lt;br/&gt;Pump 1 bag + Rye 1.5 bag sets"]:::calc
    S2["2 Sort by Placement On Scedule"]:::calc
    S3["3 Mixes per run =&lt;br/&gt;ROUNDUP(bags / bags per mix)"]:::calc
    S4["4 SCAN running count&lt;br/&gt;one row per mix"]:::calc
    CO["MCS only: add Changeover rows&lt;br/&gt;at placement above + 0.5"]:::calc
    IL["Breadline only: interleave&lt;br/&gt;Pump, Rye, Pump, Rye"]:::calc
    MCS["MCS Schedule A5:D&lt;br/&gt;47 mixes + 2 changeovers"]:::output
    BL["Breadline Schedule A5:D&lt;br/&gt;25 mixes"]:::output
    CLI["Critical Lookup Information&lt;br/&gt;D:O notes, attributes, run times"]:::input
    ATT["N:S attributes and notes"]:::lookup
    BC["F5 / G5 Bag Count&lt;br/&gt;bags mixed vs raw DSD vs raw DIST"]:::calc
    OV["Oven_Info pans to set out"]:::lookup
    F29["MCS F29 pan list"]:::output
    E4["E4 typed start time"]:::input
    MSO --> S1
    S1 --> MB
    MB --> S2
    S1 --> S2
    UD --> S2
    S2 --> S3
    UD --> S3
    S3 --> S4
    S4 --> CO
    CO --> MCS
    S4 --> IL
    IL --> BL
    CLI --> ATT
    ATT --> MCS
    ATT --> BL
    MCS --> BC
    BL --> BC
    OV --> F29
    E4 -.->|"printed only"| MCS
""",
    'stacks': [
        ('MCS Schedule', [
            card('A2 date, H2 bags', 'lookup', f"A2 {X('MCS Schedule!A2')}. H2 {X('MCS Schedule!H2')} = {V('MCS Schedule!H2')} bags."),
            card('E4 start time', 'input', 'Typed 6:45. Printed only; no finish times follow from it.'),
            card('A5 spill: run rows', 'lookup', f"Filters MCS LINE runs with Planned above 0, sorts by placement, expands one row per mix, then adds Changeover rows. Outputs run, bags, bags per mix, minutes. {X('MCS Schedule!A5')}"),
            card('Step: mixes per run', 'calc', 'k = ROUNDUP(run bags / Optimal Bag), or 1 if the run has no Optimal Bag. SCAN builds the running count so each mix gets its own row.'),
            card('Step: Changeover rows', 'calc', 'Every Unique Dough row named Changeover is placed at the placement of the row above it + 0.5, and kept only if it falls between today\'s first and last run.'),
            card('F5 Bag Count', 'calc', f"Per run: bags mixed, raw DSD bags, raw DIST bags. {X('MCS Schedule!F5')}"),
            card('F29 pan list', 'lookup', f"{X('MCS Schedule!F29')}"),
            card('N:S attributes', 'lookup', f"From Critical Lookup Information, not Unique Dough. N5 {X('MCS Schedule!N5')}."),
            card('D4 legacy run time', 'lookup', f"{X('MCS Schedule!D4')} Returns #N/A today."),
            card('As saved', 'note', '47 mixes + 2 changeovers, 180 bags, 17.25 h.'),
        ]),
        ('Breadline Schedule', [
            card('A2 date, H2 bags', 'lookup', f"A2 {X('Breadline Schedule!A2')}. H2 {X('Breadline Schedule!H2')} = {V('Breadline Schedule!H2')} bags."),
            card('E4 start time', 'input', 'Typed 7:50. Printed only.'),
            card('A5 spill: run rows', 'lookup', f"Breadline and Breadline/Artisan runs with Planned above 0. {X('Breadline Schedule!A5')}"),
            card('Step: Marble split', 'calc', 'A Marble run becomes sets of Pump for Marble (1 bag) and Rye for Marble (1.5 bags): sets = ROUNDUP(Marble bags / 2.5). Rows are interleaved Pump, Rye, Pump, Rye.'),
            card('G5 Bag Count', 'calc', f"Same as MCS F5, one column to the right. {X('Breadline Schedule!G5')}"),
            card('N:R attributes', 'lookup', f"From Critical Lookup Information. N5 {X('Breadline Schedule!N5')}."),
            card('As saved', 'note', '25 mixes, 54.5 bags, 9.92 h.'),
        ]),
        ('Differences', [
            card('MCS vs Breadline', 'note', 'Filter: MCS LINE vs Breadline + Breadline/Artisan. MCS inserts Changeover rows; Breadline splits Marble. MCS lists pans to set out (F29); Breadline does not. Bag Count sits in F5 vs G5.'),
        ]),
        ('Issues', [
            card('No start or finish times', 'issue', 'E4 is a typed start. Nothing adds run minutes to it, so every later time is written by hand.'),
            card('Bag Count spills over the form', 'issue', 'The F5/G5 summary lands on the Time Start, Time Finish, Temp and Operator columns.'),
            card('MCS N:S lookups broken', 'issue', 'Gaps, an off-by-one on row 7 and #REF! on row 10: 711 #N/A in total.'),
            card('Print areas are #REF!', 'issue', 'Both sheets\' Print_Area names point at deleted ranges.'),
            card('Placement ties', 'issue', 'Runs share placements 48, 50 and 53, so their order on the sheet is arbitrary.'),
            card('Attributes come from the second copy', 'issue', 'N:S and D4 read Critical Lookup Information, so Unique Dough edits never print.'),
        ]),
    ],
})

# ---------------------------------------------------------------- 8 Recon
# Recon!A4:G15 is the Excel table "Recon". Its row-5 formulas are read from the workbook and
# re-written with the table's structured references (C5 -> [@[Array Rows]], E5 -> [@[Table Rows]]).
RECON_COLS = ['Sheet', 'Array Cell', 'Array Rows', 'Adjacent Table', 'Table Rows',
              'Difference (Array − Table)', 'Status']


def recon_ref(formula):
    out = re.sub(r'\bC5\b', '[@[Array Rows]]', formula)
    return re.sub(r'\bE5\b', '[@[Table Rows]]', out)


RECON_F = {
    'Array Cell': recon_ref(X('Recon!B5')),
    'Array Rows': X('Recon!C5'),
    'Table Rows': X('Recon!E5'),
    'Difference (Array − Table)': recon_ref(X('Recon!F5')),
    'Status': recon_ref(X('Recon!G5')),
}
assert RECON_F['Difference (Array − Table)'] == '=[@[Array Rows]]-[@[Table Rows]]'
assert RECON_F['Status'] == '=IF([@[Array Rows]]=[@[Table Rows]],"Match",IF([@[Table Rows]]>[@[Array Rows]],"Table longer","Array longer"))'
assert RECON_F['Array Cell'] == '=SUBSTITUTE(MID(FORMULATEXT([@[Array Rows]]),FIND("!",FORMULATEXT([@[Array Rows]]))+1,99),")","")'
assert [V(f'Recon!{c}4') for c in 'ABCDEFG'] == RECON_COLS

recon_rows = []
for r in range(5, 16):
    sheet, arr, rows, table, trows, diff, status = (V(f'Recon!{c}{r}') for c in 'ABCDEFG')
    kind = 'issue' if status == 'Array longer' else 'calc'
    note = {'Match': 'every SKU has a row.',
            'Table longer': 'extra table rows below the spill show #N/A; harmless.',
            'Array longer': 'SKUs at the end of the spill have no table row and are silently dropped.'}[status]
    recon_rows.append(card(f'{table}: {status}', kind,
                           f'Sheet {sheet}, Array Cell {arr}: Array Rows {rows}, Table Rows {trows}, Difference {diff}. {status}: {note}'))
FRAMES.append({
    'title': '8. Recon',
    'subtitle': 'The Recon table: one row per spilled row list, compared with the table built beside it.',
    'mermaid': r"""flowchart LR
{classdef}
    SP["Sheet, Array Cell&lt;br/&gt;spilled row lists A3, A8, A287, A4, A6, A410"]:::lookup
    TB["Adjacent Table&lt;br/&gt;Sunday to Friday, DSD_DSnD, Dist_DSnD,&lt;br/&gt;DoughWeight, Mix_Slice_Oven, Oven_Info"]:::lookup
    C["Array Rows =&lt;br/&gt;ROWS(ANCHORARRAY(spill))"]:::calc
    E["Table Rows =&lt;br/&gt;ROWS(Table[])"]:::calc
    F["Difference =&lt;br/&gt;Array Rows - Table Rows"]:::calc
    G{"Status"}:::calc
    OK["Match"]:::calc
    TL["Table longer&lt;br/&gt;blank rows, harmless"]:::calc
    AL["Array longer&lt;br/&gt;SKUs silently dropped"]:::issue
    SP --> C
    TB --> E
    C --> F
    E --> F
    F --> G
    G -->|"0"| OK
    G -->|"Table Rows bigger"| TL
    G -->|"Array Rows bigger"| AL
""",
    'stacks': [
        ('Recon table columns', [
            card('Sheet', 'input', 'Typed label: the sheet that holds the spilled row list (Sunday to Friday, Daily Supply & Demand, DoughWeights, Mix-Slice-Oven).'),
            card('Array Cell', 'calc', f"Reads the spill address out of the Array Rows formula: {RECON_F['Array Cell']}"),
            card('Array Rows', 'lookup', f"{RECON_F['Array Rows']} on the Sunday row; each row points at its own sheet's spill, so Excel flags the column as inconsistent. That is expected."),
            card('Adjacent Table', 'input', 'Typed label: the Excel table built beside that row list (Sunday to Friday, DSD_DSnD, Dist_DSnD, DoughWeight, Mix_Slice_Oven, Oven_Info).'),
            card('Table Rows', 'lookup', f"{RECON_F['Table Rows']} on the Sunday row; each row names its own table, so this column is not a calculated column either."),
            card('Difference (Array − Table)', 'calc', f"{RECON_F['Difference (Array − Table)']}. Positive means SKUs are missing from the table."),
            card('Status', 'calc', f"{RECON_F['Status']}"),
            card('What Recon does not check', 'note', 'It only counts rows. It would not catch the BOM double count, K4 not matching today, the stale Sunday!B1 date, the dead order grids or #N/A values inside matching tables.'),
        ]),
        ('Checks as saved', recon_rows),
    ],
})

# ---------------------------------------------------------------- 9 Known issues
FRAMES.append({
    'title': '9. Known issues, ranked',
    'subtitle': 'Ranked by effect on what gets baked, with a suggested fix.',
    'mermaid': None,
    'stacks': [
        ('Wrong quantities', [
            card('1. Dough Weight double counts BOMs', 'issue', 'Up to about 22% too few bags on 11 doughs. Fix: SUMIFS only the level-1 lines (FormatLevel = 1), or sum raw materials only. Section 1.'),
            card('2. K4 is Tuesday, sheets print Friday', 'issue', 'Schedules show the wrong day. Fix: default K4 to TEXT(TODAY(),"dddd") with a manual override cell. Section 6.'),
            card('3. Lobster rolls get no dough', 'issue', 'SEARCH("OBS") matches Lobster. Fix: filter on Gen. Prod. Posting Group <> OBS instead of the description. Sections 1 and 5.'),
            card('4. Extra Bread (Runout) does nothing', 'issue', 'Fix: add X to K (or to the K4-day pounds) before bags are calculated. Section 6.'),
            card('5. Thursday counts Fri/Sat twice', 'issue', 'Non-MCS lines. Fix: drop Fri/Sat from F_Demand for those lines, or from TH_Demand. Section 4.'),
        ]),
        ('Wrong or missing data', [
            card('6. Sunday!B1 three weeks behind', 'issue', 'Julian dates wrong. Fix: Sunday!B1 = \'Daily Supply & Demand\'!H2. Section 3.'),
            card('7. Order grids dead', 'issue', 'Text dates in row 284, and grids 1_ and 2_ copy grid 0_. Fix: real dates from H2, and point each grid at its own columns. Section 4.'),
            card('8. BOMQty six months old', 'issue', 'As of 03/24/26. Fix: re-export Quantity Explosion of BOM. Section 2.'),
            card('9. Two copies of the run list', 'issue', 'Schedules read Critical Lookup Information, not Unique Dough. Fix: point the N:S and D4 lookups at UniqueDough and retire D:O. Sections 1 and 7.'),
            card('10. Everything hangs on _BC.xlsm', 'issue', 'All inventory and Dist demand come from one linked SharePoint file. Fix: keep the link path fixed and tab names consistent, or bring the count into this workbook. Section 3.'),
        ]),
        ('Maintenance traps', [
            card('11. Stored table formulas are older', 'issue', 'Refilling DSD_DSnD columns brings back old logic; 15 columns have no stored formula. Fix: re-enter each column formula across the whole column. Section 4.'),
            card('12. Typed values over formulas', 'issue', 'Dough D10004, D10061; DSD row 264; Mix-Slice-Oven BK1. Fix: restore the formulas. Sections 1, 4, 6.'),
            card('13. No start or finish times', 'issue', 'Fix: a running sum of minutes from E4 in the schedule spill. Section 7.'),
            card('14. Blank or text run data', 'issue', '7 blank Optimal Times, 3 LB. Braided = dne, 5 unknown run names, stray spaces. Fix: clean Unique Dough and Products. Section 1.'),
            card('15. Row lists and tables out of step', 'issue', 'DoughWeight drops F2562; other tables carry #N/A rows. Fix: resize each table to its spill. Section 8.'),
        ]),
    ],
})


# ---------------------------------------------------------------- layout + SVG
def split_stacks(stacks):
    out = []
    for heading, cards in stacks:
        chunks = [cards[i:i + MAXC] for i in range(0, len(cards), MAXC)]
        for i, ch in enumerate(chunks):
            out.append((heading if len(chunks) == 1 else f'{heading} ({i + 1}/{len(chunks)})', ch))
    return out


def build():
    fx, fy = FRAME_X0, FRAME_Y0
    manifest = []
    for n, fr in enumerate(FRAMES):
        cols = split_stacks(fr['stacks'])
        x0 = PAD + DIA_W + PAD if fr['mermaid'] else PAD
        W = x0 + len(cols) * COLW - (COLW - CARD_W) + PAD
        maxc = max(len(c) for _, c in cols)
        H = max(TOP + DIA_H if fr['mermaid'] else 0, 288 + maxc * PITCH - (PITCH - CARD_H)) + PAD
        assert len(fr['subtitle']) * 13 < W - 2 * PAD, (n, 'subtitle too long for frame')
        assert all(len(h) <= 23 for h, _ in cols), (n, 'stack heading wider than a column')
        parts = [f'<g id="f{n}" transform="translate({fx},{fy})" data-frame="{esc(fr["title"])}">',
                 f'  <rect data-type="frame" x="0" y="0" width="{W}" height="{H}" fill="#ffffff" data-title="{esc(fr["title"])}"/>',
                 # fixed-width text boxes: auto-sized <text> was measured a little narrow and wrapped
                 f'  <textArea id="t{n}" x="{PAD}" y="53" width="{W - 2 * PAD}" font-size="67" font-weight="bold" font-family="noto_sans" fill="#1a1a1a">{esc_body(fr["title"])}</textArea>',
                 f'  <textArea id="s{n}" x="{PAD}" y="162" width="{W - 2 * PAD}" font-size="22" font-family="noto_sans" fill="#595959">{esc_body(fr["subtitle"])}</textArea>']
        ncards = 0
        for i, (heading, cards) in enumerate(cols):
            cx = x0 + i * COLW
            parts.append(f'  <textArea id="h{n}_{i}" x="{cx}" y="240" width="{CARD_W}" font-size="22" font-weight="bold" font-family="noto_sans" fill="#1a1a1a">{esc_body(heading)}</textArea>')
            for j, c in enumerate(cards):
                desc = f"{LABEL[c['kind']]}. {c['text']}"
                parts.append(
                    f'  <rect id="c{n}_{i}_{j}" data-type="custom-widget" data-widget-type="card" '
                    f'data-title="{esc(c["title"])}" data-description="{esc(desc)}" data-color="{COLOR[c["kind"]]}" '
                    f'x="{cx}" y="{288 + j * PITCH}" width="{CARD_W}" height="{CARD_H}" fill="none" stroke="none"/>')
                ncards += 1
        if fr['mermaid']:
            body = fr['mermaid'].replace('{classdef}', CLASSDEF)
            assert '<' not in body and '&' not in body.replace('&lt;', '').replace('&gt;', '')
            body = body.replace('>', '&gt;')  # arrows: the body must carry no raw '>'
            # nested in the frame so it moves with it; x/y is the diagram's top-left
            parts.append(f'  <foreignObject id="d{n}" x="{PAD}" y="{TOP}" width="{DIA_W}" height="{DIA_H}" '
                         f'data-type="diagram" data-title="{esc(fr["title"])}">\n{body}</foreignObject>')
        parts.append('</g>')
        svg = '<svg xmlns="http://www.w3.org/2000/svg">\n' + '\n'.join(parts) + '\n</svg>\n'
        ET.fromstring(svg)  # must parse
        path = os.path.join(HERE, f'frame{n}.svg')
        open(path, 'w').write(svg)
        manifest.append({'frame': n, 'title': fr['title'], 'x': fx, 'y': fy, 'w': W, 'h': H,
                         'cards': ncards, 'columns': len(cols), 'diagram': bool(fr['mermaid']),
                         'bytes': len(svg.encode())})
        fx += W + GUTTER
    json.dump(manifest, open(os.path.join(HERE, 'manifest.json'), 'w'), indent=1)
    for m in manifest:
        print(m)
    print('total cards', sum(m['cards'] for m in manifest))


if __name__ == '__main__':
    build()
