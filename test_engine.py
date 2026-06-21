from pathlib import Path

from dynacore.data import CONCEPTS, FORMULA_RULES, MISCONCEPTION_QUIZZES, TARGET_OPTIONS
from dynacore.engine import grade_formula_sense, import_progress_json, recommend_formulas


def test_streamlit_entrypoint_calls_main():
    text = Path("streamlit_app.py").read_text(encoding="utf-8")
    assert "from app import main" in text
    assert "main()" in text


def test_target_options_have_rule_coverage():
    covered = set()
    for r in FORMULA_RULES:
        covered.update(r.get("targets", []))
    missing = set(TARGET_OPTIONS) - covered
    assert not missing, f"uncovered targets: {missing}"


def test_latex_bad_patterns_removed():
    bad = ["\\sump", "\\Deltat", "\\sumF", "\\u00", "\\u03", "\\u1e"]
    all_formulas = []
    for c in CONCEPTS.values():
        all_formulas += [f.get("latex", "") for f in c.get("formulas", [])]
    for r in FORMULA_RULES:
        all_formulas += r.get("formulas", [])
    offenders = [f for f in all_formulas if any(b in f for b in bad)]
    assert not offenders[:5]


def test_frictionless_does_not_prioritize_friction():
    recs = recommend_formulas(["속도"], ["질량", "높이"], ["경사면"], "frictionless incline height speed", limit=5)
    names = [r["concept_id"] for r in recs]
    assert "friction" not in names[:2]
    assert any(cid in names for cid in ["energy_conservation", "work_energy_principle"])


def test_not_circular_penalizes_circular_rules():
    recs = recommend_formulas(["가속도"], ["속도", "반지름"], ["평면운동"], "not circular path, radius is just a parameter", limit=5)
    top = [r["concept_id"] for r in recs[:2]]
    assert "force_in_circular_motion" not in top


def test_quiz_coverage_at_least_three_per_concept():
    counts = {cid: 0 for cid in CONCEPTS}
    for q in MISCONCEPTION_QUIZZES:
        counts[q["concept_id"]] += 1
    assert all(v >= 3 for v in counts.values())


def test_import_progress_json_filters_invalid_concepts():
    data = '{"confusion_vault":["nt_coordinates","bad_id"],"studied_concepts":["bad2","friction"],"mastery":{"bad3":99,"friction":80}}'
    out = import_progress_json(data)
    assert out["confusion_vault"] == ["nt_coordinates"]
    assert out["studied_concepts"] == ["friction"]
    assert out["mastery"] == {"friction": 80}
    assert out["warnings"]


def test_formula_sense_negation_not_correct():
    q = {
        "expected_number": 4.0,
        "expected_direction": "증가",
    }
    result = grade_formula_sense(q, "4배가 아니다")
    assert not result["correct"]


def test_import_new_profile_export_shape():
    data = '{"progress":{"nt_coordinates":{"confusion":1,"studied_count":2,"mastery":55},"bad":{"confusion":1,"studied_count":1,"mastery":99}}}'
    out = import_progress_json(data)
    assert out["confusion_vault"] == ["nt_coordinates"]
    assert out["studied_concepts"] == ["nt_coordinates"]
    assert out["mastery"] == {"nt_coordinates": 55}


def test_v3_main_menu_simplified():
    text = Path("app.py").read_text(encoding="utf-8")
    assert 'MAIN_PAGES = ["홈", "개념", "문제", "복습", "리포트", "설정"]' in text
    assert 'page_home(api_key)' in text
    assert 'page_problem_hub()' in text


def test_v3_stepper_ui_present():
    text = Path("app.py").read_text(encoding="utf-8")
    assert "page_solver_stepper" in text
    assert "문제 이해" in text and "FBD" in text and "좌표축" in text and "방정식" in text and "단위" in text
