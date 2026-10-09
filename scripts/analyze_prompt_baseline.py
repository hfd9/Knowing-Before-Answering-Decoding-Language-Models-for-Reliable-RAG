"""Supplementary first-line label analysis; never modify saved model outputs.

Report format adherence separately from classification. This parsing change is
post hoc and must be distinguished from the original strict-output protocol.
"""

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path

import prompt_baseline as baseline

PARSER_POLICY = "first_nonempty_line_single_label_v1"


def first_line_label(text):
    lines = text.strip().splitlines()
    return baseline.parse_label(lines[0]) if lines else None


def question_success(rows, records):
    groups = defaultdict(list)
    for row, record in zip(rows, records):
        groups[row["original_id"]].append(row["true_mode"] == record["pred_mode"])
    return {"all_three_correct": sum(all(group) for group in groups.values()),
            "questions": len(groups)}


def analyze(run):
    checkpoint = run / "predictions.json"
    saved = json.loads(checkpoint.read_text())
    spec = saved["spec"]
    split = spec["split"]
    reference = Path(spec["reference_run"])
    full_rows = baseline.load_rows(reference / "data" / f"instances_{split}.jsonl")
    selected = spec["selected_ids"]
    # Reuse data/model integrity checks, but evaluate the historical saved spec.
    args = argparse.Namespace(reference_run=reference, model=spec["model_and_source"]["model"],
                              split=split, max_new_tokens=spec["generation"]["max_new_tokens"],
                              limit_questions=len(selected) // 3 if len(selected) < len(full_rows) else None)
    rows, _ = baseline.load_evaluation(args)
    if [r["id"] for r in rows] != selected:
        raise ValueError("Saved sample IDs do not match source data.")
    records = baseline.load_checkpoint(run, spec, rows)
    if len(records) != len(rows):
        raise ValueError(f"Incomplete inference: {len(records)}/{len(rows)}.")
    derived = [dict(r, pred_mode=first_line_label(r["raw_output"])) for r in records]
    strict = baseline.evaluate(rows, records)
    metrics = baseline.evaluate(rows, derived)
    metrics["question_success"] = question_success(rows, derived)
    report = {
        "recorded_at": datetime.now(timezone.utc).isoformat(), "split": split,
        "source_predictions": str(checkpoint), "source_sha256": baseline.digest_file(checkpoint),
        "parser_policy": PARSER_POLICY, "parsing_changed_after_inference": True,
        "protocol_note": "First-line parsing is a supplementary post-hoc analysis. Original full-output format adherence is reported separately. No prompt or raw output changed; no inference rerun.",
        "n_instances": len(rows), "full_evaluation_set": len(rows) == len(full_rows),
        "baseline": metrics,
        "strict_output_format": {"compliant_count": len(rows) - strict["invalid_count"],
                                 "noncompliant_count": strict["invalid_count"],
                                 "compliance_rate": strict["parse_coverage"]},
        "hit_output_limit_count": sum(r["hit_output_limit"] for r in records),
        "inference_seconds_sum": sum(r["elapsed_seconds"] for r in records),
        "max_peak_allocated_gib": max(r["peak_allocated_gib"] for r in records),
    }
    errors = []
    if split == "test":
        router_file = reference / "results" / "router_test_predictions.json"
        router_all = json.loads(router_file.read_text())
        if len(router_all) != len(full_rows):
            raise ValueError("Router prediction count mismatch.")
        for row, record in zip(full_rows, router_all):
            if record["id"] != row["id"] or record["true_mode"] != row["true_mode"] or record["pred_mode"] not in baseline.MODES:
                raise ValueError("Router prediction ID/label mismatch.")
        lookup = {r["id"]: r for r in router_all}
        router = [lookup[r["id"]] for r in rows]
        report["router"] = baseline.evaluate(rows, router)
        report["router"]["question_success"] = question_success(rows, router)
        report["router_predictions_sha256"] = baseline.digest_file(router_file)
        report["paired_accuracy"] = baseline.paired_accuracy_interval(rows, derived, router)
        counts = Counter()
        transition = Counter()
        for row, base, route in zip(rows, derived, router):
            base_ok = base["pred_mode"] == row["true_mode"]
            route_ok = route["pred_mode"] == row["true_mode"]
            category = ("both_correct" if base_ok and route_ok else "baseline_only_correct" if base_ok
                        else "router_only_correct" if route_ok else "both_wrong")
            counts[category] += 1
            transition[(row["true_mode"], base["pred_mode"] or "invalid", route["pred_mode"])] += 1
            if category != "both_correct":
                errors.append({"id": row["id"], "original_id": row["original_id"],
                               "question": row["question"], "true_mode": row["true_mode"],
                               "baseline_pred": base["pred_mode"], "router_pred": route["pred_mode"],
                               "baseline_raw_output": base["raw_output"], "category": category})
        report["paired_outcomes"] = {k: counts[k] for k in ["both_correct", "baseline_only_correct", "router_only_correct", "both_wrong"]}
        report["class_transitions"] = [{"true_mode": true, "baseline_pred": base, "router_pred": route, "count": n}
                                       for (true, base, route), n in sorted(transition.items())]
    else:
        errors = [{"id": r["id"], "true_mode": r["true_mode"], "pred_mode": r["pred_mode"],
                   "raw_output": r["raw_output"]} for r in derived if r["pred_mode"] != r["true_mode"]]
    output = run / "first_line_analysis"
    baseline.write_json(output / "comparison.json", report)
    baseline.write_json(output / "errors.json", errors)
    baseline.write_json(output / "parsed_predictions.json", {"parser_policy": PARSER_POLICY,
                        "source_sha256": report["source_sha256"], "records": derived})
    lines = ["# 提示词基线首行解析补充分析", "",
             f"集合：{split}；实例：{len(rows)}；解析规则：{PARSER_POLICY}。", "",
             "模型原始输出与原评估结果均保留。这是运行后修正解析口径的补充分析：只接受首个非空行中的单一类别词，拒绝同一行多标签；后续解释不影响首行类别。",
             "完整输出格式遵从率单独报告；不能将原报告的 0% 当作模型分类能力。", "",
             "| 方法 | Accuracy | Macro-F1 | FAR | 无法解析 |", "| --- | ---: | ---: | ---: | ---: |"]
    for name, m in [("隐藏状态路由器", report["router"])] if "router" in report else []:
        lines.append(f"| {name} | {m['accuracy']:.2%} | {m['macro_f1']:.2%} | {m['far']:.2%} | {m['invalid_count']} |")
    m = metrics
    lines += [f"| 提示词基线，首行解析 | {m['accuracy']:.2%} | {m['macro_f1']:.2%} | {m['far']:.2%} | {m['invalid_count']} |", "",
              f"原完整输出格式遵从率：{strict['parse_coverage']:.2%}；首行解析覆盖率：{m['parse_coverage']:.2%}。",
              f"输出达到 token 上限且未以 EOS 结束的实例：{report['hit_output_limit_count']}/{len(rows)}。", "",
              "| 真实 / 预测 | answer | refuse | conflict | invalid |", "| --- | ---: | ---: | ---: | ---: |"]
    for name, values in zip(baseline.MODES, m["confusion_matrix"]):
        lines.append(f"| {name} | " + " | ".join(map(str, values)) + " |")
    if "paired_accuracy" in report:
        delta = report["paired_accuracy"]
        lo, hi = delta["question_bootstrap_95ci"]
        lines += ["", f"配对结果：{json.dumps(report['paired_outcomes'], ensure_ascii=False)}。",
                  f"基线减路由器准确率：{delta['difference']*100:.2f} 个百分点；按问题配对 bootstrap 95% 区间 [{lo*100:.2f}, {hi*100:.2f}] 个百分点。"]
    lines += ["", "这是当前纯文本、短输出预算设置下的结果；不能代表所有提示词基线。解析口径在运行后变更，未重新生成或修改提示词。后续提示词与 chat-template 对照应使用验证集选择设置；测试集已被查看，应保留这一记录。"]
    (output / "comparison.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run_dir", type=Path, default=Path("runs/qwen2.5-3b-prompt-baseline"))
    args = parser.parse_args()
    run = args.run_dir if args.run_dir.is_absolute() else baseline.PROJECT / args.run_dir
    with baseline.run_lock(run):
        analyze(run.resolve())


if __name__ == "__main__":
    main()
