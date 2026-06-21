# DynaMap

**DynaMap**은 동역학을 혼자 공부할 때 쓰는 개인 학습 코치형 Streamlit 앱입니다.

v3의 목표는 기능을 더 늘리는 것이 아니라, 기존 기능을 **하나의 공부 흐름**으로 묶는 것입니다.

- 앱을 켜면 바로 **오늘의 학습**이 보입니다.
- 메뉴는 **홈 / 개념 / 문제 / 복습 / 리포트 / 설정** 6개로 단순화했습니다.
- 문제풀이는 **문제 이해 → FBD → 좌표축 → 방정식 → 계산 → 해석** 단계로 진행합니다.
- 개념카드는 처음에는 핵심만 보여주고, 자세한 내용은 접어서 볼 수 있습니다.
- 시각화는 독립 기능뿐 아니라 개념 학습 안에서 바로 볼 수 있게 연결했습니다.

## 핵심 메뉴

### 1. 홈

- 오늘의 목표
- 오늘 할 일
- 예상 소요 시간
- 빠른 시작 버튼
- 최근 기록
- 오늘의 핵심 개념

### 2. 개념

포함 기능:

- 개념카드
- 개념맵
- 학습 경로
- 개념별 시각화

개념카드는 다음 순서로 정리됩니다.

1. 핵심 요약
2. 대표 공식
3. 언제 쓰는지
4. 문제 힌트
5. 바로 풀어보기
6. 접어서 보는 기호 설명, 실수, 연결 개념, 예제, 시각화

### 3. 문제

포함 기능:

- 단계형 시험 풀이
- FBD 트레이너
- 공식네비게이터

단계형 풀이는 한 화면에 모든 입력칸을 보여주지 않고, 실제 풀이 순서대로 하나씩 진행합니다.

```text
문제 이해 → 물체 선택 → FBD → 좌표축 → 방정식 → 계산 → 해석
```

### 4. 복습

포함 기능:

- 오늘 복습
- 퀴즈
- 내 말로 설명
- 헷갈림 목록

틀린 개념과 헷갈리는 개념은 숙련도와 복습 예정일에 반영됩니다.

### 5. 리포트

- 평균 숙련도
- 약점 TOP 10
- 최근 기록
- 다음 행동 제안

### 6. 설정

- 학습 기록 백업/가져오기
- API 키 설정
- AI 확장 도구

## 설치 및 실행

로컬 실행도 배포 진입점과 맞추기 위해 `streamlit_app.py`를 권장합니다.

```bash
cd DynaMap
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run streamlit_app.py
```

## Streamlit Cloud 배포

Streamlit Community Cloud에서는 다음으로 지정하세요.

```text
Main file path: streamlit_app.py
```

`streamlit_app.py`는 다음처럼 실제 앱의 `main()`을 명시적으로 호출합니다.

```python
from app import main

main()
```

## OpenAI API 키 설정

API 키가 없어도 개념카드, 공식추천, 퀴즈, FBD, 단계형 풀이는 작동합니다. API 키가 있으면 AI 첨삭과 AI 진단 기능을 사용할 수 있습니다.

### 방법 1. 환경변수

```bash
export OPENAI_API_KEY="sk-your-key-here"
```

Windows PowerShell:

```powershell
setx OPENAI_API_KEY "sk-your-key-here"
```

### 방법 2. Streamlit secrets

```bash
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
```

`.streamlit/secrets.toml`:

```toml
OPENAI_API_KEY = "sk-your-key-here"
```

### 방법 3. 앱 설정 화면에서 임시 입력

앱의 `설정 → AI 설정`에서 임시 API 키를 넣을 수 있습니다. 공용 컴퓨터에서는 권장하지 않습니다.

## 개인정보/API 안내

AI 기능을 사용하면 사용자가 입력한 설명, 문제 문장, 교재 텍스트와 해당 개념카드 정보가 OpenAI API로 전송될 수 있습니다.

- API 키를 GitHub에 올리지 마세요.
- 문제/설명 입력란에 민감한 개인정보를 넣지 마세요.
- `.streamlit/secrets.toml`은 `.gitignore`에 포함되어 있습니다.

## 파일 구조

```text
DynaMap/
├── streamlit_app.py
├── app.py
├── requirements.txt
├── README.md
├── QUICKSTART.md
├── DEPLOY.md
├── UI_UX_FIXES.md
├── content/
│   ├── concepts.json
│   ├── formula_rules.json
│   ├── fbd_scenarios.json
│   ├── learning_paths.json
│   └── problem_bank.json
├── dynacore/
│   ├── data.py
│   ├── engine.py
│   ├── ai.py
│   ├── progress.py
│   └── visuals.py
├── assets/
│   └── style.css
├── tests/
│   └── test_engine.py
└── .streamlit/
    ├── config.toml
    └── secrets.toml.example
```

## 테스트

```bash
python -m py_compile streamlit_app.py app.py dynacore/*.py
python -m pytest -q
```

## 주의

- 이 앱은 공부 보조용입니다. 교재와 강의를 완전히 대체하는 앱이 아닙니다.
- 실제 문제풀이에서는 단위, 부호, 좌표축, 문제 조건을 직접 확인해야 합니다.
- Streamlit Community Cloud의 로컬 SQLite 파일은 재배포/서버 재시작 시 초기화될 수 있으므로 중요한 기록은 JSON으로 백업하세요.
