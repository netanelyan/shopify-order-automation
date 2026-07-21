# Orders Processor

Turns a Shopify order export into a formatted `.docx` order sheet for a manufacturer.

Built for a Hebrew-language store selling football kits. Each order becomes one
page listing the shipping details, the price, and every item broken down into
edition, kit, size, player name, number and patch — translating the Hebrew
product titles into English on the way through. Bold is written as
`*asterisks*` because the finished document is sent over WhatsApp.

**Pricing, promo codes and the product catalogue are supplied via config and are
not in this repository.** Copy the two `.example.json` files to get a working
setup with placeholder values — see [Config](#config).

---

## Windows — how to run

Put the CSV export in the same folder as these files.

Shift + right-click that folder → **Open PowerShell window here**.

**One time only**, install the dependencies:

```powershell
pip install pandas
npm install docx
```

**Every time**, run these two lines — replace `orders.csv` with your file name:

```powershell
python parse_orders.py orders.csv -o test.json
node build_docx.js test.json test.docx
```

`test.docx` appears in the same folder. Done.

To process several exports at once, list them all:

```powershell
python parse_orders.py file1.csv file2.csv -o test.json
node build_docx.js test.json test.docx
```

If Hebrew shows as `?` in the console, run this once first — the docx is
unaffected either way:

```powershell
$env:PYTHONIOENCODING="utf-8"
```

---

## Mac / Linux

```bash
pip install pandas
npm install docx
chmod +x run.sh

./run.sh orders.csv output.docx
```

`run.sh` is bash only — on Windows use the PowerShell steps above, or Git Bash.

---

## Config

Create the two config files before the first run:

```bash
cp config.example.json config.json
cp translations.example.json translations.json
```

Both are gitignored, so commercial terms never reach the repository.

### `config.json`

Per-item rates and the rules for which lines to skip. See
`config.example.json` for the shape.

### `translations.json`

The Hebrew → English product catalogue. See `translations.example.json` for
the shape.

Anything the catalogue does not cover is passed through untranslated and
flagged `⚠ CHECK:` rather than silently guessed, so an incomplete catalogue
degrades visibly instead of producing a wrong order.

---

Both example files ship placeholder values only. The real rates and catalogue
are not part of this repository.

---

## Input

Export **Orders** from Matrixify with these groups ticked:

- General
- Line Type
- Customers
- Line Items

Filter: Fulfillment status = unfulfilled

> Must be a **Matrixify** export, which names columns with a colon
> (`Shipping: Name`, `Line: Name`). Shopify's own built-in order export uses
> `Shipping Name` / `Billing Address1` and will not parse.

---

## What to check after a run

After parsing, check the console for:

- `📝 order(s) have a note` — an instruction that can change what the supplier
  must print. Notes are in Hebrew and are not translated; read each one before
  sending.

  This reads the order **Notes** field only. Comments posted in the order
  **Timeline** are a separate thing in Shopify and are not exported at all, so
  they will never appear here — write anything the supplier needs in the Notes
  field on the right-hand side of the order, not in the Timeline.
- `⚠ Items flagged for manual review` — a product title the catalogue could not
  translate. These also appear as `⚠ CHECK:` in the docx.

---

## Adding a translation

Open `translations.json` and add to `kits` (longest match wins):

```json
"עברית": "English"
```

For player names, open `name_normalizer.py`:

```python
'nickname': 'Correct Name',
```
