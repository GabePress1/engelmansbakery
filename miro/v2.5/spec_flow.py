"""Logic Spec flowcharts, laid out as rows so they fit beside the Doc.

Miro draws a diagram at its natural Mermaid size, so a long `flowchart TD` chain runs
far below its frame. Each chart here is `flowchart TD` over two or three row subgraphs,
each `direction LR`. Edges between rows join the subgraphs themselves: Mermaid ignores a
subgraph's direction as soon as one of its nodes links outside it.
"""

FLOWS = {}

FLOWS[0] = '''flowchart TD
subgraph row1["1. Paste and count"]
direction LR
s(["Start of the planning week"]):::terminator
p1[/"Paste Sales History<br/>posted invoice lines"/]:::export
p2[/"Set Daily Supply and Demand H2<br/>to the planning Sunday"/]:::input
p3[/"Paste Open Sales Lines<br/>refresh the Dist Shipping pivot"/]:::export
c1[/"Floor counts typed in the<br/>_BC.xlsm day tabs"/]:::input
s --> p1
p1 --> p2
p2 --> p3
p3 --> c1
end
subgraph row2["2. Calculate"]
direction LR
d1["Sunday to Friday tables:<br/>Total and Final Inventory"]:::lookup
d2["Supply and Demand:<br/>stock minus demand = Production"]:::calc
d3["DoughWeights:<br/>packs short x lb per pack"]:::calc
k4{{"Is K4 the day<br/>being baked?"}}:::decision
fix[/"Set Mix-Slice-Oven K4"/]:::input
d4["Mix-Slice-Oven:<br/>bags, planned bags, minutes"]:::calc
d1 --> d2
d2 --> d3
d3 --> k4
k4 -->|"No"| fix
fix --> d4
k4 -->|"Yes"| d4
end
subgraph row3["3. Check and print"]
direction LR
r1{{"Recon shows<br/>Array longer?"}}:::decision
iss["SKUs dropped from a table:<br/>resize it before printing"]:::issue
o1["MCS and Breadline schedules<br/>printed run sheets"]:::output
e(["Bake"]):::terminator
r1 -->|"Yes"| iss
iss -.-> o1
r1 -->|"No"| o1
o1 --> e
end
row1 --> row2
row2 -->|"bags and minutes"| row3
'''

FLOWS[1] = '''flowchart TD
subgraph row1["1. Which lists the row joins"]
direction LR
s(["One product row in Products"]):::terminator
g{{"Gen. Prod. Posting Group?"}}:::decision
obs["OBS: left out of the row lists"]:::output
fg[/"FG: day tables and DSD_DSnD"/]:::input
dist[/"FG-DIST: day tables and Dist_DSnD"/]:::input
s --> g
g -->|"OBS"| obs
g -->|"FG"| fg
g -->|"FG-DIST"| dist
end
subgraph row2["2. Dough"]
direction LR
oc{{"Description contains OBS?"}}:::decision
lob["Skipped by DoughWeights:<br/>Lobster rolls get no dough"]:::issue
dw["DoughWeights row under its<br/>Dough code, lb = packs x Weight"]:::calc
wt["Dough Weight = SUMIFS of BOMQty<br/>for the D-code, lb per bag"]:::lookup
oc -->|"Yes"| lob
oc -->|"No"| dw
dw --> wt
end
subgraph row3["3. Mixing"]
direction LR
r{{"Asset Rank at most 3?"}}:::decision
tp["Third party: no Mix-Slice-Oven row,<br/>so no bags or minutes"]:::output
ud{{"Unique Dough name found<br/>in the Unique Dough table?"}}:::decision
blank["Blank bags per mix and minutes"]:::issue
mix["Mix-Slice-Oven row: Optimal Bag,<br/>Optimal Time, Placement"]:::lookup
pan[/"Pans/Boxes: Oven_Info pan block"/]:::lookup
e(["Row feeds Supply and Demand,<br/>DoughWeights and Mix-Slice-Oven"]):::terminator
r -->|"No"| tp
r -->|"Yes"| ud
ud -->|"No"| blank
ud -->|"Yes"| mix
mix --> pan
pan --> e
end
row1 -->|"FG and FG-DIST"| row2
row2 -->|"lb per day"| row3
'''

FLOWS[2] = '''flowchart TD
subgraph row1["1. Sales History"]
direction LR
s(["Weekly export day"]):::terminator
sh[/"Paste Sales History<br/>posted invoice lines"/]:::export
c1{{"Covers the sample week<br/>and 3 weeks before?"}}:::decision
short["Missing weeks count as 0<br/>and pull the average down"]:::issue
avg["DSD_DSnD H:M: SUMIFS of Quantity<br/>by No. and Posting Date"]:::calc
s --> sh
sh --> c1
c1 -->|"No"| short
c1 -->|"Yes"| avg
short -.-> avg
end
subgraph row2["2. Open Sales Lines"]
direction LR
so[/"Paste Open Sales Lines<br/>open order lines"/]:::export
c2{{"Row 284 grid dates<br/>are real dates?"}}:::decision
zero["Order grids stay 0"]:::issue
grid["Dist_DSnD order grids: SUMIFS of<br/>Quantity by Shipment Date"]:::calc
piv["Refresh the Dist Shipping pivot:<br/>Outstanding Quantity, DIST only"]:::output
so --> c2
c2 -->|"No"| zero
c2 -->|"Yes"| grid
zero -.-> grid
grid --> piv
end
subgraph row3["3. BOMQty, when BOMs change"]
direction LR
bom[/"Paste BOMQty<br/>Quantity Explosion of BOM"/]:::export
c3{{"BOMQty current?"}}:::decision
old["Bags use old recipes:<br/>As of 03/24/26"]:::issue
wt["Dough Weight = SUMIFS of BOMQty<br/>by No_Item"]:::lookup
e(["Exports ready for the week"]):::terminator
bom --> c3
c3 -->|"No"| old
c3 -->|"Yes"| wt
old -.-> wt
wt --> e
end
row1 --> row2
row2 --> row3
'''

FLOWS[3] = '''flowchart TD
subgraph row1["1. Opening stock"]
direction LR
s(["Start of day, one SKU"]):::terminator
row[/"Code from the A3 row list:<br/>FG then FG-DIST"/]:::lookup
init{{"Sunday?"}}:::decision
i1[/"Initial Inventory from<br/>_BC.xlsm column C"/]:::lookup
i2[/"Initial Inventory =<br/>yesterday's Final Inventory"/]:::lookup
cnt[/"Freezer and Floor from<br/>_BC.xlsm columns F and G"/]:::lookup
s --> row
row --> init
init -->|"Yes"| i1
init -->|"No"| i2
i1 --> cnt
i2 --> cnt
end
subgraph row2["2. Count check"]
direction LR
dif["Diferencias =<br/>Initial - (Freezer + Floor)"]:::calc
q{{"Diferencias = 0?"}}:::decision
var["Count and chain disagree:<br/>check the count"]:::issue
ld[/"Late/Day Orders (H) and<br/>Inv. Discounts (M)"/]:::lookup
dif --> q
q -->|"No"| var
q -->|"Yes"| ld
var -.-> ld
end
subgraph row3["3. Close the day"]
direction LR
tot["Total = Freezer + Floor<br/>- Late/Day Orders - Inv. Discounts"]:::calc
dsd["Total goes to DSD_DSnD _Floor<br/>and Dist_DSnD 0_Inventory"]:::output
wo[/"Wrapped (J) and Order (K)"/]:::lookup
fin["Final Inventory =<br/>Total + Wrapped - Order"]:::calc
e(["Final Inventory becomes<br/>tomorrow's Initial Inventory"]):::terminator
tot --> dsd
tot --> wo
wo --> fin
fin --> e
end
row1 -->|"Freezer and Floor"| row2
row2 --> row3
'''

FLOWS[4] = '''flowchart TD
subgraph row1["1. Sales to average"]
direction LR
s(["One DSD SKU, one day"]):::terminator
row[/"Sku from the A8 row list, FG only"/]:::lookup
a[/"Asset from Products"/]:::lookup
tp{{"3rd Party or<br/>3rd Party - Bake?"}}:::decision
one["Sales on the sample date only"]:::calc
avg["Average of the same weekday<br/>over 4 weeks: 0, 7, 14, 21 days back"]:::calc
s --> row
row --> a
a --> tp
tp -->|"Yes"| one
tp -->|"No"| avg
end
subgraph row2["2. Demand with a 20% buffer"]
direction LR
th{{"Thursday and Asset<br/>not MCS LINE?"}}:::decision
d1["_Demand = ROUNDUP(avg x 1.2)"]:::calc
d2["TH_Demand = ROUNDUP(Thur/Fri x 1.2<br/>+ Fri/Sat x 1.2)"]:::calc
th -->|"No"| d1
th -->|"Yes"| d2
end
subgraph row3["3. Balance"]
direction LR
fl[/"_Floor = that day's Total"/]:::lookup
fz[/"_Freeze: typed, blank today"/]:::input
bal["_Balance = Freeze + Floor - Demand"]:::calc
pr["_Production = _Balance"]:::calc
q{{"Production below 0?"}}:::decision
bake["Bake ABS(Production) packs:<br/>to DoughWeights and Mix-Slice-Oven"]:::output
e(["Stock covers demand"]):::terminator
fl --> bal
fz -.-> bal
bal --> pr
pr --> q
q -->|"Yes"| bake
q -->|"No"| e
end
row1 -->|"average"| row2
row2 -->|"_Demand"| row3
'''

FLOWS[5] = '''flowchart TD
subgraph row1["1. Row list"]
direction LR
s(["One row of the DoughWeight table"]):::terminator
row[/"Sku from the A4 row list:<br/>each dough, then its products"/]:::lookup
filt["Row list skips descriptions<br/>with OBS and Z codes"]:::calc
lob["Lobster rolls match OBS<br/>and are skipped"]:::issue
dq{{"D-code dough row?"}}:::decision
s --> row
row --> filt
filt -.-> lob
filt --> dq
end
subgraph row2["2. Product rows: pounds"]
direction LR
cq{{"Case SKU, starts F5?"}}:::decision
dist[/"Production from Dist_DSnD"/]:::lookup
dsd[/"Production from DSD_DSnD"/]:::lookup
q{{"Production below 0?"}}:::decision
zero["0 lb"]:::calc
w[/"Weight: lb of dough per pack,<br/>from Products"/]:::lookup
lb["lb = ABS(Production) x Weight"]:::calc
out["Mix-Slice-Oven: bags =<br/>lb / Dough Weight x Scrap"]:::output
cq -->|"Yes"| dist
cq -->|"No"| dsd
dist --> q
dsd --> q
q -->|"No"| zero
q -->|"Yes"| lb
w --> lb
lb --> out
end
subgraph row3["3. Dough rows"]
direction LR
sum["Dough row = SUMIFS of the column<br/>over rows with the same Dough Desc"]:::calc
e(["Pounds per day, Sunday to Friday"]):::terminator
sum --> e
end
row1 -->|"No: product rows"| row2
row2 -->|"lb rolls up"| row3
'''

FLOWS[6] = '''flowchart TD
subgraph row1["1. Bags for each SKU, then the run"]
direction LR
s(["One Unique Dough run, one day"]):::terminator
lbd[/"lb for that day from DoughWeight"/]:::lookup
l["L = ROUND(lb / Dough Weight, 2)<br/>x Scrap Factor, for each SKU"]:::calc
m["M = SUMIFS of L over the run,<br/>on its first row"]:::calc
s --> lbd
lbd --> l
l --> m
end
subgraph row2["2. Round up to whole mixes, then minutes"]
direction LR
marble{{"Marble Hearth or<br/>Marble Lg Pullman?"}}:::decision
n1["N = CEILING(M, bags per mix)"]:::calc
n2["N = CEILING(M, bags per mix) x 2.5"]:::calc
o["O Planned Total = N,<br/>type over it to override"]:::calc
mins["Minutes = Planned / bags per mix<br/>x minutes per mix, Marble / 2.5"]:::calc
marble -->|"No"| n1
marble -->|"Yes"| n2
n1 --> o
n2 --> o
o --> mins
end
subgraph row3["3. Breadline or MCS"]
direction LR
line{{"Asset?"}}:::decision
bl["Breadline or Breadline/Artisan:<br/>O1 bags, row 1 bags and hours"]:::output
mcs["MCS LINE:<br/>O2 bags, row 2 bags and hours"]:::output
sch(["Schedules print H2 bags"]):::terminator
dsd["Daily Supply and Demand<br/>rows 1-4 per day"]:::output
line -->|"Breadline"| bl
line -->|"MCS LINE"| mcs
bl --> sch
mcs --> sch
bl --> dsd
mcs --> dsd
end
row1 -->|"M bags for the run"| row2
row2 -->|"planned bags and minutes"| row3
'''

FLOWS[7] = '''flowchart TD
subgraph row1["1. Pieces needed"]
direction LR
s(["One pan on the K4 day"]):::terminator
k4[/"K4 day selector: Tuesday"/]:::input
rows[/"A410 row list: the pan,<br/>then each non-OBS product on it"/]:::lookup
d[/"Demand = packs short on the K4 day<br/>from DSD_DSnD or Dist_DSnD"/]:::lookup
pc["pieces = Demand x<br/>pieces per tray/box"]:::calc
s --> rows
rows --> d
k4 --> d
d --> pc
end
subgraph row2["2. Pans to set out"]
direction LR
sum["Pan row: SUMPRODUCT over products<br/>whose Pans/Boxes is this pan"]:::calc
pp[/"Pieces Per Pan from Pans"/]:::lookup
set["Set out = ROUNDUP(pieces / Pieces Per Pan)"]:::calc
q{{"Product under the pan on MCS LINE<br/>and set out above 0?"}}:::decision
f29(["Listed on MCS Schedule F29"]):::terminator
no["Counted but not printed:<br/>no pan list for other lines"]:::issue
sum --> set
pp --> set
set --> q
q -->|"Yes"| f29
q -->|"No"| no
end
row1 -->|"pieces per product"| row2
'''

FLOWS[8] = '''flowchart TD
subgraph row1["1. Which runs, in which order"]
direction LR
s(["Planned Total ready<br/>on Mix-Slice-Oven"]):::terminator
f["Keep runs with Planned above 0<br/>on this line"]:::calc
line{{"Breadline sheet?"}}:::decision
mar["Marble runs become sets of<br/>Pump 1 bag + Rye 1.5 bags"]:::calc
srt["Sort runs by Placement On Scedule:<br/>text or blank sorts last"]:::lookup
s --> f
f --> line
line -->|"Yes"| mar
line -->|"No"| srt
mar --> srt
end
subgraph row2["2. One row per mix"]
direction LR
k["Mixes per run = ROUNDUP(bags /<br/>Optimal Bag), 1 if none"]:::calc
scan["SCAN running count:<br/>one row per mix"]:::calc
mcs{{"MCS sheet?"}}:::decision
co["Add Changeover rows at placement<br/>above + 0.5, inside the day only"]:::calc
il["Keep Pump and Rye rows<br/>alternating"]:::calc
k --> scan
scan --> mcs
mcs -->|"Yes"| co
mcs -->|"No"| il
end
subgraph row3["3. What the sheet prints"]
direction LR
att[/"Notes and attributes N:S from<br/>Critical Lookup Information"/]:::lookup
bc["Bag Count: bags mixed,<br/>raw DSD and raw DIST per run"]:::calc
pan[/"MCS only: pans to set out<br/>from Oven_Info"/]:::lookup
e4[/"E4 start time, typed"/]:::input
nt["No start or finish times<br/>are calculated"]:::issue
out(["Printed run sheet"]):::terminator
att --> bc
bc --> pan
pan --> out
e4 -.-> nt
nt -.-> out
end
row1 -->|"sorted runs"| row2
row2 -->|"mix rows"| row3
'''

FLOWS[9] = '''flowchart TD
subgraph row1["1. Count both"]
direction LR
s(["One row of the Recon table"]):::terminator
c[/"Array Rows = ROWS(ANCHORARRAY(spill))"/]:::lookup
t[/"Table Rows = ROWS(Adjacent Table[])"/]:::lookup
b["Array Cell: read the spill address<br/>from the Array Rows formula text"]:::calc
f["Difference = Array Rows - Table Rows"]:::calc
s --> c
s --> t
c --> b
c --> f
t --> f
end
subgraph row2["2. Status"]
direction LR
g1{{"Array Rows = Table Rows?"}}:::decision
m(["Status Match: every SKU has a row"]):::terminator
g2{{"Table Rows bigger?"}}:::decision
tl["Status Table longer: extra rows<br/>show N/A, harmless"]:::output
al["Status Array longer: the last SKUs<br/>have no table row"]:::issue
fix[/"Resize the table to the spill"/]:::input
nc["Not checked: values inside rows,<br/>BOM weights, K4, dates"]:::output
g1 -->|"Yes"| m
g1 -->|"No"| g2
g2 -->|"Yes"| tl
g2 -->|"No"| al
al --> fix
tl -.-> fix
m -.-> nc
end
row1 -->|"Difference"| row2
'''
