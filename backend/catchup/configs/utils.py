import tomllib
from pathlib import Path


def get_version() -> str:
    """
    APP_VERSION 환경변수가 없는 경우 Fallback으로 실행되는 유틸 함수.
    pyproject.toml로부터 version 정보를 획득한다.
    """
    try:
        path = Path(__file__).resolve().parents[2] / "pyproject.toml"
        with open(path, "rb") as f:
            data = tomllib.load(f)
            version = data["project"]["version"]
        return version
    
    except Exception as e:
        raise RuntimeError(f"Could not read version from {path}. Check if file exists.") from e