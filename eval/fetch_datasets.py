"""Download the evaluation datasets.

Vendors nothing. Everything lands under eval/datasets/ (gitignored); no audio or
annotation file is ever committed to the repository. See eval/README.md for the
data sources, licensing, and the reasons behind the key/tempo dataset choices.

Usage:
    python eval/fetch_datasets.py --all      # key + tempo
    python eval/fetch_datasets.py --key      # GiantSteps+ EDM Key only
    python eval/fetch_datasets.py --tempo    # GTZAN audio + tempo annotations
"""

from __future__ import annotations

import argparse
import sys

import eval_datasets


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--key", action="store_true", help="GiantSteps+ EDM Key")
    parser.add_argument("--tempo", action="store_true", help="GTZAN + tempo annotations")
    parser.add_argument("--all", action="store_true", help="both datasets")
    args = parser.parse_args(argv)

    if not (args.key or args.tempo or args.all):
        parser.error("choose at least one of --key, --tempo, --all")

    if args.key or args.all:
        cov = eval_datasets.download_key()
        _report("GiantSteps+ EDM Key", cov)

    if args.tempo or args.all:
        cov = eval_datasets.download_tempo()
        _report("GTZAN Tempo", cov)

    return 0


def _report(name: str, cov: dict) -> None:
    print(
        f"\n{name}: {cov['usable']}/{cov['total']} tracks usable "
        f"(with_reference={cov['with_reference']}, with_audio={cov['with_audio']})"
    )
    if cov["usable"] == 0:
        print("  WARNING: no usable tracks - check the download output above.")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
