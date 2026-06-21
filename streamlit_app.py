"""Streamlit Community Cloud entrypoint for DynaMap."""

from pathlib import Path
import importlib.util
import sys
import types

ROOT = Path(__file__).resolve().parent
CORE = ROOT / "dynacore"

# 현재 저장소 루트를 파이썬 검색 경로에 추가
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# dynacore 폴더 자체도 검색 경로에 추가
if str(CORE) not in sys.path:
    sys.path.insert(0, str(CORE))

# dynacore를 패키지로 강제 등록
if "dynacore" not in sys.modules:
    package = types.ModuleType("dynacore")
    package.__path__ = [str(CORE)]
    package.__file__ = str(CORE / "__init__.py")
    package.__package__ = "dynacore"
    sys.modules["dynacore"] = package


def load_dynacore_module(module_name: str) -> None:
    """Load dynacore.<module_name> directly from dynacore/<module_name>.py."""
    full_name = f"dynacore.{module_name}"
    file_path = CORE / f"{module_name}.py"

    if full_name in sys.modules:
        return

    if not file_path.exists():
        raise FileNotFoundError(f"Missing required module file: {file_path}")

    spec = importlib.util.spec_from_file_location(full_name, file_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load module spec for {full_name} from {file_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[full_name] = module
    spec.loader.exec_module(module)


# app.py가 import하기 전에 dynacore 하위 모듈들을 미리 등록
for name in ["data", "engine", "progress", "visuals", "ai"]:
    load_dynacore_module(name)

from app import main

main()
