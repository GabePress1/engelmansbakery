# FPi 700 folding spec — past-due letter + statement mailer

**Purpose.** This is the reference for anyone changing the n8n workflow that generates the
past-due mailing PDFs. It describes what the FPi 700 does to a sheet of paper, and what the
generated PDF must therefore look like.

**Status of the numbers in this document.** Every figure is tagged with where it came from:

| Tag | Meaning |
|---|---|
| **[VENDOR]** | Published FP Mailing / Francotyp-Postalia spec sheet |
| **[MEASURED]** | Extracted from a real production PDF (`PastDueShipping20260813_1.pdf`, 76 pages, 19 customers, 2026-08-13) |
| **[STANDARD]** | Industry-standard envelope/paper geometry, not machine-specific |
| **[CALIBRATE]** | **Not verified. Must be measured on the actual machine before relying on it.** |

Do not promote a **[CALIBRATE]** item to a constant in code without doing the calibration in
§8 first. The official FPi 700 operator manual could not be retrieved when this document was
written (`download.fp-usa.com`, `download.francotyp.ca`, and `www.loffler.com` are blocked by
network egress policy), so several fold details that would normally be published values are
calibration steps here instead.

---

## 1. What the FPi 700 is

The **FPi 700** is a desktop **folder-inserter** made by **FP Mailing Solutions /
Francotyp-Postalia**. Despite the "FPi" model naming it is *not* a Neopost, Quadient, Hasler,
or Frama machine — do not use their manuals as a substitute reference. (FP and Neopost did
share platforms on much older *FPi 2000*-era models; that lineage does not extend to this one.)

It is not merely a folder. In one pass it:

1. **Feeds** a sheet from one of its document feeders (2 feeders, 100 sheets each, linkable
   to 200) **[VENDOR]**
2. **Accumulates** the fixed number of sheets that make up one customer's set
3. **Folds** the accumulated set on adjustable fold plates
4. **Inserts** the folded set into an envelope from the envelope hopper
5. **Seals** the envelope and stacks it

It also runs **fold-only** jobs (fold, no envelope) **[VENDOR]**, which is how you produce a
test fold during calibration without wasting envelopes.

**What the operator sets per job**, on the touchscreen: fold type, fold-plate stop positions
(fold lengths are adjustable, not fixed to thirds), sheets-per-set, envelope presence, and
sealing on/off. Jobs can be saved to memory and recalled.

**The critical consequence for the PDF:** the machine has **no idea where one customer's
document ends and the next begins.** It counts sheets. Everything in §4 follows from this.

---

## 2. Confirmed machine limits

| Spec | Value | Source | Bearing on our PDF |
|---|---|---|---|
| Letter-fold (C-fold) capacity | **3 sheets** @ 20 lb | [VENDOR] | Our 2-sheet set is inside the limit |
| Half-fold capacity | 5 sheets | [VENDOR] | n/a — we letter-fold |
| Document size | 3.5"–14" long × 5.6"–8.9" wide | [VENDOR] | US Letter 8.5×11 fits |
| Paper weight | 60–120 gsm (16–32 lb bond) | [VENDOR] | Standard copier stock is fine |
| Envelope size | 4.1"–6.4" high × 9.0"–9.5" wide | [VENDOR] | **#10 (4.125×9.5) fits. DL does NOT** — its 8.66" width is below the 9.0" minimum |
| Fold types | 4 standard, plates adjustable via touchscreen | [VENDOR] | Custom fold lengths are available if thirds don't work |
| Throughput | ~1,350 pieces/hour | [VENDOR] | — |

### Not verified — treat as calibration inputs

- **Fold-plate offsets.** Real inserters set the first-folded panel **1–3 mm shorter** than the
  others so the panels nest instead of the leading edge catching the envelope throat. The FPi
  700's factory default offsets are not documented in any source reachable from here.
  **[CALIBRATE]**
- **Feed orientation (face-up vs face-down).** This determines *which panel of the sheet ends
  up facing outward*, and therefore which panel the address must be printed on. **[CALIBRATE]**
- **OMR / barcode reading.** Not confirmed as available on this model, and the operator reports
  the machine does not have it. This spec assumes **no OMR**. If a reading option is ever
  added, §4 can be relaxed. **[CALIBRATE]**

---

## 3. The mail piece

One customer = **2 sheets**, printed **duplex**, letter-folded (C-fold), inserted into a **#10
window envelope**.

Page order per customer:

| Page | Sheet / face | Content |
|---|---|---|
| 1 | Sheet 1 front | Past-due letter (logo, subject, body, signoff) **+ mailing address in the window band** |
| 2 | Sheet 1 back | Blank |
| 3 | Sheet 2 front | Statement — "Past Due Invoices" table |
| 4 | Sheet 2 back | Blank filler, or statement page 2 |

Every set is exactly 4 pages / 2 sheets — see §4, which is what guarantees it.

### Why the address is on the front

Only one face of the folded piece shows through the envelope window. The original layout put
the address alone on **page 2 — the back of sheet 1** — which delivers a visible address only if
the machine folds reverse-side-out, an assumption nobody had confirmed.

The address now prints at the foot of page 1, alongside the letter, in the window band defined
in §6. This is the standard business-letter arrangement and it removes the dependency on feed
orientation: the front is the face the standard fold presents. It also reclaims a sheet face —
the back of sheet 1 was being spent on four lines of type and is now genuinely blank.

The letter body ends around **y=425** **[MEASURED]**, entirely in the middle and top panels, so
it clears the window band by roughly 340 pt. A regression test asserts that nothing but the
address ever prints inside the band.

**Still a calibration item:** this settles which *face* carries the address, not which *panel*
faces the window. §8 resolves the panel question.

---

## 4. The hard invariant: exactly 2 sheets per customer

**Every customer's set must be exactly 4 pages / 2 sheets. No exceptions.**

Because the machine has no OMR, it separates customers by **counting a fixed number of sheets
per set**. If one customer emits 3 sheets, the machine still takes 2 — and from that point on
*every subsequent envelope contains the wrong customer's paperwork*. This fails silently and
is not detectable until the mail is opened.

### The defect this replaced

`customerPages()` padded the letter block to 2 pages and the statement block to an **even**
page count. Even is not the same as **fixed**:

| Statement pages | Padded to | Total set | Sheets | Result |
|---|---|---|---|---|
| 1 | 2 | 4 | 2 | ✅ correct |
| 2 | 2 | 4 | 2 | ✅ correct |
| **3** | **4** | **6** | **3** | ❌ **desynchronized the entire remaining run** |

The 2026-08-13 run happened to be safe because no statement exceeded 2 pages **[MEASURED]** —
luck, not a guarantee. A customer with enough open invoices would have tripped it.

### How it is enforced now

Three layers in `original/pure-pdf.js`, against `SET_PAGES = 4`:

1. **Condense.** `fitStatementPages()` renders the statement and, if it overflows one sheet,
   collapses the oldest detail lines into a single **"Balance Forward"** row — `documentNo`
   reads "N earlier invoices" and carries their summed amount. Because lines arrive oldest-first
   and `statement.total` is untouched, the printed rows still sum to the total. Page count is
   monotonic in the number of lines kept, so it binary-searches the largest number that fits
   rather than re-rendering once per line. In practice **66 detail lines fit before
   condensation starts** — far beyond anything in the sample data, so this is a safety net
   rather than a routine path.
2. **Divert.** If even a fully condensed statement will not fit, `customerPages()` returns
   `null` and `buildBatchPdf()` leaves that customer out of the machine run, pushing
   `{ name, reason }` onto the optional `opts.excluded` sink. The n8n render node passes a sink
   and returns the names on its output item, so the operator knows who to stuff by hand.
   **A third sheet is never emitted.**
3. **Assert.** `buildBatchPdf()` throws unless total pages equal `4 × included customers` —
   failing the run is strictly better than printing mail that goes to the wrong people.

The compact on-screen copy (`pad: false`) is exempt from all of this: it is read in a browser,
never folded, so it runs to full length uncondensed.

---

## 5. Page geometry and the fold

The PDF writer uses **US Letter, 612 × 792 pt, origin at bottom-left** (1 pt = 1/72") — all
MediaBoxes in the sample run were `0 0 612 792` **[MEASURED]**. All coordinates below are in
that system.

### C-fold panel bands (nominal thirds)

```
  y = 792 ┌─────────────────────────────┐
          │                             │
          │   PANEL C  (top third)      │   528 – 792 pt   7.333" – 11.000"
          │                             │
  y = 528 ├ ─ ─ ─ ─ fold crease ─ ─ ─ ─ ┤
          │                             │
          │   PANEL B  (middle third)   │   264 – 528 pt   3.667" – 7.333"
          │                             │
  y = 264 ├ ─ ─ ─ ─ fold crease ─ ─ ─ ─ ┤
          │                             │
          │   PANEL A  (bottom third)   │     0 – 264 pt   0.000" – 3.667"
          │                             │
  y =   0 └─────────────────────────────┘
```

Each panel is 612 × 264 pt (8.5" × 3.667"). The bands sum to 792 pt.

**These are nominal.** The machine's actual creases will land 1–3 mm off these lines because
of the nesting offset **[CALIBRATE]**. Design for that:

- **Crease gutter — keep a ±9 pt (⅛") clear band either side of y=264 and y=528.** No text,
  no rules, no logo edges. A crease through a line of type is the most visible defect on the
  finished piece.
- **Feed-edge keep-out — 18 pt (¼") at the top and bottom edges of the sheet.** The feed and
  fold rollers grip here. Heavy ink coverage in this band can smear or slip.

### Which panel faces the window

**Unknown until calibrated.** **[CALIBRATE]** The existing address block sits at y=105–150 pt,
which is inside Panel A, so the original author evidently intended the **bottom panel** to be
the outward-facing one. Confirm this in §8 before moving anything — if the machine actually
presents Panel C, the whole block moves up 528 pt rather than down.

---

## 6. Address block placement

### The #10 window aperture **[STANDARD]**

A standard #10 window envelope is 4.125" × 9.5" with a 1⅛" × 4½" window inset ⅞" from the
left edge and ½" from the bottom edge:

```
   ┌───────────────────────────────────────────────────┐  4.125" (297 pt)
   │                                                   │
   │      ┌───────────────────────────────┐            │
   │      │        window aperture        │ 1.125"     │
   │      └───────────────────────────────┘            │
   │  0.875"          4.5"                    0.5"     │
   └───────────────────────────────────────────────────┘
                     9.5" (684 pt)
```

Verify against the envelope stock actually in use — window position varies by manufacturer.

### The piece floats inside the envelope — this is what tightens the target

The folded piece is 8.5" × 3.667" inside a 4.125" × 9.5" envelope, so it can shift:

- **Vertically: 0.458"** of slack (4.125 − 3.667)
- **Horizontally: 1.0"** of slack (9.5 − 8.5)

Designing for "the piece resting on the bottom of the envelope" is not enough. The address
must remain fully visible across the **entire range of travel**. Intersecting the two extreme
positions gives the real safe zone, measured **from the bottom-left corner of the
window-facing panel**:

| Axis | Safe range | Derivation |
|---|---|---|
| **Vertical** | **y 36 – 84 pt** (0.5" – 1.167") | lower bound = window bottom; upper bound = window top − vertical slack (1.625" − 0.458") |
| **Horizontal** | **x 63 – 315 pt** (0.875" – 4.375") | left = window left; right = window right − horizontal slack (5.375" − 1.0") |

That is a usable band **48 pt tall** and **252 pt wide**.

### The defect this replaced, and the fix

Before this spec existed the address was drawn at **x = 72 pt** with baselines at
**y = 150 / 135 / 120** (3-line) or **150 / 135 / 120 / 105** (4-line) **[MEASURED]** —
spanning 1.46"–2.08" above the page bottom, roughly half an inch too high. **Zero of three
baselines** fell inside the safe band for a 3-line address; one of four for a 4-line address.
Horizontally it was fine: x=72 pt is inside the 63–315 pt range, and the widest address line in
the sample run measured **165.3 pt** ("Sterling Estates-WEST COBB TTHS") against a 243 pt
budget, with zero of 61 lines over **[MEASURED]**.

`letterPages()` in `original/pure-pdf.js` now positions the block against
`WINDOW_Y_MIN` / `WINDOW_Y_MAX` / `WINDOW_X_MAX` rather than a hardcoded start:

- **Centered in the band**, so 3- and 4-line addresses both clear the aperture with margin
  instead of one of them hanging off an edge.
- **10 pt type on 12 pt leading.** Four lines at the old 15 pt leading spanned 45 pt of
  baselines plus ascender and descender — essentially the whole 48 pt band, with nothing left
  for fold variance.
- **Auto-shrink on width.** If any line would pass the window's right edge as the piece slides,
  the block steps down in half-points to a floor of 7 pt.

Verified by rendering: a 3-line address occupies ink y 43.3–76.8, a 4-line address y 37.3–82.8,
and a deliberately over-long name shrinks to 8 pt at y 38.2–81.8 — all inside the 36–84 pt band.

### Clear-zone rule

Nothing but the address may be printed inside the window band — no logo, no rule lines, no
page furniture, across the **full width** of the panel (the piece slides sideways, so
something outside the window band at rest can slide into view). This matters more now that the
address shares page 1 with the letter: the letterhead sits at y≈686–720 pt and the body ends
around y=425 **[MEASURED]**, both well clear, and a regression test enforces it by walking every
text operation on page 1 and failing if a non-address glyph lands in the band.

---

## 7. Address data quality

Folding is irrelevant if the address is undeliverable. The 2026-08-13 run had two real defects
**[MEASURED]**:

- **No state on any record.** Lines read `Atlanta 30318`, not `Atlanta, GA 30318`.
  `transform.js` maps Business Central's `County` field to State, and `County` is empty across
  the entire customer list. Ship-to records are worse: they carry **no state field at all**.
- **Two of nineteen records had a literal `-`** as their entire city/state/ZIP line (Five Star
  Culinary, Friends Table Restaurant PTC TTHS). Those envelopes had no destination.

### How it is handled now

Because `County` is empty and ship-tos have no state field, there is nowhere to map a state
*from* — so `pure-pdf.js` derives it from the ZIP:

- **`clean()`** treats placeholder junk as empty — `-`, `--`, `.`, `N/A`, `none`, `null`,
  `unknown`, `TBD` and similar. A dash is not an address and must never reach an envelope.
- **`stateFromZip()`** maps the ZIP to its USPS state using the 3-digit prefix allocations
  (including territories and the AA/AE/AP military codes). `cityStateZip()` uses an explicit
  state when present and falls back to the derived one, so all 17 deliverable records in the
  sample run now print `Atlanta, GA 30318`. This fixes shipping addresses too, which never had
  a state field to begin with.
- **`addressProblem()`** returns why a piece cannot be delivered, or `null`. It requires an
  addressee and a street line, plus **either a ZIP or a city+state**. USPS routes on the ZIP,
  so a missing state is a formatting defect rather than a delivery blocker — deliberately, since
  requiring a state before the derivation above would have suppressed the entire mailing.
- **`buildBatchPdf()` pulls failing records from the run** and reports them on the same
  `opts.excluded` sink as the set-length overflow (§4), so the operator gets names and reasons
  rather than silently mailed-blind envelopes. On the sample data: 17 of 19 mail, 2 are pulled
  as `missing ZIP and city/state`.

`normAddr()` uses the same cleaning and derivation, so a ship-to is no longer treated as a
different address purely because one side lacks a state or holds a placeholder.

**Still worth fixing at the source:** the derivation is a repair, not a substitute for real
data. Populating `County` (or whichever field Business Central actually holds state in) and
filling in the two blank customer addresses removes the guesswork.

---

## 8. Calibration procedure

This is the authority for every **[CALIBRATE]** item. It takes about ten minutes and replaces
the manual we could not obtain.

1. Print one duplex set on the production stock.
2. On the FPi 700, select the letter-fold job and run it in **fold-only** mode.
3. On the folded piece, note **which printed face is on the outside** and **which panel it is**
   (find the logo or the letter body to orient yourself). This resolves the feed-orientation
   and which-panel questions.
4. Unfold the sheet and measure the actual crease positions from the bottom edge. These are the
   real panel bands — record them; they will differ from 264/528 pt by 1–3 mm.
5. Insert the folded piece into a real #10 envelope from the production stock.
6. **Push the piece fully down and to the left**, and mark the window rectangle on the paper
   with a pencil. Then **push it fully up and to the right** and mark it again.
7. The **overlap of the two marked rectangles** is the true safe zone. Measure it from the
   panel's bottom-left corner and convert to points (×72 per inch).
8. Replace the §6 figures with the measured values, and re-run the physical test in §10.

---

## 9. Where the code lives

> **The working copy of this repo is nearly empty.** All the real code is on branch
> **`claude/business-central-mail-merge-e8m5hk`**. Fetch it before editing, or you will create
> new files instead of modifying the existing ones.

| File | Role |
|---|---|
| `original/pure-pdf.js` | **Mailing path.** `letterPages()` draws the letter and the window address block on one page; `customerPages()` fits the statement and pads the set to two sheets. This is where fold work happens. |
| `scripts/pure-pdf.js` | **Delivery path** — statement-only twin. Keep in lockstep for any shared layout change. |
| `original/transform.js` | Address token mapping, including the `County` → State issue in §7. |
| `n8n/build-workflow.js`, `original/build-workflow.js` | Generate the workflow JSON. |
| `test/validate-workflow.js` | Re-executes the *inlined* Code-node source to catch drift. |

**The n8n workflow JSON is generated, not hand-written.** `build-workflow.js` inlines
`pure-pdf.js` as the source of the `Render & Merge PDFs` Code node. Editing the JSON directly
will be overwritten on the next build. Edit the script, then regenerate both workflows and run
`npm test`.

The PDF writer emits raw PDF 1.4 with base-14 fonts and no dependencies, so it can run inside
an n8n **Cloud** Code node. Keep it that way — do not introduce PDFKit, pdf-lib, or puppeteer.

---

## 10. Verification

Layout changes cannot be signed off from a PDF viewer alone. The test is physical:

1. **Assert the invariant.** Total pages must equal `4 × customer count`. Fail the run otherwise.
2. **Print one duplex set** on production stock.
3. **Fold it on the FPi 700** at the production job's settings.
4. **Insert into a real #10 envelope** and confirm the address is fully inside the window with
   clear margin on all four sides — **including with the piece pushed to the top of its travel
   and to each side**, not just at rest.
5. **Check the creases** fall in empty space on both sheets, with no type clipped.
6. **Run a 10-customer batch** end to end and open every envelope. Each must contain exactly
   one customer's two sheets, letter and statement matching the same account.

Step 6 is the one that catches set-desynchronization, and it is the failure mode with the
worst consequences — another customer's balance disclosed to the wrong recipient. Do not skip it.
