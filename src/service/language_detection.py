from __future__ import annotations

from pathlib import Path

_EXTENSION_TO_LANGUAGE = {
    ".py": "python",
    ".cs": "c#",
    ".java": "java",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".go": "go",
    ".rs": "rust",
    ".php": "php",
    ".rb": "ruby",
    ".kt": "kotlin",
    ".swift": "swift",
    ".c": "c",
    ".cc": "c++",
    ".cpp": "c++",
    ".h": "c/c++",
    ".hpp": "c++",
}

_LANGUAGE_MARKERS = [
    ("python", ["python", "py ", "pytest", "pydantic", "django", "fastapi"]),
    ("javascript", ["javascript", "js ", "node", "npm", "express", "react"]),
    ("typescript", ["typescript", "ts ", "tsx", "nestjs", "angular"]),
    ("java", [" java", "spring", "maven", "gradle", "junit"]),
    ("c#", ["c#", "dotnet", ".net", "asp.net"]),
    ("go", [" golang", " go ", "goroutine", "go.mod"]),
    ("rust", ["rust", "cargo", "tokio"]),
    ("ruby", ["ruby", "rails", "rspec"]),
    ("php", ["php", "laravel", "composer"]),
    ("kotlin", ["kotlin", "ktor"]),
    ("swift", ["swift", "xcode", "ios"]),
]


def infer_language_from_file_paths(file_paths: list[str] | None) -> str | None:
    if not file_paths:
        return None

    language_counts: dict[str, int] = {}
    for file_path in file_paths:
        ext = Path(file_path).suffix.lower()
        language = _EXTENSION_TO_LANGUAGE.get(ext)
        if not language:
            continue
        language_counts[language] = language_counts.get(language, 0) + 1

    if not language_counts:
        return None

    return max(language_counts.items(), key=lambda item: item[1])[0]


def infer_language_from_text(text: str) -> str | None:
    text_lower = text.lower()
    for language, markers in _LANGUAGE_MARKERS:
        for marker in markers:
            if marker in text_lower:
                return language
    return None
