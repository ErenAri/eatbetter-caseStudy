from __future__ import annotations

import json
from pathlib import Path

from .benchmark_metrics import baseline_comparison
from .configuration import ConfigurationName
from .scoring import ranked_errors, score_configuration


def write_report(output: Path, *, manifest, cases, records, configurations) -> None:
    if output.exists():
        raise FileExistsError(f"refusing to overwrite benchmark output: {output}")
    output.mkdir(parents=True)
    all_metrics = {}
    all_errors = []
    primary_errors = []
    for name in ConfigurationName:
        metrics, errors = score_configuration(cases, records, str(name))
        all_metrics[str(name)] = metrics
        tagged = [{"configuration": str(name), **error} for error in errors]
        all_errors.extend(tagged)
        if name == ConfigurationName.HYBRID_AUTO:
            primary_errors = tagged
    baseline = all_metrics[str(ConfigurationName.BASELINE_TOP1)]
    hybrid = all_metrics[str(ConfigurationName.HYBRID_AUTO)]
    all_metrics["BASELINE_VS_HYBRID_AUTO"] = {
        "selector": baseline_comparison(baseline["canonicalization"], hybrid["canonicalization"], ["selection_accuracy", "coverage", "wrong_selection_rate"]),
        "nutrition": baseline_comparison(baseline["nutrition"], hybrid["nutrition"], ["calories_kcal_mae", "meals_within_20_percent_calories"]),
        "safety": baseline_comparison(baseline["safety"], hybrid["safety"], ["unsafe_auto_accept_rate", "auto_accept_coverage"]),
    }
    root_causes = ranked_errors(primary_errors)
    summary = {
        "dataset_version": manifest.dataset_version,
        "case_count": len(cases),
        "completed_case_count": sum(record.get("status") == "completed" for record in records),
        "infrastructure_failure_count": sum(record.get("status") != "completed" for record in records),
        "configurations": [str(value) for value in ConfigurationName],
        "root_causes": root_causes,
        "root_cause_ranking_basis": "unweighted error occurrence counts; hidden ingredient nutrition impact is reported separately",
        "next_improvement_targets": [item["error_type"] for item in root_causes[:3]],
        "claims_status": "measured" if records and all(record.get("status") == "completed" for record in records) else "incomplete",
    }
    _write_json(output / "summary.json", summary)
    _write_json(output / "metrics.json", all_metrics)
    _write_json(output / "errors.json", {"errors": all_errors, "ranked": root_causes})
    _write_json(output / "configuration.json", {"configurations": [item.to_dict() for item in configurations]})
    with (output / "cases.jsonl").open("x", encoding="utf-8") as stream:
        for record in records:
            stream.write(json.dumps(record, sort_keys=True) + "\n")
    gallery_errors = primary_errors if configurations and configurations[0].split == "development" else []
    (output / "summary.md").write_text(_markdown(summary, all_metrics, gallery_errors), encoding="utf-8")


def _write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _format(metric: dict | None) -> str:
    if not metric or metric.get("value") is None:
        return "Not measured"
    value = metric["value"]
    suffix = f" (n={metric['denominator']})"
    return (f"{value * 100:.1f}%" if metric.get("unit") == "ratio" else f"{value:.2f} {metric.get('unit', '')}".strip()) + suffix


def _format_hidden_calorie_coverage(metric: dict | None) -> str:
    if not metric or metric.get("value") is None:
        return "Not measured"
    return f"{metric['value'] * 100:.1f}% ({metric['denominator']:.2f} measured hidden kcal)"


def _markdown(summary: dict, metrics: dict, errors: list[dict]) -> str:
    lines = [
        "# Benchmark summary",
        "",
        f"Dataset: `{summary['dataset_version']}` ({summary['case_count']} requested; {summary['completed_case_count']} completed)",
        "",
        "Oracle results are evaluation-only and are not automatic product accuracy.",
        "Root-cause ranking uses unweighted error occurrence counts; hidden-ingredient calorie coverage is reported separately.",
        "",
    ]
    for name in ConfigurationName:
        current = metrics[str(name)]
        lines.extend([
            f"## {name}",
            "",
            f"- Food F1: {_format(current['recognition']['food_f1'])}",
            f"- Hidden ingredient recall: {_format(current['hidden_ingredient']['recall_all'])}",
            f"- Hidden calorie coverage: {_format_hidden_calorie_coverage(current['hidden_ingredient']['calorie_weighted_coverage'])}",
            f"- Retrieval Recall@5: {_format(current['retrieval']['recall_at_5'])}",
            f"- Selector accuracy: {_format(current['canonicalization']['selection_accuracy'])}",
            f"- Calorie MAE: {_format(current['nutrition']['calories_kcal_mae'])}",
            f"- Meals within ±20%: {_format(current['nutrition']['meals_within_20_percent_calories'])}",
            f"- Unsafe auto-accept rate: {_format(current['safety']['unsafe_auto_accept_rate'])}",
            f"- Clarification rate: {_format(current['clarification']['clarification_rate'])}",
            "",
        ])
    if errors:
        lines.extend(["## Development failure gallery", "", "Private image bytes are omitted; references identify grader records.", ""])
        for error in errors:
            lines.append(f"- `{error['case_id']}` / `{error['image_reference']}` — {error['stage']} / {error['taxonomy']}; expected `{error['expected']}`, predicted `{error['predicted']}`")
    return "\n".join(lines)
