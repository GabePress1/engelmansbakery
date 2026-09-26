"""Content of the Logic Spec row: one spec per main-row section (0-8).

Formulas are pulled from formulas.json through build.py's helpers (T for a table column,
X for a control cell), so no formula is retyped. `part(ref, text)` quotes a decisive
fragment of a long formula and fails if the fragment is not in that formula verbatim.
Worked-example numbers are the workbook's cached values (see README for how they were read).
Writes specs.json for spec.py.
"""
import json
import os

from build import RECON_F, T, V, X
from spec_flow import FLOWS

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
    'mermaid': FLOWS[0],
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
        '**Today** as saved 2026-09-26 is a Saturday, so DT2 = 1 and every sheet header prints Saturday.',
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
    'mermaid': FLOWS[1],
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
    'mermaid': FLOWS[2],
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
    'mermaid': FLOWS[3],
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
    'mermaid': FLOWS[4],
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
    'mermaid': FLOWS[5],
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
DAY_BAGS = lambda row: ', '.join(f"{d} {round(float(V(f'Mix-Slice-Oven!{c}{row}')), 2):g}"
                                 for d, c in zip(['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri'], ['AD', 'AI', 'AN', 'AS', 'AX', 'BC']))
DAY_HRS = lambda row: ', '.join(f"{d} {round(float(V(f'Mix-Slice-Oven!{c}{row}')), 2):g}"
                                for d, c in zip(['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri'], ['BD', 'BE', 'BF', 'BG', 'BH', 'BI']))
SPECS.append({
    'section': 6,
    'title': '6. Mix_Slice: Logic Spec',
    'subtitle': 'One run on one day: bags round up to whole mixes, minutes follow, and Asset puts the run on Breadline or MCS.',
    'mermaid': FLOWS[6],
    'inputs': [
        "**K4** (Mix-Slice-Oven!K4): the day for Planned Total and O1/O2, typed. This week Tuesday.",
        '**DoughWeight lb** per SKU and day; **Dough Weight** (Dough I) = lb in one bag.',
        '**Scrap Factor** (Products); **optimal bags per mix** and **Run Time Per Mix** (Unique Dough Optimal Bag and Optimal Time).',
        '**Asset** (Products): Breadline or Breadline/Artisan = Breadline; MCS LINE = MCS.',
    ],
    'formulas': [
        f"**L Dough Weight** {T('Mix_Slice', 'Dough Weight')}",
        f"**N Optimal Total** {T('Mix_Slice', 'Optimal Total')}",
        f"**S_Minutes** {T('Mix_Slice', 'S_Minutes')}",
        f"**O1 Breadline / O2 MCS bags** {X('Mix-Slice-Oven!O1')}; {X('Mix-Slice-Oven!O2')}",
        f"**Row 1 Breadline, Sunday** bags {X('Mix-Slice-Oven!AD1')}, hours {X('Mix-Slice-Oven!BD1')}",
        f"**Row 2 MCS, Sunday** bags {X('Mix-Slice-Oven!AD2')}, hours {X('Mix-Slice-Oven!BD2')}",
    ],
    'example': [
        '**Breadline: Challah 3 Braided, Tuesday**: M 1.298 bags, 1 bag per mix: N = 2, Planned 2, minutes 2 / 1 x 30 = 60.',
        '**MCS: 6" Italian Rolls, Tuesday**: M 8.415 bags, 4 bags per mix: N = 12, 3 mixes x 20 min = 60.',
        '**Breadline Marble Hearth, Tuesday**: M 1.672: CEILING = 2, x 2.5 = 5 bags; minutes 5 / 1 x 45 / 2.5 = 90.',
        f"**Breadline by day**: bags {DAY_BAGS(1)}; hours {DAY_HRS(1)}.",
        f"**MCS by day**: bags {DAY_BAGS(2)}; hours {DAY_HRS(2)}.",
        f"**K4 day (Tuesday)**: O1 {V('Mix-Slice-Oven!O1')} and O2 {V('Mix-Slice-Oven!O2')} bags, the same as row 1 and row 2 Tuesday.",
    ],
    'questions': [
        "Should K4 follow today's date by default, and should there be a K4-day hours cell next to O1 and O2?",
        'Should MCS changeover minutes, which exist only on the MCS Schedule, count in the MCS hours?',
        'The per-day blocks round after scrap while L rounds before: which is intended?',
        'Should Extra Bread (Runout) in column X add to the bags before they are rounded up?',
    ],
})

# ------------------------------------------------------------------ 7
SPECS.append({
    'section': 7,
    'title': '7. Oven_Info: Logic Spec',
    'subtitle': 'One pan on the K4 day: every product on it adds its pieces, and the total becomes whole pans.',
    'mermaid': FLOWS[7],
    'inputs': [
        "**K4** (Mix-Slice-Oven!K4): Demand is for this day. This week Tuesday.",
        '**Products**: Pans/Boxes (which pan a product goes on) and Pieces Per Tray/Case.',
        '**Pans**: Pieces Per Pan for each pan or box.',
        '**_Production** on DSD_DSnD (packs) or Dist_DSnD (F5 cases) for the K4 day.',
    ],
    'formulas': [
        f"**Row list (A410)** {X('Mix-Slice-Oven!A410')}",
        f"**# of Pans/Boxes to set out (P)** {T('Oven_Info', '# of Pans/Boxes to set out')}",
        f"**MCS Schedule F29** {X('MCS Schedule!F29')}",
    ],
    'example': [
        '**3.5" Challah Onion Bun pan, Tuesday**: F3082 (MCS LINE) is short 55 packs x 12 pieces = 660 pieces.',
        '**Pans**: 660 / 28 pieces per pan = 23.6, ROUNDUP = 24. MCS Schedule F29 lists it: 24.',
        '**(Grande) Large Croissant**: F8006 76 x 1 = 76 pieces / 10 = 7.6, so 8 pans. It is 3rd Party - Bake, so F29 skips it.',
    ],
    'questions': [
        'Should the Breadline Schedule and 3rd Party - Bake products get their own pan list?',
        'Should F29 check every product on a pan instead of only the first one under it?',
        'Should the print area be widened to include rows 453 to 477?',
    ],
})

# ------------------------------------------------------------------ 8
MCS_A5, BL_A5 = X('MCS Schedule!A5'), X('Breadline Schedule!A5')
F_KEEP = part(MCS_A5, 'keep,FILTER(ud,(pt>0)*(ud<>"")*(as="MCS LINE"),"")')
F_SORT = part(MCS_A5, 'p,IF(x="",9999,IFERROR(--x,9999))')
F_MIX = part(MCS_A5, 'k,IF(bpm>0,ROUNDUP(tot/bpm,0),1)')
F_ROWS = part(MCS_A5, 'cum,SCAN(0,k,LAMBDA(a,v,a+v)),r,SEQUENCE(n),idx,MAP(r,LAMBDA(v,XMATCH(v,cum,1)))')
F_CO = part(MCS_A5, 'co_ord,MAP(ci,LAMBDA(v,IF(v=0,0,IFERROR(--INDEX(upl,v-1),0)+0.5)))')
F_OK = part(MCS_A5, 'okco,(co_ord>MIN(ord))*(co_ord<MAX(ord))')
F_SETS = part(BL_A5, 'sets,IF(mu="",0,ROUNDUP(mt/(pb+rb),0))')
SPECS.append({
    'section': 8,
    'title': '8. MCS and Breadline schedules: Logic Spec',
    'subtitle': 'How the A5 formula turns Planned Total into one printed row per mix, in placement order.',
    'mermaid': FLOWS[8],
    'inputs': [
        '**Mix_Slice**: Unique Dough, Asset and Planned Total.',
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

# ------------------------------------------------------------------ 9
SPECS.append({
    'section': 9,
    'title': '9. Recon: Logic Spec',
    'subtitle': 'Each row of the Recon table compares a spilled row list with the table beside it.',
    'mermaid': FLOWS[9],
    'inputs': [
        '**Sheet** and **Adjacent Table**: typed labels in the Recon table.',
        '**Spilled row lists**: Sunday to Friday A3, Daily Supply & Demand A8 and A287, DoughWeights A4, Mix-Slice-Oven A6 and A410.',
        '**Adjacent tables**: Sunday to Friday, DSD_DSnD, Dist_DSnD, DoughWeight, Mix_Slice, Oven_Info.',
    ],
    'formulas': [
        f"**Array Cell** {RECON_F['Array Cell']}",
        f"**Array Rows** {RECON_F['Array Rows']} (Sunday row; each row names its own spill)",
        f"**Table Rows** {RECON_F['Table Rows']} (Sunday row; each row names its own table)",
        f"**Difference (Array − Table)** {RECON_F['Difference (Array − Table)']}",
        f"**Status** {RECON_F['Status']}",
        f"**As stored in the file** (A1 style, same result): Array Cell {X('Recon!B5')}; Difference {X('Recon!F5')}; Status {X('Recon!G5')}",
    ],
    'example': [
        '**DoughWeight**: Array Rows 453 (DoughWeights A4#), Table Rows 452, Difference 1, Status Array longer: the last SKU, F2562, gets no formulas.',
        '**Wednesday**: Array Rows 395, Table Rows 447, Difference -52, Status Table longer: 52 rows of N/A under the list.',
        '**Mix_Slice**: Array Rows 390, Table Rows 391, Difference -1, Status Table longer.',
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
