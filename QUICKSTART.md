# DynaMap 빠른 실행

## 1. 실행

```bash
cd DynaMap
pip install -r requirements.txt
streamlit run streamlit_app.py
```

배포와 로컬 실행 모두 `streamlit_app.py`를 기준으로 통일했습니다.

## 2. API 키 설정 선택 사항

API 키 없이도 핵심 학습 기능은 작동합니다.

```bash
export OPENAI_API_KEY="sk-your-key-here"
```

또는 `.streamlit/secrets.toml` 생성:

```toml
OPENAI_API_KEY = "sk-your-key-here"
```

앱 안에서는 `설정 → AI 설정`에서 임시 키를 넣을 수 있습니다.

## 3. 추천 사용 순서

1. `홈`에서 오늘의 학습 확인
2. `개념`에서 오늘의 핵심 개념카드 읽기
3. `문제`에서 단계형 풀이 또는 FBD 트레이너 진행
4. `복습`에서 퀴즈와 내 말로 설명하기
5. `리포트`에서 약점 확인
6. `설정`에서 기록 백업

## 4. Streamlit Cloud 배포 시

```text
Main file path: streamlit_app.py
```
