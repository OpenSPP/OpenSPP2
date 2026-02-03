"""
Common utilities for OpenSPP linting scripts.

Provides:
- Configuration loading from .openspp-lint.yaml
- Severity levels (ERROR, WARNING, INFO)
- Output formatters (text, json, github)
- Violation base class
"""

import json
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import yaml


class Severity(Enum):
    """Violation severity levels."""

    ERROR = "error"  # Must fix before merge
    WARNING = "warning"  # Should fix
    INFO = "info"  # Suggestion


@dataclass
class Violation:
    """Represents a linting violation."""

    file_path: str
    line: int
    message: str
    rule_id: str
    severity: Severity = Severity.ERROR
    column: int = 0
    suggestion: str | None = None  # Suggested fix
    doc_link: str | None = None  # Link to documentation

    def __str__(self):
        severity_icon = {
            Severity.ERROR: "❌",
            Severity.WARNING: "⚠️ ",
            Severity.INFO: "ℹ️ ",
        }
        loc = f"{self.file_path}:{self.line}"
        if self.column:
            loc += f":{self.column}"
        return f"{severity_icon[self.severity]} {loc}: {self.message}"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON output."""
        return {
            "file": self.file_path,
            "line": self.line,
            "column": self.column,
            "message": self.message,
            "rule_id": self.rule_id,
            "severity": self.severity.value,
            "suggestion": self.suggestion,
            "doc_link": self.doc_link,
        }

    def to_github_annotation(self) -> str:
        """Format as GitHub Actions annotation."""
        level = "error" if self.severity == Severity.ERROR else "warning"
        msg = self.message.replace("\n", "%0A")
        return f"::{level} file={self.file_path},line={self.line},col={self.column}::{msg}"


@dataclass
class LintConfig:
    """Configuration for OpenSPP linting."""

    # Module-specific overrides
    module_overrides: dict[str, dict] = field(default_factory=dict)

    # Global rule settings
    rules: dict[str, dict] = field(default_factory=dict)

    # Severity overrides
    severity_overrides: dict[str, str] = field(default_factory=dict)

    # Files/patterns to ignore
    ignore_patterns: list[str] = field(default_factory=list)

    @classmethod
    def load(cls, path: Path | None = None) -> "LintConfig":
        """Load configuration from file."""
        if path is None:
            # Search for config in standard locations
            search_paths = [
                Path.cwd() / ".openspp-lint.yaml",
                Path.cwd() / ".openspp-lint.yml",
                Path.cwd() / "pyproject.toml",  # Could add support later
            ]
            for p in search_paths:
                if p.exists():
                    path = p
                    break

        if path is None or not path.exists():
            return cls()  # Return defaults

        try:
            with open(path) as f:
                data = yaml.safe_load(f) or {}

            return cls(
                module_overrides=data.get("modules", {}),
                rules=data.get("rules", {}),
                severity_overrides=data.get("severity", {}),
                ignore_patterns=data.get("ignore", []),
            )
        except Exception as e:
            print(f"Warning: Could not load config from {path}: {e}", file=sys.stderr)
            return cls()

    def get_module_config(self, module_name: str) -> dict:
        """Get configuration for a specific module."""
        return self.module_overrides.get(module_name, {})

    def get_rule_config(self, rule_name: str) -> dict:
        """Get configuration for a specific rule."""
        return self.rules.get(rule_name, {})

    def get_severity(self, rule_id: str, default: Severity = Severity.ERROR) -> Severity:
        """Get severity for a rule (with overrides)."""
        override = self.severity_overrides.get(rule_id)
        if override:
            try:
                return Severity(override)
            except ValueError:
                pass
        return default

    def should_ignore(self, file_path: str) -> bool:
        """Check if a file should be ignored."""
        import fnmatch

        for pattern in self.ignore_patterns:
            if fnmatch.fnmatch(file_path, pattern):
                return True
        return False


class OutputFormatter:
    """Formats violation output in various formats."""

    def __init__(self, format_type: str = "text"):
        self.format_type = format_type

    def format(self, violations: list[Violation], show_summary: bool = True) -> str:
        """Format violations list."""
        if self.format_type == "json":
            return self._format_json(violations)
        elif self.format_type == "github":
            return self._format_github(violations)
        else:
            return self._format_text(violations, show_summary)

    def _format_text(self, violations: list[Violation], show_summary: bool) -> str:
        """Format as human-readable text."""
        if not violations:
            return "✓ No violations found"

        lines = []

        # Group by severity
        errors = [v for v in violations if v.severity == Severity.ERROR]
        warnings = [v for v in violations if v.severity == Severity.WARNING]
        infos = [v for v in violations if v.severity == Severity.INFO]

        if errors:
            lines.append("\n=== ERRORS (must fix) ===")
            for v in sorted(errors, key=lambda x: (x.file_path, x.line)):
                lines.append(str(v))
                if v.suggestion:
                    lines.append(f"    💡 Suggestion: {v.suggestion}")
                if v.doc_link:
                    lines.append(f"    📖 See: {v.doc_link}")

        if warnings:
            lines.append("\n=== WARNINGS (should fix) ===")
            for v in sorted(warnings, key=lambda x: (x.file_path, x.line)):
                lines.append(str(v))
                if v.suggestion:
                    lines.append(f"    💡 Suggestion: {v.suggestion}")

        if infos:
            lines.append("\n=== INFO (suggestions) ===")
            for v in sorted(infos, key=lambda x: (x.file_path, x.line)):
                lines.append(str(v))

        if show_summary:
            lines.append(f"\nSummary: {len(errors)} error(s), {len(warnings)} warning(s), {len(infos)} info")

        return "\n".join(lines)

    def _format_json(self, violations: list[Violation]) -> str:
        """Format as JSON."""
        data = {
            "violations": [v.to_dict() for v in violations],
            "summary": {
                "total": len(violations),
                "errors": len([v for v in violations if v.severity == Severity.ERROR]),
                "warnings": len([v for v in violations if v.severity == Severity.WARNING]),
                "info": len([v for v in violations if v.severity == Severity.INFO]),
            },
        }
        return json.dumps(data, indent=2)

    def _format_github(self, violations: list[Violation]) -> str:
        """Format as GitHub Actions annotations."""
        lines = [v.to_github_annotation() for v in violations]
        return "\n".join(lines)


def get_summary_stats(violations: list[Violation]) -> dict[str, Any]:
    """Get summary statistics for violations."""
    by_file = {}
    by_rule = {}
    by_severity = {"error": 0, "warning": 0, "info": 0}

    for v in violations:
        # Count by file
        if v.file_path not in by_file:
            by_file[v.file_path] = 0
        by_file[v.file_path] += 1

        # Count by rule
        if v.rule_id not in by_rule:
            by_rule[v.rule_id] = 0
        by_rule[v.rule_id] += 1

        # Count by severity
        by_severity[v.severity.value] += 1

    return {
        "total": len(violations),
        "by_severity": by_severity,
        "by_file": dict(sorted(by_file.items(), key=lambda x: -x[1])[:10]),  # Top 10
        "by_rule": dict(sorted(by_rule.items(), key=lambda x: -x[1])),
        "files_affected": len(by_file),
    }


def print_summary(violations: list[Violation]):
    """Print a summary report."""
    stats = get_summary_stats(violations)

    print("\n" + "=" * 60)
    print("OpenSPP Lint Summary")
    print("=" * 60)

    print(f"\nTotal violations: {stats['total']}")
    print(f"  ❌ Errors:   {stats['by_severity']['error']}")
    print(f"  ⚠️  Warnings: {stats['by_severity']['warning']}")
    print(f"  ℹ️  Info:     {stats['by_severity']['info']}")

    print(f"\nFiles affected: {stats['files_affected']}")

    if stats["by_rule"]:
        print("\nViolations by rule:")
        for rule, count in stats["by_rule"].items():
            print(f"  {rule}: {count}")

    if stats["by_file"]:
        print("\nTop files with violations:")
        for file, count in list(stats["by_file"].items())[:5]:
            print(f"  {file}: {count}")


# Standard argument parser additions
def add_common_args(parser):
    """Add common arguments to an argument parser."""
    parser.add_argument(
        "--format", choices=["text", "json", "github"], default="text", help="Output format (default: text)"
    )
    parser.add_argument("--summary", action="store_true", help="Show summary statistics")
    parser.add_argument("--config", type=Path, help="Path to .openspp-lint.yaml config file")
    parser.add_argument(
        "--severity",
        choices=["error", "warning", "info", "all"],
        default="all",
        help="Minimum severity to report (default: all)",
    )
