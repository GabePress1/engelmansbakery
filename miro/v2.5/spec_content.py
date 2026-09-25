"""Content of the Logic Spec row: one spec per main-row section (0-8).

Formulas are pulled from formulas.json through build.py's helpers (T for a table column,
X for a control cell), so no formula is retyped. `part(ref, text)` quotes a decisive
fragment of a long formula and fails if the fragment is not in that formula verbatim.
Worked-example numbers are the workbook's cached values (see README for how they were read).
Writes specs.json for spec.py.
"""
import json
import os

from build import RECON_F, T, X

HERE = os.path.dirname(os.path.abspath(__file__))


def part(formula, fragment):
    assert fragment in formula, f'not verbatim: {fragment}'
    return fragment


SPECS = []

# ------------------------------------------------------------------ 0
SPECS.append({
    'section': 0,
    'title': '0. A planning week: Logic Spec',
    'subtitle': 'The weekly routine, from pasting the exports to the printed run sheets.',
    'mermaid': '''flowchart TD
s(["Start of the planning week"]):::terminator
p1[/"Paste Sales History<br/>posted invoice lines"/]:::export
p2[/"Set Daily Supply and Demand H2<br/>to the planning Sunday"/]:::input
p3[/"Paste Open Sales Lines<br/>refresh the Dist Shipping pivot"/]:::export
c1[/"Floor counts typed in the<br/>_BC.xlsm day tabs"/]:::input
d1["Sunday to Friday tables:<br/>Total and Final Inventory"]:::lookup
d2["Supply and Demand:<br/>stock minus demand = Production"]:::calc
d3["DoughWeights:<br/>packs short x lb per pack"]:::calc
k4{{"Is K4 the day<br/>being baked?"}}:::decision
fix[/"Set Mix-Slice-Oven K4"/]:::input
d4["Mix-Slice-Oven:<br/>bags, planned bags, minutes"]:::calc
r1{{"Recon shows<br/>Array longer?"}}:::decision
iss["SKUs dropped from a table:<br/>resize it before printing"]:::issue
o1["MCS and Breadline schedules<br/>printed run sheets"]:::output
e(["Bake"]):::terminator
s --> p1
p1 --> p2
p2 --> p3
p3 --> c1
c1 --> d1
d1 --> d2
d2 --> d3
d3 --> k4
k4 -->|"No"| fix
fix --> d4
k4 -->|"Yes"| d4
d4 --> r1
r1 -->|"Yes"| iss
iss -.-> o1
r1 -->|"No"| o1
o1 --> e''',
    'inputs': [
        '**Sales History** (table SalesHistory): pasted Business Central posted invoice lines. The average needs the sample week and the three weeks before it.',
        "**H2 anchor date** ('Daily Supply & Demand'!H2): the planning Sunday, typed. This week 2026-09-20.",
        '**Open Sales Lines** (table SalesOrders): pasted open order lines, then refresh the Dist Shipping Schedule pivot.',
        '**Floor counts**: typed in the external _BC.xlsm day tabs (Sunday - Inventory to Friday-Inventory) and read by XLOOKUP.',
        '**K4 day selector** (Mix-Slice-Oven!K4): the day being planned, typed. This week it says Tuesday.',
        '**BOMQty** (DoughWeights O:AJ): pasted Quantity Explosion of BOM when recipes change. The header says As of 03/24/26.',
        '**E4 start times** on each schedule: typed first-mix start (MCS 6:45, Breadline 7:50).',
    ],
    'formulas': [
        f"**Sample dates (H3)** one week before the anchor Monday: {X('Daily Supply & Demand!H3')}. I3:M3 continue to Saturday.",
        f"**Daily demand (S_Demand)** {T('DSD_DSnD', 'S_Demand')}. The average in H:M is described in section 4.",
        f"**Balance and production** {T('DSD_DSnD', 'S_Balanace')}, then S_Production {T('DSD_DSnD', 'S_Production')}. Negative means bake.",
        f"**Breadline bags (O1)** {X('Mix-Slice-Oven!O1')}",
        f"**MCS bags (O2)** {X('Mix-Slice-Oven!O2')}. The MCS Schedule shows it in H2: {X('MCS Schedule!H2')}.",
        f"**Recon[Status]** {RECON_F['Status']}",
    ],
    'example': [
        '**Anchor** H2 = 2026-09-20. Sample dates run 9/14 to 9/19; the Sun/Mon average also reads 9/7, 8/31 and 8/24.',
        '**Today** 2026-09-25 is a Friday, so DT2 = 6 and every sheet header prints Friday.',
        "**K4** = Tuesday, so Planned Total, the slice sheet and both schedules show Tuesday's quantities.",
        '**Line totals** O1 Breadline 54.5 bags, O2 MCS LINE 180 bags, T2 234.5.',
        '**Run sheets as saved** MCS 47 mixes + 2 changeovers; Breadline 25 mixes.',
        '**Recon** DoughWeight shows Array longer (453 against 452), so F2562 has no DoughWeight row.',
    ],
    'questions': [
        "Should K4 default to today's day (TEXT(TODAY(),\"dddd\")) with a separate override cell, or is planning a different day the normal use?",
        'Who pastes each export, on which day, and should the workbook record the paste date next to each one?',
        'Should Sunday!B1 be tied to H2 so all dates in the week move together?',
        'Should the floor count keep being typed in the external _BC.xlsm, or move into this workbook?',
    ],
})

# ------------------------------------------------------------------ 1
OBS_TEST = part(X('DoughWeights!A4'), 'ISNUMBER(SEARCH("OBS",Products[Description]))=FALSE')
MSO_KEEP = part(X('Mix-Slice-Oven!A6'), 'k,(rk<=3)*(d<>"")*(gp<>"OBS")')
SPECS.append({
    'section': 1,
    'title': '1. Master data: Logic Spec',
    'subtitle': 'How one Products row decides which lists, lines, doughs and pans it reaches downstream.',
    'mermaid': '''flowchart TD
s(["One product row in Products"]):::terminator
g{{"Gen. Prod. Posting Group?"}}:::decision
obs["OBS: left out of the row lists"]:::output
fg[/"FG: day tables and DSD_DSnD"/]:::input
dist[/"FG-DIST: day tables and Dist_DSnD"/]:::input
oc{{"Description contains OBS?"}}:::decision
lob["Skipped by DoughWeights:<br/>Lobster rolls get no dough"]:::issue
dw["DoughWeights row under its<br/>Dough code, lb = packs x Weight"]:::calc
wt["Dough Weight = SUMIFS of BOMQty<br/>for the D-code, lb per bag"]:::lookup
r{{"Asset Rank at most 3?"}}:::decision
tp["Third party: no Mix-Slice-Oven row,<br/>so no bags or minutes"]:::output
ud{{"Unique Dough name found<br/>in the Unique Dough table?"}}:::decision
blank["Blank bags per mix and minutes"]:::issue
mix["Mix-Slice-Oven row: Optimal Bag,<br/>Optimal Time, Placement"]:::lookup
pan[/"Pans/Boxes: Oven_Info pan block"/]:::lookup
e(["Row feeds Supply and Demand,<br/>DoughWeights and Mix-Slice-Oven"]):::terminator
s --> g
g -->|"OBS"| obs
g -->|"FG"| fg
g -->|"FG-DIST"| dist
fg --> oc
dist --> oc
oc -->|"Yes"| lob
oc -->|"No"| dw
dw --> wt
lob -.-> r
wt --> r
r -->|"No"| tp
r -->|"Yes"| ud
ud -->|"No"| blank
ud -->|"Yes"| mix
mix --> pan
pan --> e''',
    'inputs': [
        '**No.** (Products A): item number. F5 at the start marks the case version of a pack (F51000 is the case of F1000).',
        '**Gen. Prod. Posting Group** (F): FG 277 items, FG-DIST 122, OBS 79.',
        '**Asset** (G): the production line, turned into Asset Rank.',
        '**Weight** (H): lb of dough in one pack.',
        '**Dough** (L) and **Unique Dough** (I): the dough code and the mixing run.',
        '**Scrap Factor** (N), **Packs Per Tray/Case** (J), **Pans/Boxes** (Q).',
        '**BOMQty export** (DoughWeights O:AJ): component lb for each dough, pasted from Business Central.',
        '**Unique Dough table**: Placement On Scedule, Optimal Bag and Optimal Time for each run.',
    ],
    'formulas': [
        f"**Asset Rank (P)** 1 Breadline, 2 Breadline/Artisan, 3 MCS LINE, 4 to 6 third party, 99 anything else: {T('Products', 'Asset Rank')}",
        f"**Dough Description (M)** {T('Products', 'Dough Description')}",
        f"**Non Case Sku (R)** {T('Products', 'Non Case Sku')}",
        f"**Dough Weight (Dough I)** {T('Dough', 'Weight')}",
        f"**Obsolete test in DoughWeights A4** {OBS_TEST}",
        f"**Mix-Slice-Oven A6 keeps** {MSO_KEEP}",
    ],
    'example': [
        '**F1127 Challah 3-Braid 21oz**: posting group FG, Asset Breadline, so Asset Rank 1.',
        '**Dough** D10001 Challah Dough. Dough Weight = 177.27 lb per bag, summed from BOMQty.',
        '**Unique Dough** Challah 3 Braided: Placement 49, Optimal Bag 1, Optimal Time 30 minutes.',
        '**Pack data** Weight 1.3125 lb per pack, Scrap Factor 1.1, Packs Per Tray/Case 6.',
        '**Case twin** F51127: Non Case Sku = F1127. On Tuesday its 20 cases short give the run its 1.298 bags.',
    ],
    'questions': [
        'Should the obsolete filter use Gen. Prod. Posting Group instead of looking for OBS in the description?',
        'Should Dough Weight count only level-1 BOM lines, and who confirms the real batch weight of the 11 affected doughs?',
        'Should the schedules read notes and attributes from Unique Dough, so Critical Lookup Information D:O can be retired?',
        'What should happen to products whose Unique Dough is not in the table (Gourmet Hawaiian Bun, 8 and 6 inch Philly Roll, Bread Stick)?',
    ],
})

# ------------------------------------------------------------------ 2
SPECS.append({
    'section': 2,
    'title': '2. Business Central exports: Logic Spec',
    'subtitle': 'What each weekly paste feeds, and the checks that decide whether the numbers can be trusted.',
    'mermaid': '''flowchart TD
s(["Weekly export day"]):::terminator
sh[/"Paste Sales History<br/>posted invoice lines"/]:::export
c1{{"Covers the sample week<br/>and 3 weeks before?"}}:::decision
short["Missing weeks count as 0<br/>and pull the average down"]:::issue
avg["DSD_DSnD H:M: SUMIFS of Quantity<br/>by No. and Posting Date"]:::calc
so[/"Paste Open Sales Lines<br/>open order lines"/]:::export
c2{{"Row 284 grid dates<br/>are real dates?"}}:::decision
zero["Order grids stay 0"]:::issue
grid["Dist_DSnD order grids: SUMIFS of<br/>Quantity by Shipment Date"]:::calc
piv["Refresh the Dist Shipping pivot:<br/>Outstanding Quantity, DIST only"]:::output
bom[/"Paste BOMQty when BOMs change<br/>Quantity Explosion of BOM"/]:::export
c3{{"BOMQty current?"}}:::decision
old["Bags use old recipes:<br/>As of 03/24/26"]:::issue
wt["Dough Weight = SUMIFS of BOMQty<br/>by No_Item"]:::lookup
e(["Exports ready for the week"]):::terminator
s --> sh
sh --> c1
c1 -->|"No"| short
c1 -->|"Yes"| avg
short -.-> avg
avg --> so
so --> c2
c2 -->|"No"| zero
c2 -->|"Yes"| grid
zero -.-> grid
grid --> piv
piv --> bom
bom --> c3
c3 -->|"No"| old
c3 -->|"Yes"| wt
old -.-> wt
wt --> e''',
    'inputs': [
        '**Sales History**: 203,445 rows, posting dates 5/2 to 9/23/2026. Used: No. (E), Posting Date (G), Quantity (L).',
        '**Open Sales Lines**: 1,438 rows. Used: No. (F), Quantity (J), Shipment Date (N), Outstanding Quantity (O). DSD or DIST (P) is a formula.',
        '**BOMQty**: 15,118 rows on DoughWeights O:AJ. Used: No_Item (T) and BOMQty (AF).',
        '**H3:M3 sample dates**: built from H2.',
        '**Row 284 dates**: typed above each Dist_DSnD order grid.',
    ],
    'formulas': [
        f"**Sun/Mon demand (DSD_DSnD H)** {T('DSD_DSnD', 'Sun/Mon')}",
        f"**Order grid (Dist_DSnD 0_Sun)** {T('Dist_DSnD', '0_Sun')}",
        f"**DSD or DIST (SalesOrders P)** {T('SalesOrders', 'DSD or DIST')}",
        f"**Dough Weight (Dough I)** {T('Dough', 'Weight')}",
    ],
    'example': [
        '**F1000 Rye 1/2 inch, Sun/Mon**: H3 = 9/14. SUMIFS reads 9/14, 9/7, 8/31 and 8/24; the average is 17.5 packs.',
        '**Labor Day** 9/7 is one of those four dates.',
        '**F51000 case, 0_Sun**: BI284 holds the text 8/31/2026, which never equals a Shipment Date, so the grid shows 0.',
        '**D10001 Challah Dough**: Dough Weight 177.27 lb is the sum of its BOMQty lines (Flour 100, Water 56, and the rest).',
    ],
    'questions': [
        'How many weeks of Sales History should be pasted? The formulas need 4 weeks up to the sample week; the file holds about 20.',
        'Should the order-grid dates in row 284 be formulas from H2 instead of typed text?',
        'Who refreshes BOMQty, and should Dough Weight warn when the export is older than a set number of days?',
        'Should the Dist Shipping pivot refresh when the file opens so it cannot go stale?',
    ],
})

# ------------------------------------------------------------------ 3
SPECS.append({
    'section': 3,
    'title': '3. Inventory, Sunday to Friday: Logic Spec',
    'subtitle': 'One SKU on one day: counts come in from _BC.xlsm, reconcile against yesterday and close the day.',
    'mermaid': '''flowchart TD
s(["Start of day, one SKU"]):::terminator
row[/"Code from the A3 row list:<br/>FG then FG-DIST"/]:::lookup
init{{"Sunday?"}}:::decision
i1[/"Initial Inventory from<br/>_BC.xlsm column C"/]:::lookup
i2[/"Initial Inventory =<br/>yesterday's Final Inventory"/]:::lookup
cnt[/"Freezer and Floor from<br/>_BC.xlsm columns F and G"/]:::lookup
dif["Diferencias =<br/>Initial - (Freezer + Floor)"]:::calc
q{{"Diferencias = 0?"}}:::decision
var["Count and chain disagree:<br/>check the count"]:::issue
ld[/"Late/Day Orders (H) and<br/>Inv. Discounts (M)"/]:::lookup
tot["Total = Freezer + Floor<br/>- Late/Day Orders - Inv. Discounts"]:::calc
wo[/"Wrapped (J) and Order (K)"/]:::lookup
fin["Final Inventory =<br/>Total + Wrapped - Order"]:::calc
dsd["Total goes to DSD_DSnD _Floor<br/>and Dist_DSnD 0_Inventory"]:::output
e(["Final Inventory becomes<br/>tomorrow's Initial Inventory"]):::terminator
s --> row
row --> init
init -->|"Yes"| i1
init -->|"No"| i2
i1 --> cnt
i2 --> cnt
cnt --> dif
dif --> q
q -->|"No"| var
q -->|"Yes"| ld
var -.-> ld
ld --> tot
tot --> dsd
tot --> wo
wo --> fin
fin --> e
e -.->|"next day"| init''',
    'inputs': [
        f"**Code** (B): {T('Sunday', 'Code')}, from the row list of 395 SKUs.",
        '**_BC.xlsm day tab** (external file on SharePoint): where the floor count is typed. Tabs Sunday - Inventory to Friday-Inventory.',
        '**Freezer F, Floor G, Late/Day Orders H, Wrapped J, Order K, Inv. Discounts M**: columns of the external tab, read by XLOOKUP on the code.',
        "**Initial Inventory**: external column C on Sunday; the previous day's Final Inventory after that.",
        '**QC columns O:T**: typed on the sheet and not read by any formula.',
    ],
    'formulas': [
        f"**Freezer (G)** {T('Sunday', 'Freezer')}",
        f"**Initial Inventory, Monday (D)** {T('Monday', 'Initial Inventory')}",
        f"**Diferencias (F)** {T('Sunday', 'Diferencias')}",
        f"**Total (J)** {T('Sunday', 'Total')}",
        f"**Final Inventory (M)** {T('Sunday', 'Final Inventory')}",
        f"**Julian Date (U)** {T('Sunday', 'Julian Date')}",
    ],
    'example': [
        '**F1000 Rye 1/2 inch, Sunday**: Initial 79 (external C), Freezer 79, Floor 0, so Diferencias = 79 - (79 + 0) = 0.',
        '**Sunday close**: Total 79; Wrapped 0 and Order 27, so Final Inventory 52.',
        "**Monday**: Initial 52 (Sunday's Final); Freezer 52, Floor 0, Diferencias 0; Wrapped 96, Order 9, Final 139.",
        '**Hand-off**: DSD_DSnD S_Floor for F1000 = 79 and M_Floor = 52.',
    ],
    'questions': [
        'When Diferencias is not 0, should the day stop, or is the count taken as right and the difference only logged?',
        'Freezer (Day Before) is calculated on Monday to Friday but nothing reads it: keep it as a check, or remove it?',
        'Should the counts be typed in this workbook instead of the external _BC.xlsm file?',
        'Should the Tuesday to Friday tables be trimmed to the 395-row list so the extra N/A rows go away?',
    ],
})

# ------------------------------------------------------------------ 4
SPECS.append({
    'section': 4,
    'title': '4. Daily Supply and Demand: Logic Spec',
    'subtitle': 'One SKU on one day: average past sales, add the buffer, subtract stock, and bake what is left.',
    'mermaid': '''flowchart TD
s(["One DSD SKU, one day"]):::terminator
row[/"Sku from the A8 row list, FG only"/]:::lookup
a[/"Asset from Products"/]:::lookup
tp{{"3rd Party or<br/>3rd Party - Bake?"}}:::decision
one["Sales on the sample date only"]:::calc
avg["Average of the same weekday<br/>over 4 weeks: 0, 7, 14, 21 days back"]:::calc
th{{"Thursday and Asset<br/>not MCS LINE?"}}:::decision
d1["_Demand = ROUNDUP(avg x 1.2)"]:::calc
d2["TH_Demand = ROUNDUP(Thur/Fri x 1.2<br/>+ Fri/Sat x 1.2)"]:::calc
fl[/"_Floor = that day's Total"/]:::lookup
fz[/"_Freeze: typed, blank today"/]:::input
bal["_Balance = Freeze + Floor - Demand"]:::calc
pr["_Production = _Balance"]:::calc
q{{"Production below 0?"}}:::decision
bake["Bake ABS(Production) packs:<br/>to DoughWeights and Mix-Slice-Oven"]:::output
e(["Stock covers demand"]):::terminator
s --> row
row --> a
a --> tp
tp -->|"Yes"| one
tp -->|"No"| avg
one --> th
avg --> th
th -->|"No"| d1
th -->|"Yes"| d2
d1 --> bal
d2 --> bal
fl --> bal
fz -.-> bal
bal --> pr
pr --> q
q -->|"Yes"| bake
q -->|"No"| e''',
    'inputs': [
        f"**Sku** (F): {T('DSD_DSnD', 'Sku')}, from the row list of 275 FG SKUs.",
        '**Asset** (B): from Products. Decides the 3rd-party branch and the Thursday rule.',
        '**SalesHistory**: No., Posting Date, Quantity.',
        f"**H3:M3 sample dates**: H3 {X('Daily Supply & Demand!H3')} = 9/14.",
        '**C5 buffer**: 1.2, typed.',
        "**_Floor**: that day's Total from the day table. **_Freeze**: typed, blank today.",
        "**Dist side**: demand from the external file's 'Daily Supply & Demand'!E249:L374; open orders from SalesOrders.",
    ],
    'formulas': [
        f"**Sun/Mon demand (H)** {T('DSD_DSnD', 'Sun/Mon')}",
        f"**S_Demand (U)** {T('DSD_DSnD', 'S_Demand')}",
        f"**TH_Demand (AW)** {T('DSD_DSnD', 'TH_Demand')}",
        f"**S_Floor (T)** {T('DSD_DSnD', 'S_Floor')}",
        f"**S_Balanace (V)** {T('DSD_DSnD', 'S_Balanace')}; **S_Production (W)** {T('DSD_DSnD', 'S_Production')}",
        f"**Dist demand (Dist_DSnD H)** {T('Dist_DSnD', 'Sun/Mon')}. No buffer; Dist _Production = minus demand.",
    ],
    'example': [
        '**F1000 Rye 1/2 inch, Sunday**: Sun/Mon average 17.5 packs, so S_Demand = ROUNDUP(17.5 x 1.2) = 21.',
        '**Sunday stock**: S_Floor 79, so S_Balanace = (0 + 79) - 21 = 58. Nothing to bake.',
        '**Thursday**: Asset Breadline is not MCS LINE, so TH_Demand = ROUNDUP(27.75 x 1.2 + 9.5 x 1.2) = 45. TH_Floor 113, balance 68.',
        '**Friday**: F_Floor 0 (not counted yet), F_Demand = ROUNDUP(9.5 x 1.2) = 12, F_Production -12. Bake 12 packs.',
        '**Case twin F51000**: Dist demand is 0 on every day, so its production is 0.',
    ],
    'questions': [
        'Is baking Fri/Sat demand on Thursday meant for every line except MCS, given that Friday still carries its own Fri/Sat demand?',
        'Should Dist demand get the same 1.2 buffer, and net against cases on hand?',
        'Should the 4-week average skip holidays such as Labor Day (9/7)?',
        'Is the typed row 264 (F6502, 48 every day) a deliberate override? If so, where should overrides live?',
    ],
})

# ------------------------------------------------------------------ 5
SPECS.append({
    'section': 5,
    'title': '5. DoughWeights: Logic Spec',
    'subtitle': 'Only packs that are short become pounds of dough; each dough row then adds up its products.',
    'mermaid': '''flowchart TD
s(["One row of the DoughWeight table"]):::terminator
row[/"Sku from the A4 row list:<br/>each dough, then its products"/]:::lookup
filt["Row list skips descriptions<br/>with OBS and Z codes"]:::calc
lob["Lobster rolls match OBS<br/>and are skipped"]:::issue
dq{{"D-code dough row?"}}:::decision
sum["Dough row = SUMIFS of the column<br/>over rows with the same Dough Desc"]:::calc
cq{{"Case SKU, starts F5?"}}:::decision
dist[/"Production from Dist_DSnD"/]:::lookup
dsd[/"Production from DSD_DSnD"/]:::lookup
q{{"Production below 0?"}}:::decision
zero["0 lb"]:::calc
w[/"Weight: lb of dough per pack,<br/>from Products"/]:::lookup
lb["lb = ABS(Production) x Weight"]:::calc
out["Mix-Slice-Oven: bags =<br/>lb / Dough Weight x Scrap"]:::output
e(["Pounds per day, Sunday to Friday"]):::terminator
s --> row
row --> filt
filt -.-> lob
filt --> dq
dq -->|"Yes"| sum
dq -->|"No"| cq
cq -->|"Yes"| dist
cq -->|"No"| dsd
dist --> q
dsd --> q
q -->|"No"| zero
q -->|"Yes"| lb
w --> lb
lb --> out
lb -.->|"rolls up"| sum
zero --> e
sum --> e
out --> e''',
    'inputs': [
        "**Sku** (B): the row's own A cell, from the A4 list of 453 rows.",
        '**Dough Desc** (D) and **Weight** (E): from Products.',
        '**Production**: S_ to F_Production from DSD_DSnD, or from Dist_DSnD for F5 case SKUs.',
        f"**F2 anchor date**: {X('DoughWeights!F2')}, display only.",
    ],
    'formulas': [
        f"**Row list (A4)** {X('DoughWeights!A4')}",
        f"**Sun (F)** {T('DoughWeight', 'Sun')}",
        f"**Dough Desc (D)** {T('DoughWeight', 'Dough Desc')}",
        f"**Weight (E)** {T('DoughWeight', 'Weight')}",
        '**Day columns** F Sun reads S_Production, G Mon M_, H Tue T_, I Wed W_, J Thur TH_, K Fri F_.',
    ],
    'example': [
        '**F1127 Challah 3-Braid 21oz, Friday**: F_Production -36 in DSD_DSnD, so 36 packs are short.',
        '**Pounds**: 36 x 1.3125 = 47.25 lb in DoughWeight Fri.',
        '**Sunday to Thursday**: F1127 shows 0 lb because its balance was not negative on those days.',
        '**D10001 Challah Dough row**: Sun 454, Mon 965, Tue 1,176, Wed 402.5, Thu 1,074, Fri 1,220.25 lb.',
    ],
    'questions': [
        'Should the obsolete filter use Gen. Prod. Posting Group so Lobster rolls get dough?',
        'Should case SKUs net against cases on hand before they create dough?',
        'The D-code rows repeat the product totals: keep them for reading, or remove them now that Mix-Slice-Oven sums products itself?',
        'Column L (the old existence check) is broken on every row: delete it?',
    ],
})

# ------------------------------------------------------------------ 6
SPECS.append({
    'section': 6,
    'title': '6. Mix-Slice-Oven: Logic Spec',
    'subtitle': 'One run on the K4 day: pounds become bags, bags round up to whole mixes, mixes become minutes.',
    'mermaid': '''flowchart TD
s(["One mixing run on the K4 day"]):::terminator
k4[/"K4 day selector: Tuesday"/]:::input
lbd[/"lb for that day<br/>from DoughWeight"/]:::lookup
l["L = ROUND(lb / Dough Weight, 2)<br/>x Scrap Factor, for each SKU"]:::calc
first{{"First row of this<br/>Unique Dough run?"}}:::decision
blank["M blank on the later rows"]:::calc
m["M = SUMIFS of L over the run"]:::calc
marble{{"Marble Hearth or<br/>Marble Lg Pullman?"}}:::decision
n1["N = CEILING(M, bags per mix)"]:::calc
n2["N = CEILING(M, bags per mix) x 2.5"]:::calc
o["O Planned Total = N<br/>type over it to override"]:::calc
tot["O1 Breadline, O2 MCS LINE:<br/>line totals"]:::output
mins["_Minutes per day = _Planned /<br/>bags per mix x Run Time Per Mix"]:::calc
hrs["Rows 1-2: bags and hours<br/>back to Supply and Demand"]:::output
e(["Schedules print the planned bags"]):::terminator
s --> k4
k4 --> lbd
lbd --> l
l --> first
first -->|"No"| blank
first -->|"Yes"| m
m --> marble
marble -->|"No"| n1
marble -->|"Yes"| n2
n1 --> o
n2 --> o
o --> tot
o -.->|"each day"| mins
mins --> hrs
tot --> e''',
    'inputs': [
        "**K4** (Mix-Slice-Oven!K4): the day, typed. This week Tuesday.",
        '**DoughWeight lb** for that day (Sun to Fri columns).',
        '**Dough Weight** (Dough I): lb in one bag of dough.',
        '**Scrap Factor**, **optimal bags per mix** and **Run Time Per Mix**: from Products and Unique Dough.',
        '**Unique Dough**: groups SKUs into runs. The A6 list is sorted so each run is one block of rows.',
        '**Pans**: pieces per pan, for Oven_Info.',
    ],
    'formulas': [
        f"**L Dough Weight** {T('Mix_Slice_Oven', 'Dough Weight')}",
        f"**M Bags By Unique Dough** {T('Mix_Slice_Oven', 'Bags By Unique Dough')}",
        f"**N Optimal Total** {T('Mix_Slice_Oven', 'Optimal Total')}",
        f"**O Planned Total** {T('Mix_Slice_Oven', 'Planned Total')}",
        f"**S_Minutes (BD)** {T('Mix_Slice_Oven', 'S_Minutes')}",
        f"**O1 Breadline bags** {X('Mix-Slice-Oven!O1')}",
    ],
    'example': [
        '**6" Italian Rolls, Tuesday (MCS LINE)**: L for each SKU is F3091 2.849, F3094 0.759, F3092 0.011, F30941 0.022 and case F53094 4.774 bags.',
        '**Run total**: M = 8.415 bags on the first row. Optimal bags per mix 4, so N = CEILING(8.415, 4) = 12 and Planned 12.',
        '**On the MCS sheet**: 3 mixes of 4 bags, 20 minutes each.',
        '**Challah 3 Braided, Tuesday**: F1127 0 bags; case F51127 is 20 cases short, 1.298 bags. N = CEILING(1.298, 1) = 2; T_Minutes = 2 / 1 x 30 = 60.',
        '**Line totals**: O1 Breadline 54.5 bags, O2 MCS LINE 180 bags.',
    ],
    'questions': [
        "Should K4 follow today's date by default?",
        'Should Extra Bread (Runout) in column X add to the bags before they are rounded up?',
        'The per-day blocks round after scrap while L rounds before: which is intended?',
        'For Marble runs, is 2.5 the Pump plus Rye bags per set, and should it live in Unique Dough instead of the formula?',
    ],
})

# ------------------------------------------------------------------ 7
MCS_A5, BL_A5 = X('MCS Schedule!A5'), X('Breadline Schedule!A5')
F_KEEP = part(MCS_A5, 'keep,FILTER(ud,(pt>0)*(ud<>"")*(as="MCS LINE"),"")')
F_SORT = part(MCS_A5, 'p,IF(x="",9999,IFERROR(--x,9999))')
F_MIX = part(MCS_A5, 'k,IF(bpm>0,ROUNDUP(tot/bpm,0),1)')
F_ROWS = part(MCS_A5, 'cum,SCAN(0,k,LAMBDA(a,v,a+v)),r,SEQUENCE(n),idx,MAP(r,LAMBDA(v,XMATCH(v,cum,1)))')
F_CO = part(MCS_A5, 'co_ord,MAP(ci,LAMBDA(v,IF(v=0,0,IFERROR(--INDEX(upl,v-1),0)+0.5)))')
F_OK = part(MCS_A5, 'okco,(co_ord>MIN(ord))*(co_ord<MAX(ord))')
F_SETS = part(BL_A5, 'sets,IF(mu="",0,ROUNDUP(mt/(pb+rb),0))')
SPECS.append({
    'section': 7,
    'title': '7. MCS and Breadline schedules: Logic Spec',
    'subtitle': 'How the A5 formula turns Planned Total into one printed row per mix, in placement order.',
    'mermaid': '''flowchart TD
s(["Planned Total ready<br/>on Mix-Slice-Oven"]):::terminator
f["Keep runs with Planned above 0<br/>on this line"]:::calc
line{{"Breadline sheet?"}}:::decision
mar["Marble runs become sets of<br/>Pump 1 bag + Rye 1.5 bags"]:::calc
srt["Sort runs by Placement On Scedule:<br/>text or blank sorts last"]:::lookup
k["Mixes per run = ROUNDUP(bags /<br/>Optimal Bag), 1 if none"]:::calc
scan["SCAN running count:<br/>one row per mix"]:::calc
mcs{{"MCS sheet?"}}:::decision
co["Add Changeover rows at placement<br/>above + 0.5, inside the day only"]:::calc
il["Keep Pump and Rye rows<br/>alternating"]:::calc
att[/"Notes and attributes N:S from<br/>Critical Lookup Information"/]:::lookup
bc["Bag Count: bags mixed,<br/>raw DSD and raw DIST per run"]:::calc
pan[/"MCS only: pans to set out<br/>from Oven_Info"/]:::lookup
e4[/"E4 start time, typed"/]:::input
nt["No start or finish times<br/>are calculated"]:::issue
out(["Printed run sheet"]):::terminator
s --> f
f --> line
line -->|"Yes"| mar
line -->|"No"| srt
mar --> srt
srt --> k
k --> scan
scan --> mcs
mcs -->|"Yes"| co
mcs -->|"No"| il
co --> att
il --> att
att --> bc
bc --> pan
pan --> out
e4 -.-> nt
nt -.-> out''',
    'inputs': [
        '**Mix_Slice_Oven**: Unique Dough, Asset and Planned Total.',
        '**Unique Dough table**: Placement On Scedule, Optimal Bag, Optimal Time. Changeover rows carry Optimal Time 10.',
        '**Critical Lookup Information D:O**: notes and attributes shown in N:S.',
        '**Oven_Info**: # of Pans/Boxes to set out, listed in MCS F29.',
        '**E4**: typed first-mix start (MCS 6:45, Breadline 7:50).',
        f"**H2 total bags**: MCS {X('MCS Schedule!H2')}, Breadline {X('Breadline Schedule!H2')}.",
    ],
    'formulas': [
        f"**Keep (MCS A5)** {F_KEEP}",
        f"**Sort key** {F_SORT}",
        f"**Mixes per run** {F_MIX}",
        f"**One row per mix** {F_ROWS}",
        f"**Changeover placement** {F_CO}, kept if {F_OK}",
        f"**Marble sets (Breadline A5)** {F_SETS}",
    ],
    'example': [
        '**6" Italian Rolls (MCS)**: Planned 12 bags, Optimal Bag 4, so ROUNDUP(12 / 4) = 3 mixes on rows 5 to 7, 4 bags and 20 minutes each.',
        '**Its Bag Count row**: 12 bags mixed against 3.641 raw DSD bags and 4.774 raw DIST bags.',
        '**Changeover**: the Bag Count lists a Changeover between 7" Potato Hot Dog Roll and Challah Slider Roll.',
        '**Marble (Breadline)**: the Marble Hearth run becomes Pump for Marble Hearth 2 bags and Rye for Marble Hearth 3 bags.',
        '**As saved**: MCS 47 mixes + 2 changeovers, 180 bags; Breadline 25 mixes, 54.5 bags.',
    ],
    'questions': [
        'Should the sheet calculate start and finish times from E4 and the run minutes?',
        'Several runs share a placement (48, 50, 53): which should go first?',
        'Should the Bag Count summary move so it no longer covers Time Start, Time Finish, Temp and Operator?',
        'Should notes and attributes come from Unique Dough so there is one list to maintain?',
    ],
})

# ------------------------------------------------------------------ 8
SPECS.append({
    'section': 8,
    'title': '8. Recon: Logic Spec',
    'subtitle': 'Each row of the Recon table compares a spilled row list with the table beside it.',
    'mermaid': '''flowchart TD
s(["One row of the Recon table"]):::terminator
b["Array Cell: read the spill address<br/>from the Array Rows formula text"]:::calc
c[/"Array Rows = ROWS(ANCHORARRAY(spill))"/]:::lookup
t[/"Table Rows = ROWS(Adjacent Table[])"/]:::lookup
f["Difference = Array Rows - Table Rows"]:::calc
g1{{"Array Rows = Table Rows?"}}:::decision
m(["Status Match: every SKU has a row"]):::terminator
g2{{"Table Rows bigger?"}}:::decision
tl["Status Table longer: extra rows<br/>show N/A, harmless"]:::output
al["Status Array longer: the last SKUs<br/>have no table row"]:::issue
fix[/"Resize the table to the spill"/]:::input
nc["Not checked: values inside rows,<br/>BOM weights, K4, dates"]:::output
s --> c
c --> b
s --> t
c --> f
t --> f
f --> g1
g1 -->|"Yes"| m
g1 -->|"No"| g2
g2 -->|"Yes"| tl
g2 -->|"No"| al
al --> fix
tl -.-> fix
m -.-> nc''',
    'inputs': [
        '**Sheet** and **Adjacent Table**: typed labels in the Recon table.',
        '**Spilled row lists**: Sunday to Friday A3, Daily Supply & Demand A8 and A287, DoughWeights A4, Mix-Slice-Oven A6 and A410.',
        '**Adjacent tables**: Sunday to Friday, DSD_DSnD, Dist_DSnD, DoughWeight, Mix_Slice_Oven, Oven_Info.',
    ],
    'formulas': [
        f"**Array Cell** {RECON_F['Array Cell']}",
        f"**Array Rows** {RECON_F['Array Rows']} (Sunday row; each row names its own spill)",
        f"**Table Rows** {RECON_F['Table Rows']} (Sunday row; each row names its own table)",
        f"**Difference (Array − Table)** {RECON_F['Difference (Array − Table)']}",
        f"**Status** {RECON_F['Status']}",
    ],
    'example': [
        '**DoughWeight**: Array Rows 453 (DoughWeights A4#), Table Rows 452, Difference 1, Status Array longer: the last SKU, F2562, gets no formulas.',
        '**Wednesday**: Array Rows 395, Table Rows 447, Difference -52, Status Table longer: 52 rows of N/A under the list.',
        '**Mix_Slice_Oven**: Array Rows 390, Table Rows 391, Difference -1, Status Table longer.',
        '**Sunday, Monday, DSD_DSnD, Dist_DSnD**: Status Match.',
    ],
    'questions': [
        'Should Recon also count N/A errors inside each table?',
        'Should any status other than Match turn a header red so it is seen before printing?',
        "Should Recon compare Sunday!B1 with the anchor date and K4 with today's day?",
    ],
})


if __name__ == '__main__':
    json.dump(SPECS, open(os.path.join(HERE, 'specs.json'), 'w'), indent=1)
    print(len(SPECS), 'specs written')
