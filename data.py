from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

APP_NAME = "DynaMap"
APP_SUBTITLE = "동역학 개념카드 · 공식네비게이터 · FBD · 시험형 풀이 코치"
ROOT = Path(__file__).resolve().parents[1]
CONTENT_DIR = ROOT / "content"


def _load_json(name: str) -> Any:
    path = CONTENT_DIR / name
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


CONCEPTS: Dict[str, Dict[str, Any]] = _load_json("concepts.json")
FORMULA_RULES: List[Dict[str, Any]] = _load_json("formula_rules.json")
LEARNING_PATHS: List[Dict[str, Any]] = _load_json("learning_paths.json")
PROBLEM_BANK: List[Dict[str, Any]] = _load_json("problem_bank.json")
FBD_SCENARIOS: List[Dict[str, Any]] = _load_json("fbd_scenarios.json")

CHAPTERS = list(dict.fromkeys(c["chapter"] for c in CONCEPTS.values()))

TARGET_OPTIONS = [
    "위치", "변위", "속도", "속력", "가속도", "시간", "거리", "힘", "마찰력", "수직항력", "장력",
    "일", "운동에너지", "위치에너지", "속도 변화", "충돌 후 속도", "평균 힘", "각속도", "각가속도",
    "토크", "관성모멘트", "각운동량", "반력", "미지수",
]

GIVEN_OPTIONS = [
    "질량", "힘", "시간", "거리", "위치함수", "속도", "속력", "처음속도", "나중속도", "가속도",
    "반지름", "곡률반경", "각속도", "각가속도", "각변위", "높이", "경사각", "마찰계수", "스프링상수",
    "줄", "도르래", "막대", "바퀴", "원판", "접촉시간", "힘-시간 그래프", "힘-변위 그래프",
    "반발계수", "충돌 전후 속도", "관성모멘트", "토크", "회전축", "구속조건", "잘 모르겠다",
]

MOTION_OPTIONS = [
    "직선운동", "등가속도운동", "평면운동", "포물선운동", "곡선운동", "원운동", "극좌표운동", "상대운동",
    "힘-가속도", "경사면", "마찰", "스프링", "충돌", "진자/원호", "회전운동", "평면 강체 운동", "구름운동", "잘 모르겠다",
]

ERROR_CATEGORIES = [
    "개념 오해", "공식 선택 오류", "좌표축 오류", "부호 오류", "단위 오류", "계산 실수", "FBD 누락", "구속조건 누락",
]

DAILY_ROUTINES = [
    {
        "title": "7분 기본 루틴",
        "steps": [
            "오늘의 개념카드 1개를 읽는다.",
            "대표 공식의 문자 뜻을 소리 내어 말한다.",
            "공식네비게이터에서 이 개념이 나오는 상황을 한 번 선택해본다.",
            "퀴즈 랩에서 오개념 1개와 적용 문제 1개를 푼다.",
            "내 말로 설명에서 3문장으로 정리한다.",
        ],
    }
]


def _first_formula(concept: Dict[str, Any]) -> str:
    fs = concept.get("formulas", [])
    return fs[0].get("latex", "") if fs else ""


def _generate_quizzes() -> List[Dict[str, Any]]:
    quizzes: List[Dict[str, Any]] = []
    for cid, c in CONCEPTS.items():
        title = c["title"]
        clue = c.get("problem_clues", [title])[0]
        formula = _first_formula(c)
        quizzes.append({
            "id": f"{cid}_check",
            "concept_id": cid,
            "type": "concept_check",
            "statement": f"{title}은/는 '{c['summary']}'라고 이해할 수 있다.",
            "answer": True,
            "explanation": f"맞아요. 이 개념의 핵심은 {c['summary']}입니다. 다만 문제에서는 조건과 방향까지 함께 확인해야 합니다.",
            "error_category": "개념 오해",
        })
        mistake = c.get("common_mistakes", ["공식만 외우고 조건을 확인하지 않는 실수"])[0]
        quizzes.append({
            "id": f"{cid}_mis",
            "concept_id": cid,
            "type": "misconception",
            "statement": f"'{mistake}'라는 생각은 이 개념에서 안전한 풀이 방법이다.",
            "answer": False,
            "explanation": f"틀렸어요. 바로 그 생각이 흔한 함정입니다. {title}에서는 조건, 방향, 단위, 적용 범위를 반드시 확인해야 합니다.",
            "error_category": "개념 오해",
        })
        quizzes.append({
            "id": f"{cid}_apply",
            "concept_id": cid,
            "type": "application",
            "statement": f"문제에 '{clue}' 같은 힌트가 나오면 {title}을/를 후보 개념으로 의심해볼 수 있다.",
            "answer": True,
            "explanation": f"맞아요. '{clue}'는 {title}을/를 떠올리게 하는 대표 힌트 중 하나입니다. 단, 항상 다른 조건과 함께 판단해야 합니다.",
            "error_category": "공식 선택 오류",
        })
        if formula:
            quizzes.append({
                "id": f"{cid}_formula",
                "concept_id": cid,
                "type": "formula_meaning",
                "statement": f"{title}의 대표 공식 {formula}은/는 문자 뜻과 적용 조건을 확인하지 않고 그대로 대입해도 항상 안전하다.",
                "answer": False,
                "explanation": "틀렸어요. 공식은 조건이 맞을 때만 작동합니다. 좌표축, 방향, 단위, 어떤 물체를 계로 잡았는지를 먼저 확인해야 합니다.",
                "error_category": "공식 선택 오류",
            })
    return quizzes


MISCONCEPTION_QUIZZES = _generate_quizzes()

FORMULA_SENSE_QUESTIONS = [
    {
        "id": "nt_speed_double",
        "concept_id": "nt_coordinates",
        "formula": r"a_n=\frac{v^2}{r}",
        "question": "반지름 r이 그대로일 때 속력 v가 2배가 되면 a_n은 몇 배가 되나?",
        "expected_number": 4.0,
        "expected_unit": "배",
        "expected_direction": "증가",
        "answer": "4배",
        "explanation": "v가 제곱으로 들어가므로 2²=4배가 됩니다.",
    },
    {
        "id": "nt_radius_double",
        "concept_id": "nt_coordinates",
        "formula": r"a_n=\frac{v^2}{r}",
        "question": "속력 v가 그대로일 때 반지름 r이 2배가 되면 a_n은 몇 배가 되나?",
        "expected_number": 0.5,
        "expected_unit": "배",
        "expected_direction": "감소",
        "answer": "1/2배",
        "explanation": "r이 분모에 있으므로 반지름이 커지면 방향 전환이 완만해져 법선가속도는 줄어듭니다.",
    },
    {
        "id": "spring_x_double",
        "concept_id": "spring_potential",
        "formula": r"V_s=\frac{1}{2}kx^2",
        "question": "스프링 변형량 x가 2배가 되면 저장 에너지는 몇 배가 되나?",
        "expected_number": 4.0,
        "expected_unit": "배",
        "expected_direction": "증가",
        "answer": "4배",
        "explanation": "스프링 에너지는 x²에 비례하므로 2배 늘리면 4배가 됩니다.",
    },
    {
        "id": "ke_v_double",
        "concept_id": "kinetic_energy",
        "formula": r"T=\frac{1}{2}mv^2",
        "question": "질량이 그대로일 때 속력 v가 3배가 되면 운동에너지는 몇 배가 되나?",
        "expected_number": 9.0,
        "expected_unit": "배",
        "expected_direction": "증가",
        "answer": "9배",
        "explanation": "운동에너지는 속력의 제곱에 비례합니다. 3²=9배입니다.",
    },
    {
        "id": "impulse_time_double",
        "concept_id": "impulse",
        "formula": r"J=F_{avg}\Delta t",
        "question": "같은 운동량 변화를 만들 때 접촉 시간이 2배가 되면 평균힘은 어떻게 되나?",
        "expected_number": 0.5,
        "expected_unit": "배",
        "expected_direction": "감소",
        "answer": "1/2배",
        "explanation": "J가 같다면 F_avg와 Δt는 반비례합니다. 시간이 길어지면 평균힘은 작아집니다.",
    },
    {
        "id": "rolling_radius_half",
        "concept_id": "rolling_motion",
        "formula": r"v_G=r\omega",
        "question": "중심 속도 v_G가 같을 때 반지름 r이 1/2이 되면 각속도 ω는 몇 배가 되나?",
        "expected_number": 2.0,
        "expected_unit": "배",
        "expected_direction": "증가",
        "answer": "2배",
        "explanation": "ω=v_G/r 이므로 반지름이 절반이면 같은 속도를 위해 각속도는 2배가 됩니다.",
    },
]
