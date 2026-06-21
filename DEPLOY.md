# DynaMap 배포 가이드

이 저장소는 GitHub + Streamlit Community Cloud 배포를 기준으로 준비되어 있습니다.

## 1. GitHub 저장소에 올리기

압축을 풀고 `DynaMap` 폴더 안에서 실행합니다.

```bash
git init
git add .
git commit -m "Initial DynaMap app"
git branch -M main
git remote add origin https://github.com/YOUR_ID/DynaMap.git
git push -u origin main
```

## 2. Streamlit Community Cloud 설정

1. Streamlit Community Cloud에 로그인합니다.
2. `New app`을 누릅니다.
3. Repository: `YOUR_ID/DynaMap`
4. Branch: `main`
5. Main file path: `streamlit_app.py`
6. Python version: `3.11` 또는 `3.12`
7. Secrets에 API 키를 넣습니다.

```toml
OPENAI_API_KEY = "sk-..."
```

## 3. 진입점 기준

배포 진입점은 `streamlit_app.py` 하나로 통일합니다.

```python
from app import main

main()
```

로컬에서도 가능하면 아래처럼 실행하세요.

```bash
streamlit run streamlit_app.py
```

## 4. API 키 주의

절대 실제 API 키를 GitHub에 커밋하지 마세요.

이 저장소의 `.gitignore`는 다음을 제외합니다.

```text
.streamlit/secrets.toml
.env
.venv/
__pycache__/
```

## 5. 배포 후 수정 반영

```bash
git add .
git commit -m "Update DynaMap"
git push
```

## 6. 문제 발생 시 확인 순서

1. Main file path가 `streamlit_app.py`인지 확인
2. `requirements.txt`가 저장소 루트에 있는지 확인
3. Streamlit Cloud 로그에서 `ModuleNotFoundError` 확인
4. Secrets에 `OPENAI_API_KEY = "sk-..."` 형식으로 들어갔는지 확인
5. Python 버전이 3.11 또는 3.12인지 확인
6. 로컬에서 아래 명령이 통과하는지 확인

```bash
python -m py_compile streamlit_app.py app.py dynacore/*.py
python -m pytest -q
```
