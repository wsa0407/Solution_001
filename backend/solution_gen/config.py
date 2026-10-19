from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[1]


def _load_dotenv() -> None:
    path = ROOT / ".env"
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv()


class Settings(BaseModel):
    chapter_concurrency: int = Field(default_factory=lambda: int(os.environ.get("CHAPTER_CONCURRENCY", "3")))
    qa_max_retries: int = Field(default_factory=lambda: int(os.environ.get("QA_MAX_RETRIES", "2")))
    data_dir: Path = Field(default_factory=lambda: Path(os.environ.get("SOLUTION_DATA_DIR", str(ROOT / "data"))))
    knowledge_dir: Path = Field(default_factory=lambda: Path(os.environ.get("SOLUTION_KNOWLEDGE_DIR", str(ROOT / "knowledge"))))
    token_price_per_1k: float = Field(default_factory=lambda: float(os.environ.get("TOKEN_PRICE_PER_1K", "0.02")))
    llm_base_url: str = Field(default_factory=lambda: os.environ.get("SOLUTION_LLM_BASE_URL", ""))
    llm_api_key: str = Field(default_factory=lambda: os.environ.get("SOLUTION_LLM_API_KEY", os.environ.get("MINIMAX_API_KEY", "")))
    llm_model: str = Field(default_factory=lambda: os.environ.get("SOLUTION_LLM_MODEL", "MiniMax-M3"))
    deepseek_api_key: str = Field(default_factory=lambda: os.environ.get("DEEPSEEK_API_KEY", ""))
    deepseek_base_url: str = Field(default_factory=lambda: os.environ.get("DEEPSEEK_BASE_URL", ""))
    deepseek_model: str = Field(default_factory=lambda: os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-flash"))
    dsh_timeout: int = Field(default_factory=lambda: int(os.environ.get("DSH_TIMEOUT", "180")))
    diagram_scripts_dir: Path = Field(
        default_factory=lambda: Path(os.environ.get("SOLUTION_DIAGRAM_SCRIPTS", str(ROOT / "skills" / "diagram")))
    )

    @property
    def diagram_skill_scripts(self) -> Path:
        return self.diagram_scripts_dir

    @property
    def db_path(self) -> Path:
        return self.data_dir / "jobs.db"

    @property
    def outputs_dir(self) -> Path:
        return self.data_dir / "outputs"


settings = Settings()
settings.data_dir.mkdir(parents=True, exist_ok=True)
settings.outputs_dir.mkdir(parents=True, exist_ok=True)
