"""Central API configuration."""
from __future__ import annotations
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ATS_", env_file=".env", extra="ignore")

    # Project root = parent of api/
    project_root: Path = Path(__file__).resolve().parent.parent

    # ---- Input folders ----
    api_data_root: Path = project_root / "api_data"
    upload_dir: Path = api_data_root / "raw_resumes"     # uploaded resume files
    jd_dir: Path = api_data_root / "jds"                 # JD JSON files

    # Internal metadata index (lives alongside inputs)
    metadata_file: Path = api_data_root / "metadata.json"

    # ---- Output folders ----
    result_dir: Path = project_root / "api_data_results"
    parsed_results_dir: Path = result_dir / "parsed"
    scores_results_dir: Path = result_dir / "scores"
    shortlist_results_dir: Path = result_dir / "shortlists"

    # ---- Logs ----
    log_dir: Path = project_root / "logs"

    # ---- Limits ----
    max_upload_mb: int = 10
    allowed_extensions: tuple[str, ...] = (".pdf", ".docx", ".doc")

    # ---- Async ----
    max_concurrent_workers: int = 4
    job_retention_hours: int = 24

    # ---- API ----
    api_title: str = "Zecpath ATS API"
    api_version: str = "1.0"
    api_base_path: str = "/v1"

    # ---- Logging ----
    log_level: str = "INFO"
    service_name: str = "ATS Engine"

    def all_dirs(self) -> tuple[Path, ...]:
        return (
            self.api_data_root,
            self.upload_dir,
            self.jd_dir,
            self.result_dir,
            self.parsed_results_dir,
            self.scores_results_dir,
            self.shortlist_results_dir,
            self.log_dir,
        )

    def ensure_dirs(self) -> None:
        for p in self.all_dirs():
            p.mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.ensure_dirs()
