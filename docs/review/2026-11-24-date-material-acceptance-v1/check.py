"""Replay the finite-date reference and paired input checks using only local files."""

import json
from datetime import date, timedelta
from itertools import product
from pathlib import Path


def main():
    folder = Path(__file__).resolve().parent
    inputs = json.loads((folder / "inputs.json").read_text(encoding="utf-8"))
    reference = json.loads((folder / "reference.json").read_text(encoding="utf-8"))
    versions = reference["versions"]
    amounts = reference["option_amounts_usd"]
    cases = reference["cases"]

    start, end = map(date.fromisoformat, reference["allowed_date_range_inclusive"])
    days = [start + timedelta(days=offset) for offset in range((end - start).days + 1)]
    applicable = {}
    for day in days:
        matches = [
            evidence_id
            for evidence_id, version in versions.items()
            if date.fromisoformat(version["effective_from"])
            <= day
            <= date.fromisoformat(version["applies_through"])
        ]
        assert len(matches) == 1, (day, matches)
        applicable[day.isoformat()] = matches[0]
    assert list(applicable.values()) == ["E2", "E3"]

    input_ids = {row["id"] for row in inputs}
    conditions = {(case["option"], case["event_date"]) for case in cases.values()}
    assert len(inputs) == len(input_ids) == len(cases) == 6
    assert input_ids == cases.keys()
    assert conditions == set(product(amounts, [*applicable, None]))

    common_inputs = set()
    input_texts = set()
    for row in inputs:
        case = cases[row["id"]]
        option = case["option"]
        event_date = case["event_date"]
        rules, scenario, question = row["input"].split("\n\n")
        assert set(row) == {"id", "input"}, row["id"]
        for evidence_id, version in versions.items():
            line = f'[{evidence_id}] Supplement I, comment {version["comment"]}. “{version["quote"]}”'
            assert rules.splitlines().count(line) == 1, row["id"]
            assert f'${version["threshold_usd"]:,}.' == version["quote"].split()[-1]
        for name, amount in amounts.items():
            assert f"{name} (${amount:,})" in scenario, row["id"]
        assert f"from {start} through {end}, inclusive." in scenario, row["id"]
        fact_lines = scenario.splitlines()
        dated_line = [f"The loan was consummated on {event_date}."] if event_date else []
        assert fact_lines[1:] == dated_line, row["id"]
        assert question.startswith(f"Would option {option} qualify"), row["id"]
        common_inputs.add((rules, fact_lines[0], question.replace(f"option {option}", "option", 1)))
        input_texts.add(row["input"])

        candidates = [applicable[event_date]] if event_date else list(applicable.values())
        answers = {amounts[option] > versions[evidence_id]["threshold_usd"] for evidence_id in candidates}
        expected_action = "answer" if len(answers) == 1 else "ask_date"
        expected_answer = answers.pop() if expected_action == "answer" else None
        assert case["action"] == expected_action, row["id"]
        assert case["answer"] is expected_answer, row["id"]
        assert case["evidence"] == ["E1", *candidates], row["id"]

    assert len(common_inputs) == 1 and len(input_texts) == 6
    assert sum(case["action"] == "ask_date" for case in cases.values()) == 1
    print("Pass: 2 dates, 2 versions, 2 questions, 4 dated answers, 2 omitted-date actions.")


if __name__ == "__main__":
    main()
