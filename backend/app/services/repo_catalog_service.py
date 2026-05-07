from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.config import Settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class RepoCatalogArtifacts:
    catalog_json_path: Path
    catalog_md_path: Path
    payload: dict


class RepoCatalogService:
    def __init__(self, settings: Settings):
        self._settings = settings

    def generate(self) -> RepoCatalogArtifacts:
        catalog_dir = Path(self._settings.rag_catalog_dir).resolve()
        catalog_dir.mkdir(parents=True, exist_ok=True)
        repos = self._discover_repos()
        payload = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "repo_count": len(repos),
            "repos": repos,
        }
        json_path = catalog_dir / "repo_catalog.json"
        md_path = catalog_dir / "repo_catalog.md"
        json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        md_path.write_text(self._build_markdown(payload), encoding="utf-8")
        logger.info(
            "catalog.repo.generated",
            repo_count=len(repos),
            json_path=str(json_path),
            md_path=str(md_path),
        )
        return RepoCatalogArtifacts(json_path, md_path, payload)

    def _discover_repos(self) -> list[dict]:
        cache_root = Path(self._settings.rag_repo_cache_dir).resolve()
        if not cache_root.exists():
            return []

        repo_dirs: list[Path] = []
        for child in cache_root.iterdir():
            if child.is_dir() and (child / ".git").exists():
                repo_dirs.append(child)
                continue
            if child.is_dir():
                for nested in child.iterdir():
                    if nested.is_dir() and (nested / ".git").exists():
                        repo_dirs.append(nested)

        repos: list[dict] = []
        for repo_dir in sorted(repo_dirs):
            readme_path = self._find_readme(repo_dir)
            summary = self._summary_from_readme(readme_path)
            repos.append(
                {
                    "name": repo_dir.name,
                    "path": str(repo_dir),
                    "last_updated": datetime.fromtimestamp(
                        repo_dir.stat().st_mtime, timezone.utc
                    ).isoformat(),
                    "languages": self._detect_languages(repo_dir),
                    "summary": summary,
                }
            )
        return repos

    def _find_readme(self, repo_dir: Path) -> Path | None:
        for name in ("README.md", "README.MD", "readme.md"):
            p = repo_dir / name
            if p.exists():
                return p
        return None

    def _summary_from_readme(self, readme_path: Path | None) -> str:
        if not readme_path:
            return "No README found. Repository summary unavailable."
        try:
            text = readme_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return "README unreadable. Repository summary unavailable."
        for line in text.splitlines():
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            return s[:220]
        return "README has no concise summary line."

    def _detect_languages(self, repo_dir: Path) -> list[str]:
        ext_to_lang = {
            ".py": "Python",
            ".js": "JavaScript",
            ".ts": "TypeScript",
            ".tsx": "TypeScript",
            ".jsx": "JavaScript",
            ".go": "Go",
            ".java": "Java",
            ".rb": "Ruby",
            ".rs": "Rust",
            ".cs": "C#",
            ".cpp": "C++",
            ".c": "C",
        }
        counts: Counter[str] = Counter()
        scanned = 0
        for f in repo_dir.rglob("*"):
            if scanned >= self._settings.rag_catalog_repo_max_files:
                break
            if not f.is_file():
                continue
            if ".git" in f.parts or "__pycache__" in f.parts:
                continue
            scanned += 1
            lang = ext_to_lang.get(f.suffix.lower())
            if lang:
                counts[lang] += 1
        return [lang for lang, _ in counts.most_common(3)]

    def _build_markdown(self, payload: dict) -> str:
        lines = [
            "# Repository Catalog",
            "",
            f"Generated at: {payload['generated_at']}",
            f"Repository count: {payload['repo_count']}",
            "",
        ]
        for repo in payload["repos"]:
            langs = ", ".join(repo["languages"]) if repo["languages"] else "Unknown"
            lines.extend(
                [
                    f"## {repo['name']}",
                    f"- Path: {repo['path']}",
                    f"- Last updated: {repo['last_updated']}",
                    f"- Languages: {langs}",
                    f"- Summary: {repo['summary']}",
                    "",
                ]
            )
        return "\n".join(lines).strip() + "\n"
