"""Baseline evaluation runner for backend/audio/analyzer.py.

Phase 4 measures the analyzer AS-IS: this module imports and calls
`analyze_audio` without modifying it, scores its key and tempo output against
reference datasets, and describes the spread of its energy/danceability outputs.

Layers:
  - evaluate_key / evaluate_tempo / audit_features take plain
    (audio_path, reference) pairs (or paths) and are unit-testable on synthetic
    audio with no mirdata and no network.
  - main() wires the mirdata-backed datasets (eval_datasets) into those and
    writes a JSON + text report under eval/results/.

Reproduce:
    python eval/fetch_datasets.py --all
    python eval/run_eval.py --all
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Make the app package importable so we can call the analyzer as-is, and keep
# the sibling eval modules importable when run as a script.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import audit  # noqa: E402  (sibling module)
import scoring  # noqa: E402  (sibling module)

from backend.audio.analyzer import analyze_audio  # noqa: E402

# --------------------------------------------------------------------------- #
# Key evaluation
# --------------------------------------------------------------------------- #


def evaluate_key(pairs) -> dict:
    """Score analyzer key output against reference key strings (MIREX-weighted).

    `pairs` is an iterable of (audio_path, reference_key_string).
    """
    confusion = {c: 0 for c in scoring.KEY_CATEGORIES}
    weighted_sum = 0.0
    exact = 0
    n = 0
    n_unparseable_ref = 0
    n_analysis_errors = 0
    energies: list[float] = []
    danceabilities: list[float] = []

    for audio_path, ref_str in pairs:
        reference = scoring.parse_key(ref_str)
        if reference is None:
            n_unparseable_ref += 1
            continue
        try:
            out = analyze_audio(audio_path)
        except Exception as exc:  # analyzer failure on a file - record, move on
            n_analysis_errors += 1
            print(f"  [key] analysis error on {os.path.basename(audio_path)}: {exc}")
            continue

        energies.append(out["energy"])
        danceabilities.append(out["danceability"])

        estimate = scoring.parse_key(f"{out['key']} {out['scale']}")
        if estimate is None:
            score, category = 0.0, "other"
        else:
            score, category = scoring.key_score(reference, estimate)

        confusion[category] += 1
        weighted_sum += score
        exact += category == "correct"
        n += 1

    return {
        "n": n,
        "weighted_score": (weighted_sum / n) if n else None,
        "exact_match_rate": (exact / n) if n else None,
        "exact_matches": exact,
        "confusion": confusion,
        "n_unparseable_ref": n_unparseable_ref,
        "n_analysis_errors": n_analysis_errors,
        "energy": energies,
        "danceability": danceabilities,
    }


# --------------------------------------------------------------------------- #
# Tempo evaluation
# --------------------------------------------------------------------------- #


def evaluate_tempo(pairs) -> dict:
    """Score analyzer BPM output with Accuracy1 / Accuracy2.

    `pairs` is an iterable of (audio_path, reference_bpm).
    """
    n = 0
    acc1_hits = 0
    acc2_hits = 0
    octave_hits = 0
    n_missing_ref = 0
    n_analysis_errors = 0
    energies: list[float] = []
    danceabilities: list[float] = []

    for audio_path, ref_tempo in pairs:
        if not ref_tempo or ref_tempo <= 0:
            n_missing_ref += 1
            continue
        try:
            out = analyze_audio(audio_path)
        except Exception as exc:
            n_analysis_errors += 1
            print(f"  [tempo] analysis error on {os.path.basename(audio_path)}: {exc}")
            continue

        energies.append(out["energy"])
        danceabilities.append(out["danceability"])

        est_bpm = float(out["bpm"])
        ref = float(ref_tempo)
        acc1 = scoring.tempo_accuracy1(ref, est_bpm)
        acc2 = scoring.tempo_accuracy2(ref, est_bpm)
        acc1_hits += acc1
        acc2_hits += acc2
        octave_hits += scoring.tempo_is_octave_error(ref, est_bpm)
        n += 1

    return {
        "n": n,
        "accuracy1": (acc1_hits / n) if n else None,
        "accuracy2": (acc2_hits / n) if n else None,
        "accuracy1_hits": acc1_hits,
        "accuracy2_hits": acc2_hits,
        "octave_error_hits": octave_hits,
        "n_missing_ref": n_missing_ref,
        "n_analysis_errors": n_analysis_errors,
        "energy": energies,
        "danceability": danceabilities,
    }


# --------------------------------------------------------------------------- #
# Feature distribution + internal-saturation audit
# --------------------------------------------------------------------------- #


def feature_histograms(energies: list[float], danceabilities: list[float]) -> dict:
    """Summaries of energy and danceability over [0, 1] (their design range)."""
    return {
        "energy": audit.summarize(energies, bins=10, lo=0.0, hi=1.0),
        "danceability": audit.summarize(danceabilities, bins=10, lo=0.0, hi=1.0),
    }


def audit_features(audio_paths: list[str], sample: int | None = 150) -> dict:
    """Recompute loudness/punch intermediates to test saturation and clamping.

    Samples deterministically (evenly spaced) so a partial run is reproducible
    and representative rather than front-loaded on one genre/dataset.
    """
    paths = _evenly_spaced(audio_paths, sample)
    n = 0
    loud_saturated = 0
    beat_tracked = 0
    punch_zero = 0
    loud_raw: list[float] = []
    punch_ratios: list[float] = []

    for p in paths:
        try:
            inter = audit.audit_intermediates(p)
        except Exception as exc:
            print(f"  [audit] error on {os.path.basename(p)}: {exc}")
            continue
        n += 1
        loud_saturated += inter.loudness_saturated
        loud_raw.append(inter.loudness_raw)
        if inter.had_beats:
            beat_tracked += 1
            punch_zero += inter.punch_clamped_zero
            punch_ratios.append(inter.punch_ratio)

    return {
        "n_audited": n,
        "loudness_saturation_rate": (loud_saturated / n) if n else None,
        "loudness_saturated_count": loud_saturated,
        "loudness_raw": audit.summarize(loud_raw, bins=10),
        "beat_tracked": beat_tracked,
        "punch_zero_rate": (punch_zero / beat_tracked) if beat_tracked else None,
        "punch_zero_count": punch_zero,
        "punch_ratio": audit.summarize(punch_ratios, bins=10),
    }


def _evenly_spaced(items: list, sample: int | None) -> list:
    if sample is None or sample >= len(items) or sample <= 0:
        return list(items)
    stride = len(items) / sample
    return [items[int(i * stride)] for i in range(sample)]


# --------------------------------------------------------------------------- #
# Report rendering
# --------------------------------------------------------------------------- #


def render_report(report: dict) -> str:
    lines: list[str] = ["=" * 72, "Harmonia analyzer baseline", "=" * 72]

    key = report.get("key")
    if key:
        lines += ["", "KEY  (GiantSteps+ EDM Key, MIREX-weighted)"]
        if key["n"]:
            lines.append(
                f"  scored {key['n']} tracks  "
                f"(unparseable refs skipped: {key['n_unparseable_ref']}, "
                f"analysis errors: {key['n_analysis_errors']})"
            )
            lines.append(f"  weighted score (MIREX) : {key['weighted_score']:.4f}")
            lines.append(
                f"  raw exact-match rate   : {key['exact_match_rate']:.4f} "
                f"({key['exact_matches']}/{key['n']})"
            )
            c = key["confusion"]
            lines.append(
                "  confusion              : "
                f"correct={c['correct']} fifth={c['fifth']} "
                f"relative={c['relative']} parallel={c['parallel']} other={c['other']}"
            )
        else:
            lines.append("  no tracks scored")

    tempo = report.get("tempo")
    if tempo:
        lines += ["", "TEMPO  (GTZAN, Accuracy1 / Accuracy2)"]
        if tempo["n"]:
            lines.append(
                f"  scored {tempo['n']} tracks  "
                f"(missing refs: {tempo['n_missing_ref']}, "
                f"analysis errors: {tempo['n_analysis_errors']})"
            )
            lines.append(
                f"  Accuracy1 (within 4%)  : {tempo['accuracy1']:.4f} "
                f"({tempo['accuracy1_hits']}/{tempo['n']})"
            )
            lines.append(
                f"  Accuracy2 (+ oct/3rd)  : {tempo['accuracy2']:.4f} "
                f"({tempo['accuracy2_hits']}/{tempo['n']})"
            )
            lines.append(
                f"  of which octave errors : {tempo['octave_error_hits']} "
                "(passed Accuracy2 but not Accuracy1)"
            )
        else:
            lines.append("  no tracks scored")

    feats = report.get("features")
    if feats:
        lines += ["", "FEATURE DISTRIBUTIONS"]
        lines.append(audit.format_histogram(feats["energy"], label="energy"))
        lines.append(audit.format_histogram(feats["danceability"], label="danceability"))

    au = report.get("audit")
    if au:
        lines += ["", "INTERNAL SATURATION AUDIT (analyzer.py, recomputed)"]
        if au["n_audited"]:
            lines.append(
                f"  audited {au['n_audited']} files "
                f"({au['beat_tracked']} beat-tracked)"
            )
            lines.append(
                "  loudness = min(1.0, rms/0.3) hit 1.0 in "
                f"{au['loudness_saturated_count']}/{au['n_audited']} "
                f"({_pct(au['loudness_saturation_rate'])})"
            )
            lines.append(
                "  punch = clamp((ratio-3)/6) hit 0.0 in "
                f"{au['punch_zero_count']}/{au['beat_tracked']} beat-tracked "
                f"({_pct(au['punch_zero_rate'])})"
            )
            lines.append(audit.format_histogram(au["loudness_raw"], label="  loudness_raw = rms/0.3"))
            lines.append(audit.format_histogram(au["punch_ratio"], label="  punch_ratio = beat/mean onset"))
        else:
            lines.append("  no files audited")

    lines.append("")
    return "\n".join(lines)


def _pct(x: float | None) -> str:
    return "n/a" if x is None else f"{100 * x:.1f}%"


def _strip_series(report: dict) -> dict:
    """Drop the raw per-track energy/danceability lists from the JSON payload."""
    out = json.loads(json.dumps(report))  # deep copy via round-trip
    for section in ("key", "tempo"):
        if out.get(section):
            out[section].pop("energy", None)
            out[section].pop("danceability", None)
    return out


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--key", action="store_true", help="evaluate key")
    parser.add_argument("--tempo", action="store_true", help="evaluate tempo")
    parser.add_argument("--all", action="store_true", help="evaluate both")
    parser.add_argument("--limit", type=int, default=None, help="cap tracks per dataset (quick runs)")
    parser.add_argument("--audit-sample", type=int, default=150, help="files for the saturation audit")
    parser.add_argument("--out", default=str(Path(__file__).resolve().parent / "results"))
    args = parser.parse_args(argv)

    if not (args.key or args.tempo or args.all):
        parser.error("choose at least one of --key, --tempo, --all")

    import eval_datasets

    report: dict = {}
    all_energy: list[float] = []
    all_dance: list[float] = []
    all_audio: list[str] = []

    if args.key or args.all:
        pairs = eval_datasets.key_pairs(limit=args.limit)
        print(f"Evaluating key on {len(pairs)} GiantSteps+ tracks ...")
        report["key"] = evaluate_key(pairs)
        all_energy += report["key"]["energy"]
        all_dance += report["key"]["danceability"]
        all_audio += [p for p, _ in pairs]

    if args.tempo or args.all:
        pairs = eval_datasets.tempo_pairs(limit=args.limit)
        print(f"Evaluating tempo on {len(pairs)} GTZAN tracks ...")
        report["tempo"] = evaluate_tempo(pairs)
        all_energy += report["tempo"]["energy"]
        all_dance += report["tempo"]["danceability"]
        all_audio += [p for p, _ in pairs]

    report["features"] = feature_histograms(all_energy, all_dance)
    print(f"Auditing internal saturation on up to {args.audit_sample} files ...")
    report["audit"] = audit_features(all_audio, sample=args.audit_sample)

    text = render_report(report)
    print("\n" + text)

    os.makedirs(args.out, exist_ok=True)
    (Path(args.out) / "baseline.txt").write_text(text)
    (Path(args.out) / "baseline.json").write_text(
        json.dumps(_strip_series(report), indent=2)
    )
    print(f"Wrote {args.out}/baseline.txt and baseline.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
