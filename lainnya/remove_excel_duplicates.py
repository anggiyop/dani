
#!/usr/bin/env python3
"""
remove_excel_duplicates.py

Remove duplicate rows from an .xlsx file across one or all sheets.

Features:
- Process all sheets automatically.
- Choose columns to consider for duplicate detection (by name or by index).
- Optional case-insensitive and/or whitespace-trim comparison for text columns.
- Choose which duplicate to keep: first, last, or none (drop all duplicates).
- Overwrite the original file with --inplace or write to a new file (default adds _deduped suffix).
- Prints a summary of rows removed per sheet.

Usage examples:
  python remove_excel_duplicates.py input.xlsx
  python remove_excel_duplicates.py input.xlsx --subset "Email,Phone"
  python remove_excel_duplicates.py input.xlsx --by-index "0,2,3" --ignore-case --trim
  python remove_excel_duplicates.py input.xlsx --keep last --inplace

Requirements:
  pip install pandas openpyxl
"""

import argparse
import os
import sys
from typing import List, Optional

import pandas as pd

def parse_list_arg(arg: Optional[str]) -> Optional[List[str]]:
    if arg is None or arg.strip() == "":
        return None
    # Split by comma and strip whitespace
    return [x.strip() for x in arg.split(",") if x.strip() != ""]

def pick_output_path(input_path: str, output_path: Optional[str], inplace: bool) -> str:
    if inplace:
        return input_path
    if output_path:
        return output_path
    base, ext = os.path.splitext(input_path)
    return f"{base}_deduped{ext or '.xlsx'}"

def normalize_series(s: pd.Series, do_trim: bool, do_ignore_case: bool) -> pd.Series:
    # Work only on object dtype for text transformations
    if pd.api.types.is_string_dtype(s) or s.dtype == object:
        # Preserve NaN values as NaN
        out = s.astype("string")  # keeps <NA>
        if do_trim:
            out = out.str.strip()
        if do_ignore_case:
            # casefold handles unicode better than lower()
            out = out.str.casefold()
        return out
    else:
        # For non-text types, return as is
        return s

def get_subset_by_index(df: pd.DataFrame, indices: List[int]) -> List[str]:
    cols = df.columns.tolist()
    subset_cols = []
    for idx in indices:
        if idx < 0 or idx >= len(cols):
            raise IndexError(f"Column index {idx} out of range for sheet with {len(cols)} columns")
        subset_cols.append(cols[idx])
    return subset_cols

def deduplicate_sheet(
    df: pd.DataFrame,
    subset_cols: Optional[List[str]],
    keep: str,
    trim: bool,
    ignore_case: bool,
) -> pd.DataFrame:
    # Decide which columns to use for duplicate detection
    if subset_cols is None:
        subset_cols = df.columns.tolist()
    else:
        # Validate presence
        missing = [c for c in subset_cols if c not in df.columns]
        if missing:
            raise KeyError(f"Subset columns not found: {missing}. Available: {list(df.columns)}")

    # Build a normalized copy with temp columns
    work = df.copy()
    norm_cols = []
    for c in subset_cols:
        norm_name = f"__norm__{c}"
        work[norm_name] = normalize_series(work[c], do_trim=trim, do_ignore_case=ignore_case)
        norm_cols.append(norm_name)

    # Apply drop_duplicates on normalized cols
    if keep not in {"first", "last", "false", "none"}:
        raise ValueError("--keep must be one of: first, last, none")
    keep_arg = {"first": "first", "last": "last", "none": False, "false": False}[keep]

    deduped = work.drop_duplicates(subset=norm_cols, keep=keep_arg)

    # Restore to original columns only, preserve original order
    deduped = deduped[df.columns]

    return deduped

def main():
    parser = argparse.ArgumentParser(description="Remove duplicate rows from an Excel file (.xlsx).")
    parser.add_argument("input", help="Path to input .xlsx file")
    parser.add_argument("-o", "--output", help="Path to output .xlsx file (default: <input> with _deduped suffix)")
    parser.add_argument("--subset", help="Comma-separated column NAMES to consider for duplicates (e.g., 'Email,Phone')")
    parser.add_argument("--by-index", help="Comma-separated column INDICES (0-based) to consider (e.g., '0,2,3')")
    parser.add_argument("--keep", choices=["first", "last", "none"], default="first",
                        help="Which duplicate to keep (default: first)")
    parser.add_argument("--trim", action="store_true", help="Trim whitespace on text columns before comparing")
    parser.add_argument("--ignore-case", action="store_true", help="Make text comparison case-insensitive")
    parser.add_argument("--inplace", action="store_true", help="Overwrite the input file")

    args = parser.parse_args()

    input_path = args.input
    output_path = pick_output_path(input_path, args.output, args.inplace)

    if not os.path.exists(input_path):
        print(f"ERROR: Input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    # Validate subset/by-index options
    subset_cols = None
    if args.subset and args.by_index:
        print("ERROR: Use either --subset or --by-index, not both.", file=sys.stderr)
        sys.exit(1)

    try:
        xls = pd.ExcelFile(input_path, engine="openpyxl")
    except Exception as e:
        print(f"ERROR: Failed to open Excel file. {e}", file=sys.stderr)
        sys.exit(1)

    sheet_names = xls.sheet_names
    if not sheet_names:
        print("ERROR: No sheets found in the workbook.", file=sys.stderr)
        sys.exit(1)

    deduped_frames = {}
    summary = []

    for sheet in sheet_names:
        df = pd.read_excel(xls, sheet_name=sheet)

        # Decide subset columns for this sheet
        if args.subset:
            subset_cols = parse_list_arg(args.subset)
        elif args.by_index:
            idxs = [int(x) for x in parse_list_arg(args.by_index)]
            subset_cols = get_subset_by_index(df, idxs)
        else:
            subset_cols = None  # use all columns

        before = len(df)
        try:
            out_df = deduplicate_sheet(
                df,
                subset_cols=subset_cols,
                keep=args.keep,
                trim=args.trim,
                ignore_case=args.ignore_case,
            )
        except Exception as e:
            print(f"ERROR: Sheet '{sheet}': {e}", file=sys.stderr)
            sys.exit(1)

        after = len(out_df)
        removed = before - after
        summary.append((sheet, before, after, removed))
        deduped_frames[sheet] = out_df

    # Write output
    try:
        with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
            for sheet, frame in deduped_frames.items():
                frame.to_excel(writer, sheet_name=sheet, index=False)
    except Exception as e:
        print(f"ERROR: Failed to write output workbook: {e}", file=sys.stderr)
        sys.exit(1)

    # Print summary
    print(f"Saved: {output_path}")
    for (sheet, before, after, removed) in summary:
        print(f"[{sheet}] rows: {before} -> {after} (removed {removed})")

if __name__ == "__main__":
    main()
