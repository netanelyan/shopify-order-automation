"""
parse_orders.py
---------------
Reads one or more Shopify Matrixify CSV exports and produces a JSON file
ready for build_docx.js

Usage:
    python parse_orders.py input1.csv [input2.csv ...] -o output.json
"""

import pandas as pd
import re
import io
import json
import argparse
from pathlib import Path
from name_normalizer import normalize_name

# ── Configuration ────────────────────────────────────────────────────────────
# Pricing, skip rules and translations live in JSON so they can be changed
# without touching code — and so this repo can be shared without disclosing
# commercial terms. Copy the .example files and fill in your own values.

BASE_DIR = Path(__file__).resolve().parent


def load_config(path, example):
    """Load a JSON config, pointing at the .example file if it is missing."""
    p = BASE_DIR / path
    if not p.exists():
        raise SystemExit(
            f'Missing {path}.\n'
            f'Copy {example} to {path} and fill in your own values:\n'
            f'    cp {example} {path}'
        )
    with io.open(p, encoding='utf-8') as f:
        return json.load(f)


CONFIG       = load_config('config.json',       'config.example.json')
_TR          = load_config('translations.json', 'translations.example.json')

TRANSLATIONS = _TR['kits']
PATCH_MAP    = _TR['patches']

PRICING       = CONFIG['pricing']
MYSTERY_SKIP  = set(CONFIG['skip']['order_numbers'])
SKIP_PREFIXES = CONFIG['skip']['line_prefixes']
SKIP_CONTAINS = CONFIG['skip']['line_contains']

# ── Helpers ──────────────────────────────────────────────────────────────────

def translate(s):
    for heb, eng in sorted(TRANSLATIONS.items(), key=lambda x: -len(x[0])):
        s = s.replace(heb, eng)
    return s.strip()


def translate_patch(p):
    if not p:
        return None
    return PATCH_MAP.get(p, p)


def should_skip(name):
    # Open question: 'פאטץ' and 'שם ומספר' also exist as standalone Shopify
    # products. Bought as their own line item they are counted here as kits,
    # inflating the item count (and possibly tripping the bulk tier) on top of
    # the personalisation surcharge. Adding them to skip.line_prefixes would
    # fix that but changes prices, so it was left alone deliberately.
    if pd.isna(name):
        return True
    n = str(name)
    for prefix in SKIP_PREFIXES:
        if n.startswith(prefix):
            return True
    for needle in SKIP_CONTAINS:
        if needle in n:
            return True
    return False


def parse_name_number(prop):
    if pd.isna(prop) or str(prop) == 'nan':
        return None, None
    match = re.search(r'שם ומספר:\s*(.+)', str(prop))
    if not match:
        return None, None
    raw = match.group(1).strip()
    m = re.match(r'^(\d+)\s*(.+)$', raw)
    if m:
        return normalize_name(m.group(2).strip()), m.group(1)
    m = re.match(r'^(.+?)\s*(\d+)$', raw)
    if m:
        return normalize_name(m.group(1).strip()), m.group(2)
    return normalize_name(raw), None


def parse_note(row):
    """Shopify keeps one 'Note' field per order — the customer's checkout note
    lands there and staff edits overwrite the same field, so this covers both.
    Older exports may not include the column at all."""
    try:
        note = row['Note']
    except (KeyError, IndexError):
        return None
    if pd.isna(note):
        return None
    note = ' / '.join(l.strip() for l in str(note).splitlines() if l.strip())
    return note or None


def parse_patch(prop):
    if pd.isna(prop) or str(prop) == 'nan':
        return None
    match = re.search(r'פאטץ[\':]?\s*(.+)', str(prop))
    if match:
        return match.group(1).strip().split('\n')[0].strip()
    return None


def parse_item(line_name, prop):
    s = str(line_name)
    parts = [p.strip() for p in s.split('|')]
    raw_kit = parts[0].strip()
    year    = parts[1].strip() if len(parts) > 1 else ''
    rest    = parts[2].strip() if len(parts) > 2 else ''

    # Two-segment titles ('ארגנטינה | בעלי חיים - L') carry the size on the
    # year slot, so move it to rest where the size parsing below expects it.
    if not rest and ' - ' in year:
        year, rest = year.split(' - ', 1)
        year, rest = year.strip(), rest.strip()

    is_special = any(x in s for x in ['מהדורה מיוחדת', 'מהודרה מיוחדת', 'מהדורה מוגבלת'])
    hoa_en = ''
    size   = ''
    collab = ''

    if is_special:
        if ' - ' in rest:
            collab_raw, size = rest.split(' - ', 1)
            collab = translate(collab_raw.strip())
            size   = size.split('/')[0].strip()
        else:
            size = rest
    else:
        if ' - ' in rest:
            hoa_part, size_rest = rest.split(' - ', 1)
            hoa_heb = hoa_part.strip()
            size    = size_rest.split('/')[0].strip()
            # Longest / most specific variants first — 'בית-ילדים' contains 'בית'
            if   'בית-ילדים'   in hoa_heb: hoa_en = 'home kids'
            elif 'חוץ-ילדים'   in hoa_heb: hoa_en = 'away kids'
            elif 'שוער-ילדים'  in hoa_heb: hoa_en = 'goalkeeper kids'
            elif 'חוץ אירופית' in hoa_heb: hoa_en = 'european away'
            elif 'בית'         in hoa_heb: hoa_en = 'home'
            elif 'חוץ'         in hoa_heb: hoa_en = 'away'
            elif 'שלישית'      in hoa_heb: hoa_en = 'third'
            elif 'רביעית'      in hoa_heb: hoa_en = 'fourth'
            elif 'חמישית'      in hoa_heb: hoa_en = 'fifth'
            elif 'שוער'        in hoa_heb: hoa_en = 'goalkeeper'
            elif 'גביע'        in hoa_heb: hoa_en = 'cup'
            elif 'ילדים'       in hoa_heb: hoa_en = 'kids'
            elif 'תינוקות'     in hoa_heb: hoa_en = 'baby'
            else: hoa_en = translate(hoa_heb)
        elif rest:
            size = rest

    kit_en   = translate(raw_kit)
    # The year slot is not always a year — it also carries collabs ('בעלי חיים'),
    # brands ('נייק') and garment types ('שורט'), so it needs translating too.
    year_en  = translate(year)
    kit_full = f"{kit_en} {year_en}".strip() if year_en else kit_en
    if is_special and collab:
        kit_full += f' ({collab})'
    for heb, eng in [
        ('מהדורה מיוחדת', 'special edition'),
        ('מהודרה מיוחדת', 'special edition'),
        ('מהדורה מוגבלת', 'limited edition'),
    ]:
        kit_full = kit_full.replace(heb, eng)

    is_player      = 'שחקן'       in s
    is_long_sleeve = 'שרוול ארוך'  in s
    is_kids        = 'ילדים'       in s or 'תינוקות' in s
    has_pants      = 'עם מכנס'    in s

    year_match   = re.search(r'\b(19\d{2}|200\d|201\d)\b', year)
    season_match = re.search(r'(\d{2})/(\d{2})', year)
    is_retro = False
    if year_match:
        is_retro = True
    elif season_match:
        y = int(season_match.group(1))
        full_year = 2000 + y if y < 50 else 1900 + y
        is_retro  = full_year < 2020

    if   is_special: edition = 'fan edition'
    elif is_player:  edition = 'player edition'
    elif is_retro:   edition = 'retro edition'
    else:            edition = 'fan edition'

    if   is_long_sleeve:        price_type = 'long_sleeve'
    elif is_kids:               price_type = 'kids'
    elif is_player or is_retro: price_type = 'player_retro'
    else:                       price_type = 'fan'

    player_name, number = parse_name_number(prop)
    patch      = translate_patch(parse_patch(prop))
    has_hebrew = bool(re.search(r'[\u0590-\u05FF]', kit_full + hoa_en))
    kit_display = f"{kit_full} {hoa_en}".strip() if hoa_en else kit_full

    return {
        'kit':         kit_display,
        'size':        size,
        'edition':     edition,
        'price_type':  price_type,
        'name':        player_name,
        'number':      number,
        'patch':       patch,
        'long_sleeve': is_long_sleeve,
        'has_pants':   has_pants,
        'unclear':     has_hebrew,
        'raw':         s,
    }


def calc_price(items):
    bulk = len(items) >= PRICING['bulk_threshold']
    tier = 'bulk' if bulk else 'standard'
    sur  = PRICING['surcharges']
    total = 0
    for item in items:
        rates = PRICING['base'].get(item['price_type'], PRICING['default'])
        price = rates[tier]
        if item['long_sleeve']:
            price += sur['long_sleeve']
        if item.get('name') or item.get('number') or item.get('patch'):
            price += sur['personalisation']
        if item['has_pants']:
            price += sur['pants']
        total += price
    return total


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description='Parse Shopify Matrixify CSV exports into order JSON'
    )
    parser.add_argument('csvfiles', nargs='+', help='One or more CSV files to process')
    parser.add_argument('-o', '--output', default='orders.json', help='Output JSON path')
    args = parser.parse_args()

    all_orders      = []
    mystery_skipped = []
    seen_orders     = set()

    for fname in args.csvfiles:
        df = pd.read_csv(fname)
        print(f'{fname}: {df["Name"].nunique()} orders')

        order_rows     = {}
        order_sequence = []
        for _, row in df.iterrows():
            name = row['Name']
            if name not in order_rows:
                order_rows[name] = []
                order_sequence.append(name)
            order_rows[name].append(row)

        for order_name in order_sequence:
            if order_name in MYSTERY_SKIP:
                continue
            if order_name in seen_orders:
                continue
            seen_orders.add(order_name)

            rows  = order_rows[order_name]
            first = rows[0]
            phone = str(first['Shipping: Phone']) if pd.notna(first['Shipping: Phone']) else ''
            phone = phone.lstrip("'")

            items_display = []
            items_pricing = []

            for row in rows:
                if pd.isna(row['Line: Name']):
                    continue
                if any(x in str(row['Line: Name']) for x in SKIP_CONTAINS):
                    mystery_skipped.append(order_name)
                    continue
                if should_skip(row['Line: Name']):
                    continue

                qty = 1
                try:
                    qty = int(float(row['Line: Quantity']))
                except Exception:
                    pass

                parsed       = parse_item(row['Line: Name'], row['Line: Properties'])
                display_item = dict(parsed)
                display_item['qty'] = qty
                items_display.append(display_item)
                for _ in range(qty):
                    items_pricing.append(dict(parsed))

            if not items_display:
                continue

            # A note can be set on any row of the order; take the first non-empty
            note = next((n for n in (parse_note(r) for r in rows) if n), None)

            all_orders.append({
                'order':         order_name,
                'note':          note,
                'shipping_name': str(first['Shipping: Name'])      if pd.notna(first['Shipping: Name'])      else '',
                'address':       str(first['Shipping: Address 1'])  if pd.notna(first['Shipping: Address 1'])  else '',
                'city':          str(first['Shipping: City'])       if pd.notna(first['Shipping: City'])       else '',
                'phone':         phone,
                'email':         str(first['Customer: Email'])     if pd.notna(first['Customer: Email'])     else '',
                'price':         calc_price(items_pricing),
                'items':         items_display,
            })

    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(all_orders, f, ensure_ascii=False, indent=2)

    print(f'\n✓ {len(all_orders)} orders written to {args.output}')

    if mystery_skipped:
        print(f'✗ Mystery box orders skipped: {sorted(set(mystery_skipped))}')

    noted = [o for o in all_orders if o.get('note')]
    if noted:
        print(f'\n📝 {len(noted)} order(s) have a note — read before sending:')
        for o in noted:
            print(f'   {o["order"]}: {o["note"]}')

    unclear = [
        (o['order'], item['raw'])
        for o in all_orders
        for item in o['items']
        if item['unclear']
    ]
    if unclear:
        print('\n⚠  Items flagged for manual review (untranslated Hebrew):')
        for order_name, raw in unclear:
            print(f'   {order_name}: {raw[:70]}')
    else:
        print('✓ No unclear items')


if __name__ == '__main__':
    main()
