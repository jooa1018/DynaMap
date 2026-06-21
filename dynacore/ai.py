from __future__ import annotations

import os
from typing import Any, Dict, Optional


def get_api_key_from_sources(st_secrets: Optional[Dict[str, Any]] = None, override: str = "") -> Optional[str]:
    if override and override.strip():
        return override.strip()
    if st_secrets:
        try:
            value = st_secrets.get("OPENAI_API_KEY")
            if value:
                return str(value)
        except Exception:
            pass
    return os.getenv("OPENAI_API_KEY")


def _concept_context(concept: Dict[str, Any]) -> str:
    formulas = "\n".join([f"- {f.get('latex','')}: {f.get('meaning','')}" for f in concept.get("formulas", [])])
    symbols = "\n".join([f"- {k}: {v}" for k, v in concept.get("symbols", {}).items()])
    mistakes = "\n".join([f"- {m}" for m in concept.get("common_mistakes", [])])
    clues = ", ".join(concept.get("problem_clues", []))
    uses = "\n".join([f"- {u}" for u in concept.get("when_to_use", [])])
    return f"""
개념 제목: {concept.get('title','')}
단원: {concept.get('chapter','')}
요약: {concept.get('summary','')}
쉬운 비유: {concept.get('analogy','')}
대표 공식:
{formulas}
기호 뜻:
{symbols}
언제 쓰나:
{uses}
문제 힌트: {clues}
자주 하는 실수:
{mistakes}
미니 예제: {concept.get('mini_example',{}).get('problem','')} / {concept.get('mini_example',{}).get('solution','')}
""".strip()


def call_openai_feedback(api_key: str, model: str, concept: Dict[str, Any], user_answer: str) -> str:
    """Call OpenAI Responses API with the same concept context shown in the app."""
    from openai import OpenAI

    client = OpenAI(api_key=api_key)
    system = (
        "너는 한국어로 설명하는 동역학 튜터다. 학생은 물리 기초가 약하다. "
        "앱 내부 개념카드와 일관되게 평가한다. 틀린 주장은 반드시 짚되, 설명은 친절하게 한다. "
        "반드시 1) 점수 0~100, 2) 잘한 점, 3) 개념 오류/위험 문장, 4) 빠진 핵심, 5) 더 나은 답안, 6) 다음 미니문제 순서로 출력한다. "
        "수식은 LaTeX로 간결하게 쓴다."
    )
    prompt = f"""
아래 앱 내부 개념카드를 기준으로 학생 설명을 평가해줘.

[개념카드]
{_concept_context(concept)}

[학생 설명]
{user_answer}
""".strip()
    response = client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
    )
    return getattr(response, "output_text", str(response))


def call_openai_card_from_text(api_key: str, model: str, pasted_text: str) -> str:
    from openai import OpenAI

    client = OpenAI(api_key=api_key)
    system = (
        "너는 동역학 교재의 긴 설명을 초보 공대생용 개념카드로 바꾸는 전문가다. "
        "한국어로 쉽고 자세하지만 구조적으로 작성한다. "
        "반드시 다음 섹션을 포함한다: 한 줄 요약, 쉬운 비유, 핵심 공식, 기호 뜻, 언제 쓰는지, 문제 힌트, 자주 하는 실수, 1분 예제, 내 말로 설명하기 질문. "
        "불확실한 내용은 단정하지 말고 '확인 필요'라고 표시한다."
    )
    prompt = f"다음 동역학 관련 텍스트를 개념카드로 바꿔줘.\n\n{pasted_text}"
    response = client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
    )
    return getattr(response, "output_text", str(response))


def call_openai_problem_triage(api_key: str, model: str, problem_text: str, internal_recommendations: str) -> str:
    from openai import OpenAI

    client = OpenAI(api_key=api_key)
    system = (
        "너는 동역학 문제를 바로 풀기보다, 먼저 어떤 개념과 공식을 써야 하는지 진단하는 코치다. "
        "앱 내부 공식네비게이터 추천 결과를 우선 기준으로 삼고, 다르면 왜 다른지 설명한다. "
        "정답 풀이를 길게 하지 말고 문제 인식에 집중한다. 한국어로 답한다. "
        "형식: 1) 문제 속 힌트, 2) 내부 추천과의 일치/불일치, 3) 추천 개념 TOP3, 4) 후보 공식, 5) 왜 다른 공식은 아닌지, 6) 첫 풀이 행동."
    )
    prompt = f"""
[문제]
{problem_text}

[앱 내부 공식네비게이터 추천]
{internal_recommendations}
""".strip()
    response = client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
    )
    return getattr(response, "output_text", str(response))
