#!/usr/bin/env python3
"""
parse_codebook.py

Parse the BRFSS USCODE HTML codebook to extract value -> label mappings for
the `_STATE` (State FIPS) table and the Age-group table(s). Writes CSVs to
`2433_p3_data/healthcare.gov/exports/codebook_tables/` and prints a brief
summary.

Usage:
    python scripts/parse_codebook.py
    python scripts/parse_codebook.py --html path/to/USCODE24_LLCP_082125.HTML

Notes:
 - The script tries to be robust to variations in the HTML layout. It looks
   for tables whose headers contain 'Value' and 'Value Label', and then
   inspects nearby preceding text to infer the variable name (e.g. `_STATE`)
   or an age-related label.
 - If BeautifulSoup4 is not available this script will prompt to install
   it (or you can install via `pip install beautifulsoup4`).
"""
from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path
import re
import sys
from typing import Dict, List, Optional, Tuple

try:
    from bs4 import BeautifulSoup
except Exception:
    BeautifulSoup = None  # type: ignore


def find_candidate_tables(soup):
    """Return all <table> tags whose header contains 'Value' and 'Value Label'."""
    candidates = []
    for tbl in soup.find_all('table'):
        # Extract header text from th or first tr
        header_text = ''
        ths = tbl.find_all('th')
        if ths:
            header_text = ' '.join(t.get_text(separator=' ').strip() for t in ths)
        else:
            # maybe the first row is header
            first_row = tbl.find('tr')
            if first_row:
                header_text = ' '.join(td.get_text(separator=' ').strip() for td in first_row.find_all(['td','th']))
        ht = header_text.lower()
        if 'value' in ht and ('value label' in ht or 'value_label' in ht or 'value label' in ht):
            candidates.append(tbl)
    return candidates


def infer_variable_name_from_context(tbl) -> Optional[str]:
    """Walk backward from the table to find a nearby label or 'SAS Variable Name' mentioning the variable."""
    # Search previous headings/siblings up to a small limit
    limit = 12
    varname = None
    # pattern to match SAS var name like: SAS Variable Name: _STATE
    sas_var_re = re.compile(r'sas variable name[:\s]*([A-Za-z0-9_\-]+)', flags=re.I)
    # pattern to match explicit variable tokens like _STATE or RIDAGE_G or AGE
    var_token_re = re.compile(r'\b([A-Z_]{2,20}[0-9A-Z_]*)\b')

    # check several previous blocks
    checked = 0
    for prev in tbl.find_all_previous():
        txt = prev.get_text(' ', strip=True)
        if not txt:
            continue
        checked += 1
        m = sas_var_re.search(txt)
        if m:
            return m.group(1).strip()
        # direct token search: look for common variable names
        if '_STATE' in txt:
            return '_STATE'
        if 'state fips' in txt.lower():
            return '_STATE'
        if 'age' in txt.lower() and any(k in txt.lower() for k in ('age group','agegrp','age g','ageg','age')):
            # try to pick a likely variable token
            tkns = var_token_re.findall(txt)
            if tkns:
                # return the first token that looks like an age var
                for t in tkns:
                    if 'AGE' in t or 'age' in t or 'RIDAGE' in t or 'AGEG' in t:
                        return t
                return tkns[0]
        if checked > limit:
            break
    return None


def parse_table_to_pairs(tbl) -> List[Tuple[str, str]]:
    """Extract (value, label) pairs from a table element. Returns a list of tuples."""
    rows = []
    for tr in tbl.find_all('tr'):
        cells = [td.get_text(' ', strip=True) for td in tr.find_all(['td', 'th'])]
        if not cells:
            continue
        # Skip header rows that are all non-data like 'Value Value Label Frequency ...'
        lower_cells = [c.lower() for c in cells]
        if any('value' in c for c in lower_cells) and any('label' in c for c in lower_cells):
            continue
        # pick first two columns as value and label when available
        if len(cells) >= 2:
            val = cells[0]
            label = cells[1]
            # sometimes tables include a header row repeated as first row; skip if value contains non-data words
            if re.search('[A-Za-z]', val) and not re.match(r'^[0-9\-]+$', val):
                # val looks like text, but sometimes value labels use text; we'll still include
                pass
            rows.append((val, label))
        elif len(cells) == 1:
            # single-column tables sometimes put "1  Alabama" as one cell; try to split
            parts = cells[0].split(None, 1)
            if len(parts) == 2:
                rows.append((parts[0], parts[1]))
    # filter out blank or obviously header-like rows
    out = []
    for v, l in rows:
        if v is None or v == '':
            continue
        # skip rows that look like table captions
        if v.lower().startswith('value') and 'label' in l.lower():
            continue
        out.append((v, l))
    return out


def write_csv(p: Path, pairs: List[Tuple[str, str]]):
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open('w', newline='', encoding='utf-8') as fh:
        w = csv.writer(fh)
        w.writerow(['value', 'label'])
        for v, l in pairs:
            w.writerow([v, l])


def main(html_path: Path, out_dir: Path):
    if BeautifulSoup is None:
        print('BeautifulSoup4 is not available. Please install with: pip install beautifulsoup4')
        sys.exit(2)

    if not html_path.exists():
        print(f'Error: HTML codebook not found at: {html_path}')
        sys.exit(1)

    text = html_path.read_text(encoding='utf-8', errors='replace')
    soup = BeautifulSoup(text, 'html.parser')

    candidates = find_candidate_tables(soup)
    print(f'Found {len(candidates)} candidate value-label tables in codebook HTML')

    state_pairs: List[Tuple[str, str]] = []
    # collect multiple age-table candidates keyed by variable name
    age_tables: Dict[str, List[Tuple[str, str]]] = {}

    for tbl in candidates:
        var = infer_variable_name_from_context(tbl)
        pairs = parse_table_to_pairs(tbl)
        if not pairs:
            continue
        # heuristics: if var is `_STATE` or context mentions 'state', treat as state
        ctx_text = ''
        try:
            ctx_text = ' '.join([p.get_text(' ', strip=True) for p in tbl.find_all_previous(limit=10)])
        except Exception:
            ctx_text = ''

        if var and var.upper() == '_STATE' or 'state' in ctx_text.lower() or 'state fips' in ctx_text.lower():
            if not state_pairs:
                state_pairs = pairs
                print('Assigned a table to `_STATE` based on nearby context')
            else:
                print('Additional candidate for _STATE found; skipping extra')
            continue

        # Age heuristics: explicitly detect the common BRFSS computed age-group variables
        low_ctx = ctx_text.lower()
        tbl_text = tbl.get_text(' ', strip=True).lower()
        assigned_age = None

        # explicit var name detection
        if var:
            vup = var.upper()
            if vup in ('_AGEG5YR', 'AGEG5YR', 'RIDAGE_G', 'RIDAGE'):
                assigned_age = '_AGEG5YR'
            elif vup in ('_AGE65YR', 'AGE65YR'):
                assigned_age = '_AGE65YR'

        # keyword/context based detection
        if not assigned_age:
            if 'five-year' in low_ctx or 'five year' in low_ctx or 'five-year' in tbl_text or 'age in five' in low_ctx:
                assigned_age = '_AGEG5YR'
            elif 'two age' in low_ctx or '18 to 64' in low_ctx or '18-64' in low_ctx or 'two age groups' in low_ctx:
                assigned_age = '_AGE65YR'

        if assigned_age:
            if assigned_age not in age_tables:
                age_tables[assigned_age] = pairs
                print(f'Assigned a table to age variable `{assigned_age}` (inferred from context)')
            else:
                print(f'Additional candidate age table found for `{assigned_age}`; skipping extra')
            continue

    # fallback: try to find by scanning all tables for ones that have a lot of items and include typical state names
    if not state_pairs:
        # search tables that include 'Alabama' or other known states
        for tbl in candidates:
            ttxt = tbl.get_text(' ', strip=True)
            if 'Alabama' in ttxt and 'Alaska' in ttxt:
                state_pairs = parse_table_to_pairs(tbl)
                print('Fallback: assigned state table by detecting state names inside table')
                break

    # If no explicit age tables were found via context heuristics, try fallbacks
    if not age_tables:
        # fallback: search for common age labels like '18-24' or '75+' in candidate tables
        for tbl in candidates:
            ttxt = tbl.get_text(' ', strip=True)
            if re.search(r'18[-–]24|75\+', ttxt):
                # prefer assigning to the 5-year grouping if many ranges found
                pairs = parse_table_to_pairs(tbl)
                if pairs:
                    age_tables['_AGEG5YR'] = pairs
                    print('Fallback: assigned Age Group table to `_AGEG5YR` by detecting age ranges inside table')
                    break

    out_dir.mkdir(parents=True, exist_ok=True)

    if state_pairs:
        state_csv = out_dir / 'state_fips_codes.csv'
        write_csv(state_csv, state_pairs)
        print(f'Wrote {len(state_pairs)} state rows to: {state_csv}')
    else:
        print('No state table extracted.')

    if age_tables:
        total_age_rows = 0
        for varname, pairs in age_tables.items():
            # sanitize varname for filename
            safe_var = varname.replace('/', '_').replace(' ', '_')
            age_csv = out_dir / f'age_{safe_var}_values.csv'
            write_csv(age_csv, pairs)
            print(f'Wrote {len(pairs)} rows for age variable {varname} to: {age_csv}')
            total_age_rows += len(pairs)
    else:
        print('No age-group table extracted.')

    # Also write a small JSON summary
    # summary: include per-variable age counts
    summary = {
        'state_rows': len(state_pairs),
        'age_tables': {k: len(v) for k, v in age_tables.items()},
    }
    (out_dir / 'summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print('Wrote summary.json')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description='Parse USCODE LLCP HTML codebook to extract state and age value-label tables')
    default_html = Path('2433_p3_data/healthcare.gov/CODEBOOK/USCODE24_LLCP_082125.HTML')
    p.add_argument('--html', '-i', type=Path, default=default_html, help='Path to codebook HTML file')
    p.add_argument('--out', '-o', type=Path, default=Path('2433_p3_data/healthcare.gov/exports/codebook_tables/'), help='Output directory for CSVs')
    args = p.parse_args()
    main(args.html, args.out)
