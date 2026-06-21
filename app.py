from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import random
from datetime import datetime
from typing import Any, Dict, List

import pandas as pd
import streamlit as st

from dynacore.ai import (
    call_openai_card_from_text,
    call_openai_feedback,
    call_openai_problem_triage,
    get_api_key_from_sources,
)
from dynacore.data import (
    APP_NAME,
    APP_SUBTITLE,
    CHAPTERS,
    CONCEPTS,
    DAILY_ROUTINES,
    ERROR_CATEGORIES,
    FBD_SCENARIOS,
    FORMULA_RULES,
    GIVEN_OPTIONS,
    LEARNING_PATHS,
    MOTION_OPTIONS,
    PROBLEM_BANK,
    TARGET_OPTIONS,
)
from dynacore.engine import (
    build_progress_snapshot,
    check_numeric_with_unit,
    evaluate_explanation_offline,
    get_formula_sense_questions,
    get_quizzes_for_concept,
    get_related_concepts,
    grade_formula_sense,
    grade_text_by_rubric,
    import_progress_json,
    recommend_formulas,
    search_concepts,
)
from dynacore.progress import (
    due_reviews,
    export_profile,
    get_confusion_ids,
    get_progress,
    init_db,
    log_explanation,
    log_quiz,
    mark_studied,
    merge_imported_progress,
    new_profile_id,
    recent_events,
    set_confusion,
)
from dynacore.visuals import (
    circular_motion_figure,
    collision_figure,
    concept_mastery_bar,
    energy_bar_figure,
    incline_fbd_figure,
    pulley_figure,
    rolling_figure,
)

st.set_page_config(page_title="DynaMap", page_icon="🧭", layout="wide", initial_sidebar_state="expanded")


def load_css() -> None:
    try:
        with open("assets/style.css", "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        pass


def init_state() -> None:
    init_db()
    defaults = {
        "selected_concept": "nt_coordinates",
        "api_key_override": "",
        "model_name": "gpt-4.1-mini",
        "page_mode": "대시보드",
        "quiz_filter_key": "전체|전체|오개념 O/X",
        "profile_id": new_profile_id(),
        "profile_name": "내 학습 기록",
        "studied_concepts": [],
        "confusion_vault": [],
        "quiz_log": [],
        "explain_log": [],
        "mastery": {},
    }
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)
    sync_session_from_db()


def sync_session_from_db() -> None:
    profile = st.session_state.get("profile_id")
    progress = get_progress(profile)
    st.session_state.confusion_vault = [cid for cid, row in progress.items() if row.get("confusion")]
    st.session_state.studied_concepts = [cid for cid, row in progress.items() if row.get("studied_count", 0) > 0]
    st.session_state.mastery = {cid: row.get("mastery", 25) for cid, row in progress.items()}


def pill(text: str) -> str:
    return f"<span class='pill'>{text}</span>"


def section_header(title: str, caption: str = "") -> None:
    st.markdown(f"<div class='section-title'>{title}</div>", unsafe_allow_html=True)
    if caption:
        st.caption(caption)


def add_studied(concept_id: str) -> None:
    mark_studied(st.session_state.profile_id, concept_id)
    sync_session_from_db()


def add_confusion(concept_id: str) -> None:
    set_confusion(st.session_state.profile_id, concept_id, True)
    sync_session_from_db()
    st.toast(f"'{CONCEPTS[concept_id]['title']}' 헷갈림 목록에 추가했어요.")


def remove_confusion(concept_id: str) -> None:
    set_confusion(st.session_state.profile_id, concept_id, False)
    sync_session_from_db()
    st.toast(f"'{CONCEPTS[concept_id]['title']}' 헷갈림 목록에서 뺐어요.")


def render_formula_latex(formula: str, caption: str = "") -> None:
    with st.container(border=True):
        st.latex(formula)
        if caption:
            st.write(caption)


def render_formula(formula: Dict[str, str]) -> None:
    render_formula_latex(formula.get("latex", ""), formula.get("meaning", ""))


def concept_selectbox(label: str, key: str, default: str | None = None) -> str:
    ids = list(CONCEPTS.keys())
    default = default if default in ids else st.session_state.get("selected_concept", ids[0])
    idx = ids.index(default) if default in ids else 0
    return st.selectbox(label, ids, index=idx, format_func=lambda cid: CONCEPTS[cid]["title"], key=key)


def render_concept_card(concept_id: str, compact: bool = False) -> None:
    c = CONCEPTS[concept_id]
    add_studied(concept_id)
    mastery = st.session_state.mastery.get(concept_id, 25)

    st.markdown(
        f"""
        <div class="hero-card">
            <div class="kicker">{c['chapter']} · 난이도 {'★' * c['level']}{'☆' * (5-c['level'])} · 약 {c['time_min']}분 · 숙련도 {mastery:.0f}/100</div>
            <h2>{c['title']}</h2>
            <p>{c['summary']}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    top_cols = st.columns([1.1, 1])
    with top_cols[0]:
        section_header("쉬운 비유")
        st.info(c.get("analogy", ""))
        section_header("언제 쓰나?")
        st.markdown("\n".join([f"- {x}" for x in c.get("when_to_use", [])]))
    with top_cols[1]:
        section_header("문제에서 보이는 힌트")
        st.markdown(" ".join([pill(x) for x in c.get("problem_clues", [])]), unsafe_allow_html=True)
        section_header("대표 공식")
        for f in c.get("formulas", [])[:2 if compact else None]:
            render_formula(f)

    if compact:
        return

    tab1, tab2, tab3, tab4 = st.tabs(["기호·실수", "미니 예제", "연결 개념", "퀴즈 바로가기"])
    with tab1:
        sym_df = pd.DataFrame([{"기호": k, "뜻": v} for k, v in c.get("symbols", {}).items()])
        if not sym_df.empty:
            st.dataframe(sym_df, use_container_width=True, hide_index=True)
        for m in c.get("common_mistakes", []):
            st.warning(m, icon="⚠️")
    with tab2:
        ex = c.get("mini_example", {})
        st.write(f"**문제**: {ex.get('problem', '')}")
        with st.expander("풀이 보기"):
            st.write(ex.get("solution", ""))
    with tab3:
        rel = get_related_concepts(concept_id)
        if rel:
            cols = st.columns(min(4, len(rel)))
            for idx, (rid, rc) in enumerate(rel):
                with cols[idx % len(cols)]:
                    if st.button(rc["title"], key=f"related_{concept_id}_{rid}", use_container_width=True):
                        st.session_state.selected_concept = rid
                        st.rerun()
        else:
            st.info("등록된 연결 개념이 아직 없습니다.")
    with tab4:
        q_count = len(get_quizzes_for_concept(concept_id))
        st.write(f"이 개념에는 자동/수동 퀴즈가 **{q_count}개** 연결되어 있어요.")
        if st.button("이 개념 퀴즈 풀러 가기", use_container_width=True):
            st.session_state.page_mode = "퀴즈 랩"
            st.session_state.quiz_preselect = concept_id
            st.rerun()

    st.divider()
    b1, b2, b3, b4 = st.columns(4)
    with b1:
        if st.button("헷갈림 목록에 추가", key=f"confuse_{concept_id}", use_container_width=True):
            add_confusion(concept_id)
    with b2:
        if st.button("공식네비게이터로 연결", key=f"to_nav_{concept_id}", use_container_width=True):
            st.session_state.nav_keyword_seed = " ".join(c.get("problem_clues", [])[:5])
            st.session_state.page_mode = "공식네비게이터"
            st.rerun()
    with b3:
        if st.button("30초 설명 연습", key=f"to_explain_{concept_id}", use_container_width=True):
            st.session_state.explain_concept = concept_id
            st.session_state.page_mode = "내 말로 설명"
            st.rerun()
    with b4:
        if st.button("FBD/풀이 훈련", key=f"to_solver_{concept_id}", use_container_width=True):
            st.session_state.page_mode = "시험형 풀이 모드"
            st.rerun()


def page_dashboard(api_key: str | None) -> None:
    st.markdown(
        f"""
        <div class="title-wrap">
          <div class="app-logo">🧭</div>
          <div>
            <h1>{APP_NAME}</h1>
            <p>{APP_SUBTITLE}</p>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    progress = get_progress(st.session_state.profile_id)
    due = due_reviews(st.session_state.profile_id)
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("개념카드", f"{len(CONCEPTS)}개")
    c2.metric("공식 규칙", f"{len(FORMULA_RULES)}개")
    c3.metric("헷갈림", f"{len(st.session_state.confusion_vault)}개")
    c4.metric("복습 예정", f"{len(due)}개")
    c5.metric("AI 코치", "ON" if api_key else "OFF")

    st.info("DynaMap은 개념카드만 보는 앱이 아니라, 공식 선택 → FBD → 단계별 풀이 → 복습 기록까지 연결하는 동역학 학습 코치입니다.")

    left, right = st.columns([1.2, 1])
    with left:
        section_header("오늘의 7분 루틴")
        routine = DAILY_ROUTINES[0]
        with st.container(border=True):
            st.subheader(routine["title"])
            for i, step in enumerate(routine["steps"], start=1):
                st.write(f"{i}. {step}")
        section_header("빠른 개념카드")
        quick = concept_selectbox("오늘 볼 개념", "dash_quick", st.session_state.selected_concept)
        st.session_state.selected_concept = quick
        render_concept_card(quick, compact=True)
    with right:
        section_header("복습/헷갈림")
        if due:
            st.write("**오늘 다시 보면 좋은 개념**")
            for cid in due:
                if st.button(CONCEPTS[cid]["title"], key=f"due_{cid}", use_container_width=True):
                    st.session_state.selected_concept = cid
                    st.session_state.page_mode = "개념카드"
                    st.rerun()
        if not st.session_state.confusion_vault:
            st.success("헷갈림 목록이 비어 있어요. 어려운 개념은 카드에서 저장해두면 자동 복습에 반영됩니다.")
        else:
            for cid in st.session_state.confusion_vault[:8]:
                with st.container(border=True):
                    st.write(f"**{CONCEPTS[cid]['title']}**")
                    st.caption(CONCEPTS[cid]["summary"])
                    b1, b2 = st.columns(2)
                    if b1.button("복습", key=f"dash_review_{cid}", use_container_width=True):
                        st.session_state.selected_concept = cid
                        st.session_state.page_mode = "개념카드"
                        st.rerun()
                    if b2.button("해제", key=f"dash_clear_{cid}", use_container_width=True):
                        remove_confusion(cid)
                        st.rerun()


def page_learning_path() -> None:
    section_header("학습 경로", "초보자가 길을 잃지 않도록 개념 선후관계를 순서로 보여줍니다.")
    path = st.selectbox("경로 선택", LEARNING_PATHS, format_func=lambda p: p["name"])
    st.caption(path["description"])
    progress = get_progress(st.session_state.profile_id)
    for idx, cid in enumerate(path["concept_ids"], 1):
        c = CONCEPTS[cid]
        mastery = progress.get(cid, {}).get("mastery", 25)
        with st.container(border=True):
            cols = st.columns([0.15, 0.6, 0.25])
            cols[0].markdown(f"### {idx}")
            cols[1].write(f"**{c['title']}**")
            cols[1].caption(c["summary"])
            cols[2].progress(int(mastery), text=f"숙련도 {mastery:.0f}/100")
            if st.button("이 개념 보기", key=f"path_{path['name']}_{cid}"):
                st.session_state.selected_concept = cid
                st.session_state.page_mode = "개념카드"
                st.rerun()


def page_concept_map() -> None:
    section_header("개념 맵", "개념이 서로 어떻게 이어지는지 봅니다.")
    mode = st.radio("보기", ["전체 흐름", "선택 개념 주변"], horizontal=True)
    if mode == "선택 개념 주변":
        cid = concept_selectbox("중심 개념", "map_center", st.session_state.selected_concept)
        nodes = [cid] + [x for x in CONCEPTS[cid].get("linked", []) if x in CONCEPTS]
    else:
        nodes = list(CONCEPTS.keys())
    lines = ["digraph G {", 'rankdir=LR;', 'node [shape=box, style="rounded,filled", fillcolor="#F7F7F7", fontname="Arial"];']
    for cid in nodes:
        lines.append(f'"{CONCEPTS[cid]["title"]}";')
    for cid in nodes:
        for lid in CONCEPTS[cid].get("linked", []):
            if lid in CONCEPTS and lid in nodes:
                lines.append(f'"{CONCEPTS[cid]["title"]}" -> "{CONCEPTS[lid]["title"]}";')
    lines.append("}")
    st.graphviz_chart("\n".join(lines), use_container_width=True)
    st.caption("화살표는 이 개념을 공부할 때 같이 보거나 선행으로 보면 좋은 개념을 뜻합니다.")


def page_concept_cards() -> None:
    section_header("개념카드", "긴 교재 설명을 짧은 구조로 쪼개서 봅니다.")
    left, right = st.columns([0.9, 2.1])
    with left:
        chapter = st.selectbox("단원", ["전체"] + CHAPTERS)
        query = st.text_input("검색", placeholder="예: 원운동, 마찰, 에너지, 충돌")
        results = search_concepts(query, None if chapter == "전체" else chapter)
        concept_ids = [cid for cid, _, _ in results]
        if not concept_ids:
            st.warning("검색 결과가 없어요. 다른 단어로 찾아보세요.")
            return
        current = st.session_state.selected_concept if st.session_state.selected_concept in concept_ids else concept_ids[0]
        chosen = st.radio("개념 선택", concept_ids, format_func=lambda cid: CONCEPTS[cid]["title"], index=concept_ids.index(current))
        st.session_state.selected_concept = chosen
    with right:
        render_concept_card(st.session_state.selected_concept)


def page_formula_navigator() -> None:
    section_header("공식네비게이터", "문제 상황을 선택하면 공식 후보와 연결 개념을 추천합니다. 부정 표현도 함께 봅니다.")
    with st.container(border=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            targets = st.multiselect("무엇을 구하나요?", TARGET_OPTIONS, default=[])
        with col2:
            given = st.multiselect("무엇이 주어졌나요?", GIVEN_OPTIONS, default=[])
        with col3:
            motion = st.multiselect("운동 형태는?", MOTION_OPTIONS, default=[])
        default_kw = st.session_state.pop("nav_keyword_seed", "") if "nav_keyword_seed" in st.session_state else ""
        keywords = st.text_area("문제의 핵심 문장/힌트 단어", value=default_kw, placeholder="예: frictionless circular path, radius 50 m, speed 20 m/s")
        limit = st.slider("추천 개수", 1, 8, 5)
    recs = recommend_formulas(targets, given, motion, keywords, limit=limit, include_excluded=True)
    if not recs:
        st.warning("아직 추천할 만큼 정보가 부족해요. 구하는 값/주어진 값/운동 형태 중 하나 이상 선택해보세요.")
        return
    for i, rec in enumerate(recs, start=1):
        concept = rec["concept"]
        with st.container(border=True):
            st.markdown(f"### {i}. {rec['name']}  ·  점수 {rec['score']}")
            st.caption(f"연결 개념: {concept.get('title', rec['concept_id'])} · {concept.get('chapter', '')}")
            st.write(f"**왜 이걸 의심하나?** {rec['reason']}")
            if rec.get("match_reasons"):
                st.write("**매칭 근거**: " + " / ".join(rec["match_reasons"]))
            fcols = st.columns(min(3, max(1, len(rec.get("formulas", [])))))
            for idx, formula in enumerate(rec.get("formulas", [])):
                with fcols[idx % len(fcols)]:
                    st.latex(formula)
            with st.expander("체크포인트와 제외 이유"):
                st.write("**확인할 것**")
                for cp in rec.get("checkpoints", []):
                    st.write(f"- {cp}")
                if rec.get("not_recommended_when"):
                    st.write("**이 공식이 아닐 수 있는 경우**")
                    for x in rec["not_recommended_when"]:
                        st.write(f"- {x}")
                excluded = rec.get("excluded_candidates", [])
                if excluded:
                    st.write("**부정 조건 때문에 제외된 후보**")
                    for ex in excluded:
                        st.write(f"- {ex['name']}: {ex.get('excluded_reason', '조건 불일치')}")
            if st.button("관련 개념카드 보기", key=f"nav_concept_{rec['concept_id']}_{i}"):
                st.session_state.selected_concept = rec["concept_id"]
                st.session_state.page_mode = "개념카드"
                st.rerun()


def page_quiz_lab() -> None:
    section_header("퀴즈 랩", "각 개념마다 개념 확인, 오개념, 적용 퀴즈가 연결됩니다.")
    mode = st.radio("훈련 모드", ["오개념 O/X", "공식 감각 질문"], horizontal=True)
    pre = st.session_state.pop("quiz_preselect", "전체") if "quiz_preselect" in st.session_state else "전체"
    ids = ["전체"] + list(CONCEPTS.keys())
    idx = ids.index(pre) if pre in ids else 0
    concept_filter = st.selectbox("개념 필터", ids, format_func=lambda cid: "전체" if cid == "전체" else CONCEPTS[cid]["title"], index=idx)
    qtype = "전체"
    if mode == "오개념 O/X":
        qtype = st.selectbox("퀴즈 종류", ["전체", "concept_check", "misconception", "application", "formula_meaning"], format_func=lambda x: {"concept_check":"개념 확인", "misconception":"오개념", "application":"적용", "formula_meaning":"공식 의미"}.get(x, x))
    filter_key = f"{concept_filter}|{qtype}|{mode}"
    if filter_key != st.session_state.get("quiz_filter_key"):
        for k in ["current_mis_q", "current_sense_q", "sense_answer"]:
            st.session_state.pop(k, None)
        st.session_state.quiz_filter_key = filter_key

    if mode == "오개념 O/X":
        qs = get_quizzes_for_concept(None if concept_filter == "전체" else concept_filter, qtype=qtype)
        st.caption(f"현재 필터 문제 수: {len(qs)}개")
        if not qs:
            st.info("이 필터에는 퀴즈가 없어요.")
            return
        if st.button("랜덤 문제 뽑기") or "current_mis_q" not in st.session_state:
            st.session_state.current_mis_q = random.choice(qs)
        q = st.session_state.current_mis_q
        with st.container(border=True):
            st.subheader("다음 문장은 맞을까?")
            st.write(f"### {q['statement']}")
            col1, col2 = st.columns(2)
            user = None
            if col1.button("맞다", use_container_width=True):
                user = True
            if col2.button("틀리다", use_container_width=True):
                user = False
            if user is not None:
                correct = user == q["answer"]
                log_quiz(st.session_state.profile_id, q["concept_id"], correct, q.get("type", "ox"), q.get("error_category", "개념 오해"), payload=q)
                sync_session_from_db()
                if correct:
                    st.success("정답! 감을 잘 잡았어요.")
                else:
                    st.error("아쉽지만 틀렸어요. 이게 자주 나오는 함정입니다.")
                    add_confusion(q["concept_id"])
                st.write(q["explanation"])
                st.caption(f"연결 개념: {CONCEPTS[q['concept_id']]['title']} · 오답 유형: {q.get('error_category','')}")
    else:
        qs = get_formula_sense_questions(None if concept_filter == "전체" else concept_filter)
        if not qs:
            st.info("이 개념에는 아직 공식 감각 질문이 없어요. 전체로 바꿔보세요.")
            return
        if st.button("랜덤 질문 뽑기") or "current_sense_q" not in st.session_state:
            st.session_state.current_sense_q = random.choice(qs)
            st.session_state.sense_answer = ""
        q = st.session_state.current_sense_q
        with st.container(border=True):
            st.subheader(CONCEPTS[q["concept_id"]]["title"])
            st.latex(q["formula"])
            answer = st.text_input(q["question"], key="sense_answer")
            if st.button("채점"):
                result = grade_formula_sense(q, answer)
                ok = result["correct"]
                log_quiz(st.session_state.profile_id, q["concept_id"], ok, "formula_sense", "공식 선택 오류", payload={"question": q, "grade": result})
                sync_session_from_db()
                if ok:
                    st.success("좋아요. 숫자와 증가/감소 방향을 모두 제대로 봤어요.")
                else:
                    st.warning(f"핵심 답: {q['answer']}")
                    st.write(f"숫자 판정: {result['numeric_ok']}, 방향 판정: {result['direction_ok']}, 부정 표현 감지: {result['negation_detected']}")
                    add_confusion(q["concept_id"])
                st.write(q["explanation"])


def render_offline_feedback(result: Dict[str, Any]) -> None:
    st.metric("오프라인 점수", f"{result['score']}점", result["level"])
    for f in result["feedback"]:
        st.write(f"- {f}")
    with st.expander("모범 설명 예시"):
        st.write(result["model_answer"])


def page_explain(api_key: str | None, model_name: str) -> None:
    section_header("내 말로 설명", "AI가 없어도 오개념 탐지와 필수 관계 검사를 먼저 수행합니다.")
    default = st.session_state.get("explain_concept", st.session_state.selected_concept)
    cid = concept_selectbox("설명할 개념", "explain_concept_select", default)
    c = CONCEPTS[cid]
    st.info(c.get("explain_prompt", f"{c['title']}을 네 말로 설명해봐."))
    with st.expander("API 사용 개인정보 안내", expanded=bool(api_key)):
        st.write("AI 코치를 켜면 네가 입력한 설명과 해당 개념카드 정보가 OpenAI API로 전송됩니다. API 키는 앱 코드나 GitHub에 저장하지 말고 Streamlit Secrets 또는 환경변수로 넣는 방식을 권장합니다. AI 코치를 끄면 외부 API 전송 없이 오프라인 채점만 수행합니다.")
    answer = st.text_area("내 설명", height=180, placeholder="예: n-t 좌표계는 곡선 운동에서 가속도를 접선방향과 법선방향으로 나눠서 보는 방법이다...")
    use_ai = st.toggle("AI 코치로 추가 첨삭", value=False, disabled=not bool(api_key), help="오프라인 채점 후 AI 피드백을 추가로 받습니다.")
    if st.button("설명 채점하기", type="primary"):
        if not answer.strip():
            st.warning("먼저 네 설명을 입력해줘.")
            return
        result = evaluate_explanation_offline(cid, answer)
        render_offline_feedback(result)
        log_explanation(st.session_state.profile_id, cid, result["score"], "offline", payload={"detected_errors": result.get("detected_errors", [])})
        sync_session_from_db()
        if use_ai and api_key:
            try:
                with st.spinner("AI 코치가 앱 내부 개념카드를 기준으로 설명을 읽고 있어요..."):
                    fb = call_openai_feedback(api_key, model_name, c, answer)
                st.markdown("### AI 코치 피드백")
                st.markdown(fb)
                log_explanation(st.session_state.profile_id, cid, result["score"], "ai", payload={"used_ai": True})
            except Exception as e:
                st.error(f"AI 호출에 실패했어요: {e}")


def page_fbd_trainer() -> None:
    section_header("FBD 트레이너", "힘을 직접 고르고 방향·좌표축·방정식을 점검합니다.")
    scenario = st.selectbox("상황 선택", FBD_SCENARIOS, format_func=lambda s: s["title"])
    st.info(scenario["situation"])
    if scenario["id"] == "incline_down":
        st.plotly_chart(incline_fbd_figure(), use_container_width=True)
    elif scenario["id"] == "hanging_mass":
        st.plotly_chart(pulley_figure(), use_container_width=True)
    elif scenario["id"] == "circular_car":
        st.plotly_chart(circular_motion_figure(10, 30, 0), use_container_width=True)
    else:
        st.caption("그림이 단순화되어 있어도 실제 풀이에서는 반드시 물체 하나만 분리해서 힘을 그려야 합니다.")
    choices = scenario["correct_forces"] + scenario.get("optional_forces", []) + ["가속도 ma", "구심력이라는 별도 힘", "운동방향 힘 없음"]
    selected = st.multiselect("FBD에 그릴 힘을 선택", choices)
    axis = st.text_input("좌표축을 어떻게 잡을까?", placeholder=scenario["axis"])
    equation = st.text_area("운동방정식 또는 모멘트방정식을 써봐", placeholder="예: ΣFx=P-f=ma, ΣFy=N-mg=0")
    if st.button("FBD 점검", type="primary"):
        correct = set(scenario["correct_forces"])
        sel = set(selected)
        missing = sorted(correct - sel)
        extra = sorted(sel - correct - set(scenario.get("optional_forces", [])))
        axis_score, axis_hits, axis_miss = grade_text_by_rubric(axis, scenario["axis"].split())
        eq_rubric = []
        for eq in scenario["equations"]:
            eq_rubric += [x for x in ["sum", "Σ", "F", "M", "ma", "I", "alpha", "mg", "N", "f"] if x in eq or x.replace("alpha", "\\alpha") in eq]
        eq_score, _, _ = grade_text_by_rubric(equation, eq_rubric or ["F", "ma"])
        force_ok = not missing and not extra
        total = int((55 if force_ok else max(0, 55 - 15 * len(missing) - 10 * len(extra))) + 0.2 * axis_score + 0.25 * eq_score)
        st.metric("FBD 점수", f"{max(0,min(100,total))}점")
        if missing:
            st.error("빠진 힘: " + ", ".join(missing))
        if extra:
            st.warning("불필요하거나 위험한 항목: " + ", ".join(extra))
        if not missing and not extra:
            st.success("힘 목록은 좋아요. 이제 방향과 방정식 부호를 확인하면 됩니다.")
        st.write("**권장 좌표축**: " + scenario["axis"])
        st.write("**대표 방정식**")
        for eq in scenario["equations"]:
            st.latex(eq)
        cid = scenario["concept_ids"][0]
        log_quiz(st.session_state.profile_id, cid, force_ok and total >= 70, "fbd", "FBD 누락" if missing else "좌표축 오류", payload={"scenario": scenario["id"], "missing": missing, "extra": extra})
        sync_session_from_db()


def page_solver() -> None:
    section_header("시험형 풀이 모드", "문제 제시 → 물체 선택 → FBD → 좌표축 → 방정식 → 계산 → 단위 검산 순서로 훈련합니다.")
    problem = st.selectbox("문제 선택", PROBLEM_BANK, format_func=lambda p: f"[{p['level']}단계] {p['title']}")
    st.markdown(f"### {problem['statement']}")
    with st.expander("주어진 값"):
        st.json(problem.get("givens", {}))
    for cid in problem.get("concept_ids", []):
        st.markdown(pill(CONCEPTS[cid]["title"]), unsafe_allow_html=True)

    st.divider()
    for idx, step in enumerate(problem["steps"], 1):
        with st.container(border=True):
            st.subheader(f"{idx}. {step['name']}")
            st.write(step["prompt"])
            ans = st.text_input("내 답", key=f"solver_{problem['id']}_{idx}")
            if st.button("이 단계 점검", key=f"check_solver_{problem['id']}_{idx}"):
                if "numeric_answer" in step:
                    result = check_numeric_with_unit(ans, step["numeric_answer"], step.get("tolerance", 0.01), step.get("unit", ""))
                    if result["correct"]:
                        st.success("계산값과 단위가 모두 맞아요.")
                    else:
                        st.warning(f"점검: 숫자 {result['numeric_ok']}, 단위 {result['unit_ok']}, 읽은 값 {result['parsed_number']}")
                    ok = result["correct"]
                else:
                    score, hits, misses = grade_text_by_rubric(ans, step.get("rubric", []))
                    st.metric("단계 점수", f"{score}점")
                    if misses:
                        st.warning("빠진 핵심: " + ", ".join(misses))
                    ok = score >= 60
                with st.expander("모범 답안"):
                    st.write(step["answer"])
                log_quiz(st.session_state.profile_id, problem["concept_ids"][0], ok, "solver", "단위 오류" if "numeric_answer" in step and not ok else "공식 선택 오류", payload={"problem": problem["id"], "step": step["name"]})
                sync_session_from_db()
    with st.expander("이 문제에서 자주 하는 실수"):
        for e in problem.get("common_errors", []):
            st.write(f"- {e}")


def page_visual_lab() -> None:
    section_header("시각화 랩", "원운동, 경사면 FBD, 도르래, 충돌, 구름운동, 에너지 감각을 눈으로 확인합니다.")
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["원운동", "경사면 FBD", "도르래", "충돌", "구름운동", "에너지"])
    with tab1:
        c1, c2, c3 = st.columns(3)
        v = c1.slider("속력 v (m/s)", 0.0, 40.0, 10.0, 0.5)
        r = c2.slider("반지름 r (m)", 0.5, 100.0, 20.0, 0.5)
        at = c3.slider("접선가속도 a_t (m/s²)", -10.0, 10.0, 0.0, 0.5)
        st.plotly_chart(circular_motion_figure(v, r, at), use_container_width=True)
        st.info("속력 v를 2배로 키우면 법선가속도 aₙ은 4배가 됩니다. 반지름 r이 커지면 aₙ은 작아집니다.")
    with tab2:
        theta = st.slider("경사각 θ", 5, 60, 30)
        friction = st.toggle("마찰 표시", value=True)
        st.plotly_chart(incline_fbd_figure(theta, friction), use_container_width=True)
    with tab3:
        st.plotly_chart(pulley_figure(), use_container_width=True)
        st.caption("줄 장력은 같은 줄/이상적 도르래 조건에서 같게 둘 수 있습니다. 실제 문제 조건을 먼저 확인하세요.")
    with tab4:
        v1 = st.slider("v1", -10.0, 10.0, 5.0)
        v2 = st.slider("v2", -10.0, 10.0, 0.0)
        st.plotly_chart(collision_figure(v1, v2), use_container_width=True)
    with tab5:
        rr = st.slider("바퀴 반지름", 0.1, 2.0, 0.5)
        omega = st.slider("각속도 ω", 0.0, 30.0, 8.0)
        st.plotly_chart(rolling_figure(rr, omega), use_container_width=True)
    with tab6:
        e1, e2, e3, e4, e5 = st.columns(5)
        T1 = e1.number_input("T1", value=0.0)
        V1 = e2.number_input("V1", value=10.0)
        Unc = e3.number_input("U_nc", value=0.0)
        T2 = e4.number_input("T2", value=10.0)
        V2 = e5.number_input("V2", value=0.0)
        st.plotly_chart(energy_bar_figure(T1, V1, Unc, T2, V2), use_container_width=True)


def page_ai_tools(api_key: str | None, model_name: str) -> None:
    section_header("AI 확장 도구", "AI는 내부 엔진을 대체하지 않고 보조합니다.")
    st.warning("AI 기능을 사용하면 입력한 교재 텍스트/문제 문장과 앱 내부 추천 정보가 OpenAI API로 전송됩니다. 민감한 개인정보나 API 키를 본문에 넣지 마세요.")
    if not api_key:
        st.info("사이드바에서 API 키를 입력하거나 Streamlit Secrets에 `OPENAI_API_KEY`를 설정하면 사용할 수 있어요. API 없이도 개념카드, 추천 엔진, 퀴즈, FBD, 풀이 모드는 작동합니다.")
        return
    tab1, tab2 = st.tabs(["긴 글 → 개념카드", "문제 → 내부 추천 + AI 진단"])
    with tab1:
        text = st.text_area("교재/강의 노트 일부를 붙여넣기", height=220)
        if st.button("개념카드로 압축", type="primary"):
            if not text.strip():
                st.warning("텍스트를 먼저 붙여넣어줘.")
            else:
                try:
                    with st.spinner("긴 글을 개념카드로 바꾸는 중..."):
                        out = call_openai_card_from_text(api_key, model_name, text)
                    st.markdown(out)
                except Exception as e:
                    st.error(f"AI 호출 실패: {e}")
    with tab2:
        problem = st.text_area("동역학 문제 문장을 붙여넣기", height=220)
        if st.button("개념/공식 진단", type="primary"):
            if not problem.strip():
                st.warning("문제 문장을 먼저 붙여넣어줘.")
            else:
                recs = recommend_formulas([], [], [], problem, limit=5, include_excluded=True)
                summary = "\n".join([f"- {r['name']} / {CONCEPTS[r['concept_id']]['title']} / {', '.join(r['formulas'])}" for r in recs]) or "추천 없음"
                st.write("### 내부 공식네비게이터 추천")
                for r in recs:
                    st.write(f"- **{r['name']}** → {CONCEPTS[r['concept_id']]['title']}")
                try:
                    with st.spinner("AI가 내부 추천 결과와 문제 문장을 함께 분석하는 중..."):
                        out = call_openai_problem_triage(api_key, model_name, problem, summary)
                    st.markdown("### AI 진단")
                    st.markdown(out)
                except Exception as e:
                    st.error(f"AI 호출 실패: {e}")


def page_report() -> None:
    section_header("학습 리포트", "숙련도, 약점, 오답 유형, 복습 예정 개념을 확인합니다.")
    progress = get_progress(st.session_state.profile_id)
    rows = []
    for cid, c in CONCEPTS.items():
        row = progress.get(cid, {})
        rows.append({"concept_id": cid, "title": c["title"], "chapter": c["chapter"], "mastery": float(row.get("mastery", 25)), "correct": int(row.get("correct_count", 0)), "wrong": int(row.get("wrong_count", 0)), "confusion": bool(row.get("confusion", 0)), "next_review_at": row.get("next_review_at", "")})
    df = pd.DataFrame(rows)
    c1, c2, c3 = st.columns(3)
    c1.metric("평균 숙련도", f"{df['mastery'].mean():.0f}/100")
    c2.metric("약점 개념", f"{(df['mastery']<45).sum()}개")
    c3.metric("헷갈림", f"{df['confusion'].sum()}개")
    weak = df.sort_values(["mastery", "wrong"], ascending=[True, False]).head(10)
    st.plotly_chart(concept_mastery_bar(weak.to_dict("records")), use_container_width=True)
    st.write("### 약점 TOP 10")
    st.dataframe(weak[["title", "chapter", "mastery", "correct", "wrong", "confusion", "next_review_at"]], use_container_width=True, hide_index=True)
    st.write("### 최근 기록")
    events = recent_events(st.session_state.profile_id, 50)
    if events:
        ev_df = pd.DataFrame(events)
        if "payload_json" in ev_df:
            ev_df = ev_df.drop(columns=["payload_json"])
        st.dataframe(ev_df, use_container_width=True, hide_index=True)
    else:
        st.info("아직 기록이 없습니다.")


def page_data_manager() -> None:
    section_header("기록 관리", "SQLite 자동 저장 + JSON 내보내기/가져오기를 함께 제공합니다.")
    st.write(f"현재 프로필 ID: `{st.session_state.profile_id}`")
    st.caption("Streamlit Community Cloud에서는 서버 재시작/재배포 시 로컬 SQLite 파일이 초기화될 수 있습니다. 중요한 기록은 JSON으로 백업하세요.")
    c1, c2 = st.columns(2)
    with c1:
        st.download_button("현재 학습 기록 JSON 다운로드", data=export_profile(st.session_state.profile_id), file_name="dynamap_progress_export.json", mime="application/json")
        st.download_button("구버전 호환 JSON 다운로드", data=build_progress_snapshot(st.session_state), file_name="dynamap_legacy_progress.json", mime="application/json")
    with c2:
        uploaded = st.file_uploader("학습 기록 JSON 가져오기", type=["json"])
        if uploaded is not None:
            text = uploaded.read().decode("utf-8")
            try:
                data = import_progress_json(text)
                warnings = data.pop("warnings", [])
                warnings += merge_imported_progress(st.session_state.profile_id, data)
                sync_session_from_db()
                st.success("가져오기를 완료했어요.")
                for w in warnings:
                    st.warning(w)
            except Exception as e:
                st.error(f"가져오기 실패: {e}")



# -----------------------------------------------------------------------------
# DynaMap v3 UI/UX layer
# 전문가 UI 피드백 반영: 큰 메뉴 6개, 오늘의 학습 홈, 단계형 풀이, 가벼운 개념카드,
# FBD 핵심화, 시각화 통합, 일관된 디자인 시스템.
# -----------------------------------------------------------------------------

MAIN_PAGES = ["홈", "개념", "문제", "복습", "리포트", "설정"]
PAGE_ICONS = {
    "홈": "🏠",
    "개념": "🧠",
    "문제": "🧩",
    "복습": "🔁",
    "리포트": "📊",
    "설정": "⚙️",
}


def safe_page(page: str) -> str:
    if page in MAIN_PAGES:
        return page
    legacy_map = {
        "대시보드": "홈",
        "학습 경로": "개념",
        "개념 맵": "개념",
        "개념카드": "개념",
        "시각화 랩": "개념",
        "공식네비게이터": "문제",
        "FBD 트레이너": "문제",
        "시험형 풀이 모드": "문제",
        "퀴즈 랩": "복습",
        "내 말로 설명": "복습",
        "학습 리포트": "리포트",
        "기록 관리": "설정",
        "AI 확장 도구": "설정",
    }
    return legacy_map.get(page, "홈")


def init_state() -> None:
    init_db()
    defaults = {
        "selected_concept": "nt_coordinates",
        "api_key_override": "",
        "model_name": "gpt-4.1-mini",
        "page_mode": "홈",
        "concept_submode": "개념카드",
        "problem_submode": "단계형 풀이",
        "review_submode": "오늘 복습",
        "settings_submode": "기록/백업",
        "quiz_filter_key": "전체|전체|오개념 O/X",
        "profile_id": new_profile_id(),
        "profile_name": "내 학습 기록",
        "studied_concepts": [],
        "confusion_vault": [],
        "quiz_log": [],
        "explain_log": [],
        "mastery": {},
        "today_focus_concept": "normal_force",
    }
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)
    st.session_state.page_mode = safe_page(st.session_state.get("page_mode", "홈"))
    sync_session_from_db()


def card_html(title: str, body: str = "", kicker: str = "", cls: str = "study-card") -> None:
    st.markdown(
        f"""
        <div class="{cls}">
          {f'<div class="kicker">{kicker}</div>' if kicker else ''}
          <h3>{title}</h3>
          {f'<p>{body}</p>' if body else ''}
        </div>
        """,
        unsafe_allow_html=True,
    )


def status_chip(text: str, kind: str = "blue") -> str:
    return f"<span class='chip chip-{kind}'>{text}</span>"


def formula_box(formula: str, meaning: str = "") -> None:
    with st.container(border=True):
        st.markdown("<div class='formula-kicker'>FORMULA</div>", unsafe_allow_html=True)
        st.latex(formula)
        if meaning:
            st.caption(meaning)


def get_focus_concept() -> str:
    due = due_reviews(st.session_state.profile_id)
    if due:
        return due[0]
    progress = get_progress(st.session_state.profile_id)
    if progress:
        candidates = []
        for cid in CONCEPTS:
            row = progress.get(cid, {})
            candidates.append((float(row.get("mastery", 25)), cid))
        return sorted(candidates)[0][1]
    return st.session_state.get("today_focus_concept", "normal_force") if st.session_state.get("today_focus_concept") in CONCEPTS else "nt_coordinates"


def make_today_plan() -> Dict[str, Any]:
    focus = get_focus_concept()
    c = CONCEPTS[focus]
    chapter = c.get("chapter", "")
    title = c["title"]
    if any(word in title for word in ["수직항력", "마찰", "뉴턴", "힘", "장력"]):
        mission = f"{title}을 실제 FBD에서 정확히 찾기"
        tasks = [
            f"{title} 개념카드 핵심만 읽기",
            "FBD 트레이너에서 힘 목록 직접 고르기",
            "관련 오개념 퀴즈 3개 풀기",
            "틀린 부분을 3문장으로 설명하기",
        ]
    elif any(word in title for word in ["에너지", "일", "스프링"]):
        mission = f"{title}을 문제 조건에서 알아보기"
        tasks = [
            f"{title} 개념카드 핵심만 읽기",
            "공식네비게이터로 에너지 방법이 맞는지 확인하기",
            "시험형 풀이에서 단위 검산까지 진행하기",
            "오답 원인을 기록하기",
        ]
    else:
        mission = f"{title}의 대표 공식과 적용 조건 연결하기"
        tasks = [
            f"{title} 개념카드 핵심만 읽기",
            "대표 공식의 문자 뜻 확인하기",
            "공식네비게이터에서 이 개념이 나오는 조건 고르기",
            "짧은 퀴즈와 내 말로 설명까지 끝내기",
        ]
    return {"concept_id": focus, "title": mission, "chapter": chapter, "tasks": tasks, "minutes": max(15, min(25, int(c.get("time_min", 5)) + 15))}


def compact_metric(label: str, value: str, helper: str = "") -> None:
    st.markdown(
        f"""
        <div class="mini-metric">
          <div class="mini-label">{label}</div>
          <div class="mini-value">{value}</div>
          {f'<div class="mini-helper">{helper}</div>' if helper else ''}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_concept_visualization(concept_id: str) -> None:
    c = CONCEPTS[concept_id]
    title = c["title"]
    tags = " ".join(c.get("tags", []) + c.get("problem_clues", []) + [title])
    st.markdown("<div class='section-title'>바로 보는 그림</div>", unsafe_allow_html=True)
    if any(x in tags for x in ["원운동", "곡선", "구심", "n-t", "반지름", "곡률"]):
        col1, col2, col3 = st.columns(3)
        v = col1.slider("속력 v", 1.0, 40.0, 12.0, 0.5, key=f"vis_v_{concept_id}")
        r = col2.slider("반지름 r", 1.0, 100.0, 30.0, 1.0, key=f"vis_r_{concept_id}")
        at = col3.slider("접선가속도 a_t", -10.0, 10.0, 0.0, 0.5, key=f"vis_at_{concept_id}")
        st.plotly_chart(circular_motion_figure(v, r, at), use_container_width=True)
    elif any(x in tags for x in ["경사", "마찰", "수직항력", "분해"]):
        theta = st.slider("경사각 θ", 5, 60, 30, key=f"vis_theta_{concept_id}")
        friction = st.toggle("마찰 표시", value=True, key=f"vis_friction_{concept_id}")
        st.plotly_chart(incline_fbd_figure(theta, friction), use_container_width=True)
    elif any(x in tags for x in ["도르래", "장력", "줄"]):
        st.plotly_chart(pulley_figure(), use_container_width=True)
    elif any(x in tags for x in ["충돌", "운동량", "충격량", "반발"]):
        col1, col2 = st.columns(2)
        v1 = col1.slider("물체 1 속도", -10.0, 10.0, 5.0, key=f"vis_c1_{concept_id}")
        v2 = col2.slider("물체 2 속도", -10.0, 10.0, 0.0, key=f"vis_c2_{concept_id}")
        st.plotly_chart(collision_figure(v1, v2), use_container_width=True)
    elif any(x in tags for x in ["구름", "바퀴", "순간중심"]):
        rr = st.slider("바퀴 반지름", 0.1, 2.0, 0.5, key=f"vis_roll_r_{concept_id}")
        omega = st.slider("각속도 ω", 0.0, 30.0, 8.0, key=f"vis_roll_o_{concept_id}")
        st.plotly_chart(rolling_figure(rr, omega), use_container_width=True)
    elif any(x in tags for x in ["에너지", "일", "스프링", "위치에너지", "운동에너지"]):
        col1, col2, col3, col4, col5 = st.columns(5)
        T1 = col1.number_input("T1", value=0.0, key=f"vis_e_t1_{concept_id}")
        V1 = col2.number_input("V1", value=10.0, key=f"vis_e_v1_{concept_id}")
        Unc = col3.number_input("U_nc", value=0.0, key=f"vis_e_unc_{concept_id}")
        T2 = col4.number_input("T2", value=10.0, key=f"vis_e_t2_{concept_id}")
        V2 = col5.number_input("V2", value=0.0, key=f"vis_e_v2_{concept_id}")
        st.plotly_chart(energy_bar_figure(T1, V1, Unc, T2, V2), use_container_width=True)
    else:
        st.info("이 개념은 아직 전용 시각화가 연결되지 않았어요. 공식과 문제 힌트를 먼저 보고, 관련 개념 시각화를 함께 확인해보세요.")


def render_concept_card(concept_id: str, compact: bool = False) -> None:
    c = CONCEPTS[concept_id]
    add_studied(concept_id)
    mastery = st.session_state.mastery.get(concept_id, 25)

    st.markdown(
        f"""
        <div class="concept-hero">
          <div class="kicker">{c['chapter']} · 난이도 {'★' * c['level']}{'☆' * (5-c['level'])} · 약 {c['time_min']}분</div>
          <div class="concept-title-row">
            <h2>{c['title']}</h2>
            <span class="mastery-badge">숙련도 {mastery:.0f}/100</span>
          </div>
          <p>{c['summary']}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    quick_cols = st.columns([1.05, 0.95])
    with quick_cols[0]:
        st.markdown("<div class='section-title'>먼저 이것만</div>", unsafe_allow_html=True)
        with st.container(border=True):
            st.write(f"**핵심 요약**  \n{c['summary']}")
            if c.get("common_mistakes"):
                st.warning(f"대표 실수: {c['common_mistakes'][0]}", icon="⚠️")
            if c.get("when_to_use"):
                st.write("**언제 쓰나?**")
                st.markdown(" ".join([status_chip(x, "blue") for x in c.get("when_to_use", [])[:4]]), unsafe_allow_html=True)
        if not compact:
            st.markdown("<div class='button-row-label'>바로 행동하기</div>", unsafe_allow_html=True)
            b1, b2, b3 = st.columns(3)
            if b1.button("문제로 바로 풀기", key=f"v3_solve_{concept_id}", use_container_width=True, type="primary"):
                st.session_state.page_mode = "문제"
                st.session_state.problem_submode = "단계형 풀이"
                st.rerun()
            if b2.button("퀴즈 풀기", key=f"v3_quiz_{concept_id}", use_container_width=True):
                st.session_state.page_mode = "복습"
                st.session_state.review_submode = "퀴즈"
                st.session_state.quiz_preselect = concept_id
                st.rerun()
            if b3.button("헷갈림 저장", key=f"v3_confuse_{concept_id}", use_container_width=True):
                add_confusion(concept_id)
    with quick_cols[1]:
        st.markdown("<div class='section-title'>대표 공식</div>", unsafe_allow_html=True)
        formulas = c.get("formulas", [])[:1 if compact else 2]
        if formulas:
            for f in formulas:
                formula_box(f.get("latex", ""), f.get("meaning", ""))
        else:
            st.info("등록된 대표 공식이 없습니다.")
        if c.get("problem_clues"):
            st.markdown("<div class='section-title'>문제 힌트</div>", unsafe_allow_html=True)
            st.markdown(" ".join([status_chip(x, "slate") for x in c.get("problem_clues", [])[:6]]), unsafe_allow_html=True)

    if compact:
        return

    with st.expander("기호 설명 · 자세히 보기", expanded=False):
        sym_df = pd.DataFrame([{"기호": k, "뜻": v} for k, v in c.get("symbols", {}).items()])
        if not sym_df.empty:
            st.dataframe(sym_df, use_container_width=True, hide_index=True)
        st.write("**쉬운 비유**")
        st.info(c.get("analogy", ""))
        if len(c.get("formulas", [])) > 2:
            st.write("**추가 공식**")
            for f in c.get("formulas", [])[2:]:
                formula_box(f.get("latex", ""), f.get("meaning", ""))

    with st.expander("자주 하는 실수 · 연결 개념", expanded=False):
        for m in c.get("common_mistakes", []):
            st.warning(m, icon="⚠️")
        rel = get_related_concepts(concept_id)
        if rel:
            st.write("**같이 보면 좋은 개념**")
            cols = st.columns(min(4, len(rel)))
            for idx, (rid, rc) in enumerate(rel):
                with cols[idx % len(cols)]:
                    if st.button(rc["title"], key=f"v3_related_{concept_id}_{rid}", use_container_width=True):
                        st.session_state.selected_concept = rid
                        st.rerun()

    with st.expander("미니 예제", expanded=False):
        ex = c.get("mini_example", {})
        st.write(f"**문제**: {ex.get('problem', '')}")
        st.write("**풀이**")
        st.write(ex.get("solution", ""))

    with st.expander("이 개념을 그림으로 보기", expanded=False):
        render_concept_visualization(concept_id)


def page_home(api_key: str | None) -> None:
    plan = make_today_plan()
    cid = plan["concept_id"]
    st.session_state.today_focus_concept = cid
    progress = get_progress(st.session_state.profile_id)
    due = due_reviews(st.session_state.profile_id)
    concept_rows = progress or {}
    avg_mastery = 25 if not concept_rows else sum(float(v.get("mastery", 25)) for v in concept_rows.values()) / max(1, len(CONCEPTS))

    st.markdown(
        f"""
        <div class="home-hero">
          <div class="home-hero-left">
            <div class="kicker">TODAY'S DYNAMICS COACH</div>
            <h1>오늘의 학습</h1>
            <p>{plan['title']}</p>
            <div class="hero-tags">
              {status_chip(plan['chapter'], 'blue')}
              {status_chip('예상 ' + str(plan['minutes']) + '분', 'green')}
              {status_chip('AI 코치 ' + ('ON' if api_key else 'OFF'), 'slate')}
            </div>
          </div>
          <div class="home-hero-right">🧭</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    m1, m2, m3, m4 = st.columns(4)
    with m1:
        compact_metric("평균 숙련도", f"{avg_mastery:.0f}/100", "기록 기반")
    with m2:
        compact_metric("오늘 복습", f"{len(due)}개", "간격 반복")
    with m3:
        compact_metric("헷갈림", f"{len(st.session_state.confusion_vault)}개", "직접 저장")
    with m4:
        compact_metric("개념카드", f"{len(CONCEPTS)}개", "전체 단원")

    left, right = st.columns([1.15, 0.85])
    with left:
        st.markdown("<div class='section-title'>오늘 할 일</div>", unsafe_allow_html=True)
        for idx, task in enumerate(plan["tasks"], start=1):
            st.markdown(
                f"""
                <div class="task-card">
                  <div class="task-number">{idx}</div>
                  <div class="task-body">{task}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        c1, c2, c3 = st.columns([1.3, 1, 1])
        if c1.button("오늘의 학습 시작하기", type="primary", use_container_width=True):
            st.session_state.selected_concept = cid
            st.session_state.page_mode = "개념"
            st.session_state.concept_submode = "개념카드"
            st.rerun()
        if c2.button("바로 문제 풀기", use_container_width=True):
            st.session_state.page_mode = "문제"
            st.session_state.problem_submode = "단계형 풀이"
            st.rerun()
        if c3.button("짧은 복습", use_container_width=True):
            st.session_state.page_mode = "복습"
            st.session_state.review_submode = "퀴즈"
            st.session_state.quiz_preselect = cid
            st.rerun()

        st.markdown("<div class='section-title'>최근 기록</div>", unsafe_allow_html=True)
        events = recent_events(st.session_state.profile_id, 5)
        if events:
            for ev in events:
                st.markdown(
                    f"<div class='log-line'><b>{ev.get('event_type','기록')}</b><span>{ev.get('concept_id','')}</span><em>{ev.get('created_at','')}</em></div>",
                    unsafe_allow_html=True,
                )
        else:
            st.info("아직 기록이 없어. 오늘의 학습을 시작하면 여기에 쌓여.")

    with right:
        st.markdown("<div class='section-title'>오늘의 핵심 개념</div>", unsafe_allow_html=True)
        render_concept_card(cid, compact=True)
        if due:
            with st.container(border=True):
                st.write("**오늘 다시 보면 좋은 개념**")
                for dcid in due[:5]:
                    if st.button(CONCEPTS[dcid]["title"], key=f"home_due_{dcid}", use_container_width=True):
                        st.session_state.selected_concept = dcid
                        st.session_state.page_mode = "개념"
                        st.session_state.concept_submode = "개념카드"
                        st.rerun()


def page_concept_hub() -> None:
    st.markdown("<div class='page-heading'><h1>개념</h1><p>개념카드, 개념맵, 시각화를 한 흐름으로 봅니다.</p></div>", unsafe_allow_html=True)
    mode = st.radio("개념 메뉴", ["개념카드", "개념맵", "학습 경로", "시각화"], key="concept_submode", horizontal=True)
    if mode == "개념카드":
        page_concept_cards()
    elif mode == "개념맵":
        page_concept_map()
    elif mode == "학습 경로":
        page_learning_path()
    else:
        cid = concept_selectbox("시각화와 연결할 개념", "concept_visual_select", st.session_state.selected_concept)
        st.session_state.selected_concept = cid
        render_concept_card(cid, compact=True)
        render_concept_visualization(cid)
        with st.expander("전체 시각화 도구 보기", expanded=False):
            page_visual_lab()


def _grade_solver_step(problem: Dict[str, Any], step: Dict[str, Any], ans: str) -> bool:
    if "numeric_answer" in step:
        result = check_numeric_with_unit(ans, step["numeric_answer"], step.get("tolerance", 0.01), step.get("unit", ""))
        if result["correct"]:
            st.success("계산값과 단위가 모두 맞아요.")
        else:
            st.warning(f"점검 결과: 숫자 {result['numeric_ok']}, 단위 {result['unit_ok']}, 읽은 값 {result['parsed_number']}")
        ok = bool(result["correct"])
    else:
        score, hits, misses = grade_text_by_rubric(ans, step.get("rubric", []))
        st.metric("단계 점수", f"{score}점")
        if hits:
            st.success("잡은 핵심: " + ", ".join(hits))
        if misses:
            st.warning("빠진 핵심: " + ", ".join(misses))
        ok = score >= 60
    with st.expander("모범 답안 보기"):
        st.write(step["answer"])
    log_quiz(
        st.session_state.profile_id,
        problem["concept_ids"][0],
        ok,
        "solver_stepper",
        "단위 오류" if "numeric_answer" in step and not ok else "공식 선택 오류",
        payload={"problem": problem["id"], "step": step["name"], "user_answer": ans},
    )
    sync_session_from_db()
    return ok


def page_solver_stepper() -> None:
    st.markdown("<div class='section-title'>단계형 시험 풀이</div>", unsafe_allow_html=True)
    st.caption("한 번에 모든 칸을 채우지 말고, 실제 동역학 풀이 순서대로 하나씩 통과합니다.")
    problem = st.selectbox("문제 선택", PROBLEM_BANK, format_func=lambda p: f"[{p['level']}단계] {p['title']}", key="stepper_problem")
    steps = problem["steps"]
    step_key = f"solver_step_index_{problem['id']}"
    st.session_state.setdefault(step_key, 0)
    st.session_state[step_key] = max(0, min(st.session_state[step_key], len(steps)-1))
    current_idx = st.session_state[step_key]

    st.markdown(f"<div class='problem-card'><div class='kicker'>시험형 문제</div><h3>{problem['title']}</h3><p>{problem['statement']}</p></div>", unsafe_allow_html=True)
    st.progress((current_idx + 1) / len(steps), text=f"{current_idx + 1}/{len(steps)}단계")

    with st.expander("주어진 값과 관련 개념", expanded=False):
        st.json(problem.get("givens", {}))
        st.markdown(" ".join([status_chip(CONCEPTS[cid]["title"], "blue") for cid in problem.get("concept_ids", []) if cid in CONCEPTS]), unsafe_allow_html=True)

    step = steps[current_idx]
    step_names = ["문제 이해", "물체 선택", "FBD", "좌표축", "방정식", "계산", "해석"]
    inferred_name = step_names[min(current_idx, len(step_names)-1)]
    st.markdown(
        f"""
        <div class="step-card">
          <div class="step-index">STEP {current_idx + 1}</div>
          <h3>{inferred_name}: {step['name']}</h3>
          <p>{step['prompt']}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if "FBD" in step["name"] or "힘" in step["prompt"]:
        st.info("FBD 단계에서는 실제 힘만 적어야 해. '구심력'은 새 힘이 아니라 중심방향 합력의 이름이라는 점을 조심해.")
    if "단위" in step.get("name", "") or "계산" in step.get("name", ""):
        st.info("숫자만 쓰지 말고 단위까지 함께 입력해. 예: 3.2 m/s^2")

    answer_key = f"stepper_answer_{problem['id']}_{current_idx}"
    ans = st.text_area("내 답", key=answer_key, height=120, placeholder="이 단계에서 필요한 판단만 적어봐.")
    b1, b2, b3, b4 = st.columns([1, 1, 1, 1])
    if b1.button("이 단계 점검", type="primary", use_container_width=True, key=f"grade_step_{problem['id']}_{current_idx}"):
        _grade_solver_step(problem, step, ans)
    if b2.button("이전", use_container_width=True, disabled=current_idx == 0, key=f"prev_step_{problem['id']}"):
        st.session_state[step_key] -= 1
        st.rerun()
    if b3.button("다음", use_container_width=True, disabled=current_idx >= len(steps)-1, key=f"next_step_{problem['id']}"):
        st.session_state[step_key] += 1
        st.rerun()
    if b4.button("처음부터", use_container_width=True, key=f"reset_step_{problem['id']}"):
        st.session_state[step_key] = 0
        st.rerun()

    with st.expander("이 문제에서 자주 하는 실수"):
        for e in problem.get("common_errors", []):
            st.warning(e, icon="⚠️")


def page_fbd_trainer() -> None:
    st.markdown("<div class='section-title'>FBD 트레이너</div>", unsafe_allow_html=True)
    st.caption("DynaMap의 핵심 훈련입니다. 힘을 직접 고르고, 빠진 힘/불필요한 힘/좌표축/방정식을 구분해서 피드백합니다.")
    scenario = st.selectbox("상황 선택", FBD_SCENARIOS, format_func=lambda s: s["title"], key="v3_fbd_scenario")

    st.markdown(f"<div class='problem-card'><div class='kicker'>FBD SCENARIO</div><h3>{scenario['title']}</h3><p>{scenario['situation']}</p></div>", unsafe_allow_html=True)
    vis_col, input_col = st.columns([0.95, 1.05])
    with vis_col:
        if scenario["id"] == "incline_down":
            st.plotly_chart(incline_fbd_figure(), use_container_width=True)
        elif scenario["id"] == "hanging_mass":
            st.plotly_chart(pulley_figure(), use_container_width=True)
        elif scenario["id"] == "circular_car":
            st.plotly_chart(circular_motion_figure(10, 30, 0), use_container_width=True)
        else:
            st.info("그림이 단순해도 원칙은 같아. 물체 하나만 분리해서 실제 힘만 그려야 해.")
        with st.expander("FBD 원칙"):
            st.write("- 물체 하나만 고른다.")
            st.write("- 실제로 작용하는 힘만 그린다.")
            st.write("- 가속도는 힘이 아니다.")
            st.write("- 구심력은 별도 힘이 아니라 중심방향 합력의 이름이다.")
    with input_col:
        choices = sorted(set(scenario["correct_forces"] + scenario.get("optional_forces", []) + ["가속도 ma", "구심력이라는 별도 힘", "운동방향 힘 없음", "관성력"]))
        selected = st.multiselect("FBD에 그릴 힘", choices, key=f"v3_forces_{scenario['id']}")
        axis = st.text_input("좌표축 설정", placeholder=scenario["axis"], key=f"v3_axis_{scenario['id']}")
        equation = st.text_area("운동방정식", placeholder="예: ΣFx=P-f=ma, ΣFy=N-mg=0", key=f"v3_eq_{scenario['id']}")
        if st.button("FBD 점검", type="primary", use_container_width=True, key=f"v3_fbd_check_{scenario['id']}"):
            correct = set(scenario["correct_forces"])
            sel = set(selected)
            missing = sorted(correct - sel)
            extra = sorted(sel - correct - set(scenario.get("optional_forces", [])))
            axis_score, _, axis_miss = grade_text_by_rubric(axis, scenario["axis"].split())
            eq_rubric = []
            for eq in scenario["equations"]:
                eq_rubric += [x for x in ["sum", "Σ", "F", "M", "ma", "I", "alpha", "mg", "N", "f"] if x in eq or x.replace("alpha", "\\alpha") in eq]
            eq_score, _, _ = grade_text_by_rubric(equation, eq_rubric or ["F", "ma"])
            force_ok = not missing and not extra
            total = int((55 if force_ok else max(0, 55 - 15 * len(missing) - 10 * len(extra))) + 0.2 * axis_score + 0.25 * eq_score)
            st.metric("FBD 점수", f"{max(0, min(100, total))}점")
            if missing:
                st.error("빠진 힘: " + ", ".join(missing))
            if extra:
                st.warning("불필요하거나 위험한 항목: " + ", ".join(extra))
                if any("구심력" in x for x in extra):
                    st.info("구심력은 새로운 힘이 아니라 중심 방향 합력의 이름입니다. 실제 힘은 중력, 장력, 마찰력, 수직항력처럼 물체에 직접 작용하는 힘입니다.")
            if not missing and not extra:
                st.success("힘 목록은 좋아요. 이제 방향과 방정식 부호를 확인하면 됩니다.")
            if axis_miss:
                st.warning("좌표축 설명에서 부족한 말: " + ", ".join(axis_miss))
            st.write("**권장 좌표축**: " + scenario["axis"])
            st.write("**대표 방정식**")
            for eq in scenario["equations"]:
                st.latex(eq)
            cid = scenario["concept_ids"][0]
            log_quiz(st.session_state.profile_id, cid, force_ok and total >= 70, "fbd", "FBD 누락" if missing else "좌표축 오류", payload={"scenario": scenario["id"], "missing": missing, "extra": extra})
            sync_session_from_db()


def page_problem_hub() -> None:
    st.markdown("<div class='page-heading'><h1>문제</h1><p>공식 선택 → FBD → 단계형 풀이를 한 흐름으로 훈련합니다.</p></div>", unsafe_allow_html=True)
    mode = st.radio("문제 메뉴", ["단계형 풀이", "FBD 트레이너", "공식네비게이터"], key="problem_submode", horizontal=True)
    if mode == "단계형 풀이":
        page_solver_stepper()
    elif mode == "FBD 트레이너":
        page_fbd_trainer()
    else:
        page_formula_navigator()


def page_review_hub(api_key: str | None, model_name: str) -> None:
    st.markdown("<div class='page-heading'><h1>복습</h1><p>짧은 퀴즈, 내 말로 설명, 헷갈림 목록을 한곳에서 관리합니다.</p></div>", unsafe_allow_html=True)
    mode = st.radio("복습 메뉴", ["오늘 복습", "퀴즈", "내 말로 설명", "헷갈림"], key="review_submode", horizontal=True)
    if mode == "오늘 복습":
        due = due_reviews(st.session_state.profile_id)
        if not due:
            st.success("오늘 꼭 복습해야 하는 개념은 없어요. 대신 약한 개념 하나를 가볍게 보면 좋아요.")
            due = [get_focus_concept()]
        for cid in due[:8]:
            with st.container(border=True):
                col1, col2, col3 = st.columns([1.2, 0.9, 0.9])
                col1.write(f"**{CONCEPTS[cid]['title']}**")
                col1.caption(CONCEPTS[cid]["summary"])
                if col2.button("개념 보기", key=f"review_card_{cid}", use_container_width=True):
                    st.session_state.selected_concept = cid
                    st.session_state.page_mode = "개념"
                    st.session_state.concept_submode = "개념카드"
                    st.rerun()
                if col3.button("퀴즈 풀기", key=f"review_quiz_{cid}", use_container_width=True):
                    st.session_state.review_submode = "퀴즈"
                    st.session_state.quiz_preselect = cid
                    st.rerun()
    elif mode == "퀴즈":
        page_quiz_lab()
    elif mode == "내 말로 설명":
        page_explain(api_key, model_name)
    else:
        st.markdown("<div class='section-title'>헷갈린 개념</div>", unsafe_allow_html=True)
        if not st.session_state.confusion_vault:
            st.success("헷갈림 목록이 비어 있어요. 개념카드에서 어려운 개념을 저장하면 여기에 모입니다.")
        for cid in st.session_state.confusion_vault:
            with st.container(border=True):
                col1, col2, col3 = st.columns([1.3, 0.7, 0.7])
                col1.write(f"**{CONCEPTS[cid]['title']}**")
                col1.caption(CONCEPTS[cid]["summary"])
                if col2.button("복습", key=f"conf_review_{cid}", use_container_width=True):
                    st.session_state.selected_concept = cid
                    st.session_state.page_mode = "개념"
                    st.session_state.concept_submode = "개념카드"
                    st.rerun()
                if col3.button("해제", key=f"conf_clear_{cid}", use_container_width=True):
                    remove_confusion(cid)
                    st.rerun()


def page_report_hub() -> None:
    st.markdown("<div class='page-heading'><h1>리포트</h1><p>이번 주 약점과 다음 행동을 확인합니다.</p></div>", unsafe_allow_html=True)
    page_report()
    st.markdown("<div class='section-title'>다음 행동 제안</div>", unsafe_allow_html=True)
    progress = get_progress(st.session_state.profile_id)
    weak = sorted([(float(progress.get(cid, {}).get("mastery", 25)), cid) for cid in CONCEPTS])[:5]
    for _, cid in weak:
        with st.container(border=True):
            col1, col2 = st.columns([1.4, 0.6])
            col1.write(f"**{CONCEPTS[cid]['title']}**")
            col1.caption("개념카드 3분 → 퀴즈 2문제 → 내 말로 설명 순서 추천")
            if col2.button("보강 시작", key=f"report_fix_{cid}", use_container_width=True):
                st.session_state.selected_concept = cid
                st.session_state.page_mode = "개념"
                st.session_state.concept_submode = "개념카드"
                st.rerun()


def page_settings_hub(api_key: str | None, model_name: str) -> None:
    st.markdown("<div class='page-heading'><h1>설정</h1><p>API, 백업, 데이터 관리 기능을 모았습니다.</p></div>", unsafe_allow_html=True)
    mode = st.radio("설정 메뉴", ["기록/백업", "AI 설정", "AI 확장 도구"], key="settings_submode", horizontal=True)
    if mode == "기록/백업":
        page_data_manager()
    elif mode == "AI 설정":
        st.markdown("<div class='section-title'>AI 설정 / 개인정보 안내</div>", unsafe_allow_html=True)
        st.warning("AI 기능을 사용하면 네가 입력한 설명, 문제 문장, 교재 텍스트와 해당 개념카드 정보가 OpenAI API로 전송될 수 있습니다. API 키나 개인정보를 본문에 넣지 마세요.")
        st.text_input("임시 API 키", type="password", key="api_key_override", help="GitHub에는 절대 올리지 마세요. 배포에서는 Streamlit Secrets 사용을 권장합니다.")
        st.text_input("모델명", key="model_name")
        st.info("API 키가 없어도 개념카드, 공식추천, 퀴즈, FBD, 단계형 풀이는 작동합니다. AI 첨삭/진단만 비활성화됩니다.")
        st.write("현재 AI 코치 상태: " + ("ON" if api_key else "OFF"))
    else:
        page_ai_tools(api_key, model_name)


def sidebar() -> tuple[str, str | None, str]:
    st.sidebar.markdown("## 🧭 DynaMap")
    st.sidebar.caption("개인 동역학 코치")
    st.sidebar.text_input("프로필", key="profile_name", label_visibility="collapsed")
    current = safe_page(st.session_state.get("page_mode", "홈"))
    page = st.sidebar.radio(
        "메뉴",
        MAIN_PAGES,
        index=MAIN_PAGES.index(current),
        key="page_mode",
        format_func=lambda p: f"{PAGE_ICONS[p]} {p}",
    )
    st.sidebar.divider()
    api_key = get_api_key_from_sources(getattr(st, "secrets", None), st.session_state.get("api_key_override", ""))
    st.sidebar.markdown("### 오늘")
    plan = make_today_plan()
    st.sidebar.caption(plan["title"])
    st.sidebar.progress(min(1.0, st.session_state.mastery.get(plan["concept_id"], 25) / 100), text=f"{CONCEPTS[plan['concept_id']]['title']} 숙련도")
    st.sidebar.divider()
    st.sidebar.caption("API: " + ("ON" if api_key else "OFF") + " · 설정에서 변경")
    return page, api_key, st.session_state.get("model_name", "gpt-4.1-mini")


def main() -> None:
    load_css()
    init_state()
    page, api_key, model_name = sidebar()
    if page == "홈":
        page_home(api_key)
    elif page == "개념":
        page_concept_hub()
    elif page == "문제":
        page_problem_hub()
    elif page == "복습":
        page_review_hub(api_key, model_name)
    elif page == "리포트":
        page_report_hub()
    elif page == "설정":
        page_settings_hub(api_key, model_name)


if __name__ == "__main__":
    main()
