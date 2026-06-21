from __future__ import annotations

import json
import math
import re
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .data import CONCEPTS, FORMULA_RULES, MISCONCEPTION_QUIZZES, FORMULA_SENSE_QUESTIONS


def normalize_text(text: str) -> str:
    text = (text or "").strip().lower()
    text = text.replace("μ", "mu").replace("θ", "theta").replace("ω", "omega").replace("α", "alpha")
    return re.sub(r"\s+", " ", text)


NEGATION_PATTERNS = {
    "friction": [r"frictionless", r"no\s+friction", r"without\s+friction", r"마찰\s*없", r"마찰이\s*없", r"매끄러운"],
    "circular": [r"not\s+circular", r"not\s+a\s+circle", r"not\s+circle", r"원운동\s*아님", r"원형\s*아니", r"원이\s*아니"],
    "spring": [r"no\s+spring", r"스프링\s*없"],
    "collision": [r"not\s+a\s+collision", r"충돌\s*아님"],
}

KEYWORD_CATEGORIES = {
    "friction": ["friction", "마찰", "mu", "μ"],
    "circular": ["circular", "circle", "radius", "curvature", "원운동", "원형", "반지름", "곡률"],
    "spring": ["spring", "스프링", "stiffness", "k="],
    "collision": ["collision", "impact", "rebound", "충돌", "튕김", "부딪"],
}

TARGET_SYNONYMS = {"속력": "속도", "변위": "위치", "반력": "수직항력"}


def analyze_problem_text(text: str) -> Dict[str, Any]:
    norm = normalize_text(text)
    negated_categories: List[str] = []
    for category, patterns in NEGATION_PATTERNS.items():
        if any(re.search(p, norm) for p in patterns):
            negated_categories.append(category)
    positive_categories: List[str] = []
    for category, words in KEYWORD_CATEGORIES.items():
        if any(normalize_text(w) in norm for w in words) and category not in negated_categories:
            positive_categories.append(category)
    return {"normalized": norm, "negated_categories": negated_categories, "positive_categories": positive_categories}


def _expand(values: Iterable[str]) -> List[str]:
    out = list(values or [])
    for v in list(out):
        if v in TARGET_SYNONYMS and TARGET_SYNONYMS[v] not in out:
            out.append(TARGET_SYNONYMS[v])
    return out


def get_concepts_by_chapter(chapter: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
    if not chapter or chapter == "전체":
        return CONCEPTS
    return {cid: c for cid, c in CONCEPTS.items() if c.get("chapter") == chapter}


def search_concepts(query: str, chapter: Optional[str] = None) -> List[Tuple[str, Dict[str, Any], int]]:
    q = normalize_text(query)
    pool = get_concepts_by_chapter(chapter)
    if not q:
        return [(cid, c, 0) for cid, c in pool.items()]
    results = []
    for cid, c in pool.items():
        blob = " ".join([
            c.get("title", ""), c.get("chapter", ""), c.get("summary", ""), c.get("analogy", ""),
            " ".join(c.get("tags", [])), " ".join(c.get("problem_clues", [])), " ".join(c.get("when_to_use", [])),
        ]).lower()
        score = 0
        for token in q.split():
            if token in blob:
                score += 3
            if token in c.get("title", "").lower():
                score += 6
        if score > 0:
            results.append((cid, c, score))
    return sorted(results, key=lambda x: (-x[2], x[1]["level"], x[1]["title"]))


def _overlap_score(selected: Iterable[str], rule_values: Iterable[str], weight: int = 3) -> Tuple[int, List[str]]:
    selected_set = set(_expand(selected or []))
    rule_set = set(rule_values or [])
    hits = sorted(selected_set.intersection(rule_set))
    return len(hits) * weight, hits


def _keyword_hits(rule: Dict[str, Any], analysis: Dict[str, Any]) -> Tuple[int, List[str], List[str]]:
    norm = analysis["normalized"]
    score = 0
    hits: List[str] = []
    penalties: List[str] = []
    for k in rule.get("keywords", []):
        nk = normalize_text(k)
        if not nk:
            continue
        if nk in norm:
            score += 5
            hits.append(k)
    for k in rule.get("negative_keywords", []):
        nk = normalize_text(k)
        if nk and nk in norm:
            score -= 8
            penalties.append(k)
    concept_id = rule.get("concept_id", "")
    # semantic negation penalties
    neg = set(analysis.get("negated_categories", []))
    if concept_id == "friction" and "friction" in neg:
        score -= 20
        penalties.append("마찰 없음/무마찰 조건")
    if concept_id in {"circular_motion", "nt_coordinates", "force_in_circular_motion"} and "circular" in neg:
        score -= 16
        penalties.append("원운동 부정 조건")
    if concept_id in {"spring_potential", "energy_conservation", "rigid_body_work_energy"} and "spring" in neg:
        score -= 8
        penalties.append("스프링 없음 조건")
    # concept clue weak hits
    concept = CONCEPTS.get(concept_id, {})
    clue_blob = concept.get("problem_clues", []) + concept.get("tags", []) + [concept.get("title", "")]
    for token in norm.split():
        if len(token) >= 2 and any(token in normalize_text(x) for x in clue_blob):
            score += 1
    return score, hits, penalties


def recommend_formulas(targets: List[str], given: List[str], motion: List[str], keywords: str = "", limit: int = 5, include_excluded: bool = False) -> List[Dict[str, Any]]:
    analysis = analyze_problem_text(keywords)
    recs: List[Dict[str, Any]] = []
    excluded: List[Dict[str, Any]] = []
    for rule in FORMULA_RULES:
        score = 0
        reasons: List[str] = []
        s, hits = _overlap_score(targets, rule.get("targets", []), 5)
        score += s
        if hits:
            reasons.append(f"구하는 값 일치: {', '.join(hits)}")
        s, hits = _overlap_score(given, rule.get("given", []), 3)
        score += s
        if hits:
            reasons.append(f"주어진 값 일치: {', '.join(hits)}")
        s, hits = _overlap_score(motion, rule.get("motion", []), 5)
        score += s
        if hits:
            reasons.append(f"운동 형태 일치: {', '.join(hits)}")
        ks, khits, penalties = _keyword_hits(rule, analysis)
        score += ks
        if khits:
            reasons.append(f"문장 힌트: {', '.join(khits[:4])}")
        if "잘 모르겠다" in given or "잘 모르겠다" in motion or "미지수" in targets:
            score += 1
            reasons.append("정보가 불확실하므로 기본 점검 후보")
        rec = dict(rule)
        rec["score"] = score
        rec["matched_keywords"] = khits
        rec["penalties"] = penalties
        rec["match_reasons"] = reasons
        rec["concept"] = CONCEPTS.get(rule["concept_id"], {})
        if score > 0:
            recs.append(rec)
        elif penalties:
            rec["excluded_reason"] = f"부정 조건 감지: {', '.join(penalties)}"
            excluded.append(rec)
    recs = sorted(recs, key=lambda r: (-r["score"], r["name"]))[:limit]
    if include_excluded:
        for r in recs:
            r["excluded_candidates"] = sorted(excluded, key=lambda x: x["score"])[:3]
    return recs


def get_related_concepts(concept_id: str) -> List[Tuple[str, Dict[str, Any]]]:
    concept = CONCEPTS.get(concept_id, {})
    return [(cid, CONCEPTS[cid]) for cid in concept.get("linked", []) if cid in CONCEPTS]


def get_quizzes_for_concept(concept_id: Optional[str] = None, qtype: Optional[str] = None) -> List[Dict[str, Any]]:
    qs = MISCONCEPTION_QUIZZES
    if concept_id and concept_id != "전체":
        qs = [q for q in qs if q["concept_id"] == concept_id]
    if qtype and qtype != "전체":
        qs = [q for q in qs if q.get("type") == qtype]
    return qs


def get_formula_sense_questions(concept_id: Optional[str] = None) -> List[Dict[str, Any]]:
    if not concept_id or concept_id == "전체":
        return FORMULA_SENSE_QUESTIONS
    return [q for q in FORMULA_SENSE_QUESTIONS if q["concept_id"] == concept_id]


def _contains_any(answer: str, terms: Iterable[str]) -> List[str]:
    norm = normalize_text(answer)
    hits = []
    for term in terms:
        nt = normalize_text(term)
        if nt and (nt in norm or any(tok and tok in norm for tok in nt.split()[:2])):
            hits.append(term)
    return hits


CONTRADICTION_PATTERNS = {
    "nt_coordinates": [(r"속력.*일정.*가속도.*0", "속력이 일정해도 방향이 바뀌면 법선가속도는 존재합니다.")],
    "circular_motion": [(r"원운동.*가속도.*없", "원운동은 속력 일정이어도 방향 변화 때문에 가속도가 있습니다.")],
    "force_in_circular_motion": [(r"구심력.*새로운.*힘", "구심력은 별도의 새로운 힘이 아니라 중심방향 합력의 이름입니다.")],
    "friction": [(r"마찰.*항상.*운동.*반대", "마찰은 상대운동 또는 상대운동 경향을 막는 방향입니다. 항상 실제 운동 반대는 아닙니다.")],
    "normal_force": [(r"수직항력.*항상.*mg", "수직항력은 항상 mg가 아니라 접촉 조건과 가속도에 따라 달라집니다.")],
    "energy_conservation": [(r"마찰.*있.*보존", "마찰 같은 비보존력이 일을 하면 단순 T+V 보존은 쓸 수 없습니다.")],
    "momentum_conservation": [(r"운동에너지.*항상.*보존", "운동량이 보존되어도 운동에너지는 충돌 종류에 따라 보존되지 않을 수 있습니다.")],
}
GENERIC_BAD_PATTERNS = [
    (r"가속도.*항상.*0", "가속도는 속력 변화뿐 아니라 방향 변화로도 생깁니다."),
    (r"공식.*항상.*대입", "공식은 적용 조건이 맞을 때만 안전합니다."),
    (r"방향.*상관없", "동역학에서는 방향과 부호가 핵심입니다."),
]


def evaluate_explanation_offline(concept_id: str, user_answer: str) -> Dict[str, Any]:
    concept = CONCEPTS.get(concept_id, {})
    answer = normalize_text(user_answer)
    if not answer:
        return {"score": 0, "level": "보완 필요", "feedback": ["설명을 먼저 입력해야 합니다."], "model_answer": build_model_explanation(concept_id), "detected_errors": []}
    terms = list(dict.fromkeys(concept.get("essential_terms", []) + concept.get("tags", []) + [concept.get("title", "")]))
    when_terms = concept.get("when_to_use", []) + concept.get("problem_clues", [])
    formula_symbols = []
    for f in concept.get("formulas", []):
        formula_symbols.extend(re.findall(r"[a-zA-Z가-힣]+", f.get("latex", "")))
    term_hits = _contains_any(answer, terms)
    use_hits = _contains_any(answer, when_terms)
    formula_hits = _contains_any(answer, formula_symbols[:8])
    detected_errors: List[str] = []
    for pattern, msg in GENERIC_BAD_PATTERNS + CONTRADICTION_PATTERNS.get(concept_id, []):
        if re.search(pattern, answer):
            detected_errors.append(msg)
    score = 35
    score += min(25, len(term_hits) * 6)
    score += min(20, len(use_hits) * 6)
    score += min(10, len(formula_hits) * 2)
    if len(user_answer.strip()) >= 80:
        score += 10
    if detected_errors:
        score -= min(45, 18 * len(detected_errors))
    score = max(0, min(100, score))
    level = "좋음" if score >= 78 else "보통" if score >= 58 else "보완 필요"
    feedback = []
    if detected_errors:
        feedback.append("개념적으로 위험한 문장이 감지됐어요: " + " / ".join(detected_errors))
    if len(user_answer.strip()) < 50:
        feedback.append("설명이 짧아요. 정의 → 언제 쓰는지 → 대표 공식 의미 순서로 3문장 이상 써보세요.")
    if len(term_hits) < 2:
        feedback.append("핵심 단어가 부족해요. 카드의 제목, 태그, 대표 공식의 물리적 뜻을 넣어보세요.")
    if not use_hits:
        feedback.append("문제에서 어떤 힌트가 보이면 이 개념을 쓰는지 설명이 부족해요.")
    if score >= 78 and not detected_errors:
        feedback.append("좋아요. 이제 이 개념이 나오는 문제 상황을 직접 하나 만들어 설명해보면 더 단단해집니다.")
    return {"score": score, "level": level, "feedback": feedback, "model_answer": build_model_explanation(concept_id), "detected_errors": detected_errors, "hits": {"terms": term_hits, "uses": use_hits}}


def build_model_explanation(concept_id: str) -> str:
    c = CONCEPTS[concept_id]
    first_formula = c.get("formulas", [{}])[0]
    return (
        f"{c['title']}은/는 {c['summary']} "
        f"쉽게 말하면 {c['analogy']} 대표 공식은 {first_formula.get('latex','')}이고, "
        f"그 뜻은 {first_formula.get('meaning','')} 문제에서 {', '.join(c.get('problem_clues', [])[:4])} 같은 힌트가 보이면 이 개념을 의심하면 됩니다."
    )


def parse_numeric_answer(text: str) -> Optional[float]:
    t = normalize_text(text).replace(",", "")
    # handle fractions like 1/2
    frac = re.search(r"(-?\d+(?:\.\d+)?)\s*/\s*(-?\d+(?:\.\d+)?)", t)
    if frac:
        den = float(frac.group(2))
        if abs(den) > 1e-12:
            return float(frac.group(1)) / den
    nums = re.findall(r"-?\d+(?:\.\d+)?", t)
    if nums:
        return float(nums[0])
    words = {"절반": 0.5, "반": 0.5, "두배": 2.0, "두 배": 2.0, "네배": 4.0, "네 배": 4.0}
    for k, v in words.items():
        if k in t:
            return v
    return None


def grade_formula_sense(question: Dict[str, Any], answer: str) -> Dict[str, Any]:
    norm = normalize_text(answer)
    expected = question.get("expected_number")
    expected_dir = question.get("expected_direction")
    number = parse_numeric_answer(answer)
    negation = bool(re.search(r"아니|않|not|no", norm))
    direction_ok = True
    if expected_dir == "증가":
        direction_ok = any(w in norm for w in ["증가", "커", "크", "늘", "배", "up", "increase"]) and not any(w in norm for w in ["감소", "줄", "작"])
    elif expected_dir == "감소":
        direction_ok = any(w in norm for w in ["감소", "줄", "작", "절반", "1/2", "0.5", "half", "decrease"]) and not any(w in norm for w in ["증가", "커", "늘"])
    numeric_ok = False
    if expected is not None and number is not None:
        numeric_ok = math.isclose(float(number), float(expected), rel_tol=0.03, abs_tol=0.03)
    ok = numeric_ok and direction_ok and not negation
    return {"correct": ok, "numeric_ok": numeric_ok, "direction_ok": direction_ok, "parsed_number": number, "negation_detected": negation}


def grade_text_by_rubric(text: str, rubric: Iterable[str]) -> Tuple[int, List[str], List[str]]:
    norm = normalize_text(text)
    hits, misses = [], []
    for item in rubric:
        candidates = [normalize_text(item)] + normalize_text(item).split()
        if any(c and c in norm for c in candidates):
            hits.append(item)
        else:
            misses.append(item)
    score = int(100 * len(hits) / max(1, len(list(rubric))))
    return score, hits, misses


def check_numeric_with_unit(answer: str, expected: float, tolerance: float, unit: str) -> Dict[str, Any]:
    num = parse_numeric_answer(answer)
    unit_norm = unit.replace("²", "^2").lower()
    text = answer.lower().replace("²", "^2")
    numeric_ok = num is not None and abs(float(num) - float(expected)) <= tolerance
    unit_aliases = [unit_norm, unit_norm.replace(" ", ""), unit.replace("^2", "²").lower()]
    unit_ok = any(u and u in text.replace(" ", "") for u in unit_aliases) or (unit in ["rad/s"] and "rad" in text)
    return {"correct": bool(numeric_ok and unit_ok), "numeric_ok": bool(numeric_ok), "unit_ok": bool(unit_ok), "parsed_number": num}


def build_progress_snapshot(session_state: Dict[str, Any]) -> str:
    data = {
        "exported_at": datetime.now().isoformat(timespec="seconds"),
        "confusion_vault": list(session_state.get("confusion_vault", [])),
        "studied_concepts": list(session_state.get("studied_concepts", [])),
        "quiz_log": list(session_state.get("quiz_log", [])),
        "explain_log": list(session_state.get("explain_log", [])),
        "mastery": dict(session_state.get("mastery", {})),
    }
    return json.dumps(data, ensure_ascii=False, indent=2)


def import_progress_json(text: str) -> Dict[str, Any]:
    parsed = json.loads(text)
    warnings: List[str] = []
    # Supports both the legacy session JSON and the newer SQLite profile export.
    if isinstance(parsed, dict) and isinstance(parsed.get("progress"), dict):
        progress = parsed.get("progress", {})
        out = {
            "confusion_vault": [cid for cid, row in progress.items() if isinstance(row, dict) and row.get("confusion")],
            "studied_concepts": [cid for cid, row in progress.items() if isinstance(row, dict) and row.get("studied_count", 0) > 0],
            "quiz_log": [],
            "explain_log": [],
            "mastery": {cid: row.get("mastery", 25) for cid, row in progress.items() if isinstance(row, dict)},
        }
    else:
        allowed = {"confusion_vault", "studied_concepts", "quiz_log", "explain_log", "mastery"}
        out = {k: parsed.get(k, [] if k != "mastery" else {}) for k in allowed}
    for key in ["confusion_vault", "studied_concepts"]:
        valid, invalid = [], []
        for cid in out.get(key, []):
            if cid in CONCEPTS:
                valid.append(cid)
            else:
                invalid.append(cid)
        out[key] = list(dict.fromkeys(valid))
        if invalid:
            warnings.append(f"{key}에서 존재하지 않는 concept_id 제거: {', '.join(map(str, invalid[:5]))}")
    if isinstance(out.get("mastery"), dict):
        out["mastery"] = {cid: val for cid, val in out["mastery"].items() if cid in CONCEPTS and isinstance(val, (int, float))}
    else:
        out["mastery"] = {}
        warnings.append("mastery 형식이 잘못되어 초기화했습니다.")
    for logkey in ["quiz_log", "explain_log"]:
        cleaned = []
        for item in out.get(logkey, []):
            if isinstance(item, dict) and (not item.get("concept_id") or item.get("concept_id") in CONCEPTS):
                cleaned.append(item)
        out[logkey] = cleaned[-500:]
    out["warnings"] = warnings
    return out
