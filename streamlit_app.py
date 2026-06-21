"""Streamlit Community Cloud entrypoint for DynaMap."""

from pathlib import Path
import importlib.util
import sys

ROOT = Path(__file__).resolve().parent
CORE = ROOT / "dynacore"

# 현재 앱 폴더를 파이썬 모듈 검색 경로 맨 앞에 둔다.
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# 혹시 Streamlit 환경에서 dynacore 이름이 꼬이거나 다른 패키지와 충돌해도
# 반드시 현재 저장소의 dynacore 폴더를 쓰도록 강제로 등록한다.
if CORE.exists() and (CORE / "__init__.py").exists():
    spec = importlib.util.spec_from_file_location(
        "dynacore",
        CORE / "__init__.py",
        submodule_search_locations=[str(CORE)],
    )
    dynacore_module = importlib.util.module_from_spec(spec)
    sys.modules["dynacore"] = dynacore_module

    if spec.loader is not None:
        spec.loader.exec_module(dynacore_module)

from app import main

main()
