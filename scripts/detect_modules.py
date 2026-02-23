#!/usr/bin/env python3
"""Detect OpenSPP modules that need testing based on changed files.

Features:
- Detects which modules have changed files
- Finds modules that depend on changed modules (reverse dependencies)
- Outputs JSON for GitHub Actions matrix

Usage:
    # From changed files list (stdin)
    git diff --name-only origin/19.0...HEAD | python scripts/detect_modules.py

    # Include critical modules on PRs
    git diff --name-only origin/19.0...HEAD | python scripts/detect_modules.py --include-critical

    # Get all modules with tests
    python scripts/detect_modules.py --all
"""

import argparse
import ast
import json
import os
import sys
from pathlib import Path

# Critical modules that should always be tested on PRs
CRITICAL_MODULES = {"spp_security", "spp_registry", "spp_programs", "spp_base_common", "spp_demo"}


def parse_manifest(manifest_path: Path) -> dict:
    """Parse an Odoo __manifest__.py file using AST (safe eval).

    Handles files with comments, imports, and other statements
    by walking the AST to find the dictionary expression.
    """
    try:
        source = manifest_path.read_text()
        tree = ast.parse(source, filename=str(manifest_path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Expr) and isinstance(node.value, ast.Dict):
                return ast.literal_eval(node.value)
    except (SyntaxError, ValueError):
        pass
    return {}


def is_odoo_module(module_path: Path) -> bool:
    """Check if a directory is an Odoo module."""
    return (module_path / "__manifest__.py").exists()


def has_tests(module_path: Path) -> bool:
    """Check if module has a tests directory with test files."""
    tests_directory = module_path / "tests"
    if not tests_directory.exists():
        return False
    return any(f.name.startswith("test_") and f.suffix == ".py" for f in tests_directory.iterdir())


def get_module_depends(module_path: Path) -> list[str]:
    """Extract dependencies from module's __manifest__.py."""
    manifest = parse_manifest(module_path / "__manifest__.py")
    return manifest.get("depends", [])


def discover_modules(project_root: Path) -> list[str]:
    """Find all Odoo module directories in the project root."""
    return [entry.name for entry in project_root.iterdir() if entry.is_dir() and is_odoo_module(entry)]


def build_reverse_dependency_graph(project_root: Path, all_modules: list[str]) -> dict[str, set[str]]:
    """Build reverse dependency graph: module -> set of modules that depend on it."""
    reverse_deps: dict[str, set[str]] = {}

    for module_name in all_modules:
        module_path = project_root / module_name
        for dep in get_module_depends(module_path):
            if dep not in reverse_deps:
                reverse_deps[dep] = set()
            reverse_deps[dep].add(module_name)

    return reverse_deps


def get_impacted_modules(
    changed_modules: set[str],
    reverse_deps: dict[str, set[str]],
    max_depth: int = 3,
) -> set[str]:
    """Get all modules impacted by changes (recursive reverse dependencies)."""
    impacted = set(changed_modules)
    frontier = set(changed_modules)

    for _ in range(max_depth):
        next_frontier: set[str] = set()
        for module in frontier:
            if module in reverse_deps:
                for dependent in reverse_deps[module]:
                    if dependent not in impacted:
                        impacted.add(dependent)
                        next_frontier.add(dependent)
        if not next_frontier:
            break
        frontier = next_frontier

    return impacted


def is_code_relevant(file_path: str) -> bool:
    """Check if a changed file is relevant for testing (not just docs/static)."""
    p = Path(file_path)
    parts = p.parts
    # Skip top-level README (auto-generated)
    if p.name == "README.rst":
        return False
    # Skip readme fragments directory
    if len(parts) > 1 and parts[1] == "readme":
        return False
    # Skip static/description (auto-generated index.html, icons, etc.)
    if len(parts) > 2 and parts[1] == "static" and parts[2] == "description":
        return False
    return True


def extract_modules_from_files(changed_files: list[str], all_modules: set[str]) -> set[str]:
    """Extract module names from changed file paths.

    Only considers code-relevant files (ignores READMEs, static descriptions).
    """
    modules: set[str] = set()
    for file_path in changed_files:
        parts = Path(file_path).parts
        if parts and parts[0] in all_modules and is_code_relevant(file_path):
            modules.add(parts[0])
    return modules


def main():
    parser = argparse.ArgumentParser(description="Detect modules to test")
    parser.add_argument("--all", action="store_true", help="List all modules with tests")
    parser.add_argument(
        "--include-critical",
        action="store_true",
        help="Always include critical modules",
    )
    parser.add_argument(
        "--output",
        choices=["json", "list", "matrix"],
        default="matrix",
        help="Output format",
    )
    parser.add_argument(
        "--max-modules",
        type=int,
        default=20,
        help="Maximum number of modules to test (0 = unlimited)",
    )
    args = parser.parse_args()

    # Get project root
    script_directory = Path(__file__).parent
    project_root = script_directory.parent
    os.chdir(project_root)

    # Discover all Odoo modules
    all_modules = discover_modules(project_root)
    all_module_names = set(all_modules)

    # Build dependency graph
    reverse_deps = build_reverse_dependency_graph(project_root, all_modules)

    if args.all:
        # List all modules with tests (no limit for --all)
        modules_to_test = {m for m in all_modules if has_tests(project_root / m)}
        args.max_modules = 0
    else:
        # Read changed files from stdin
        changed_files = [line.strip() for line in sys.stdin if line.strip()]

        if not changed_files:
            if args.output == "matrix":
                print(json.dumps([]))
            else:
                print("")
            return

        # Extract directly changed modules
        changed_modules = extract_modules_from_files(changed_files, all_module_names)

        # Get impacted modules (those that depend on changed modules)
        impacted = get_impacted_modules(changed_modules, reverse_deps)

        # Add critical modules if requested
        if args.include_critical:
            impacted.update(CRITICAL_MODULES)

        # Filter to only modules that have tests and exist
        modules_to_test = {m for m in impacted if (project_root / m).exists() and has_tests(project_root / m)}

    # Sort for deterministic output
    sorted_modules = sorted(modules_to_test)

    # Apply max limit if set
    if args.max_modules > 0 and len(sorted_modules) > args.max_modules:
        # Prioritize critical modules
        critical_first = [m for m in sorted_modules if m in CRITICAL_MODULES]
        others = [m for m in sorted_modules if m not in CRITICAL_MODULES]
        sorted_modules = (critical_first + others)[: args.max_modules]
        print(
            f"Warning: Limited to {args.max_modules} modules",
            file=sys.stderr,
        )

    # Output in requested format
    if args.output == "matrix":
        print(json.dumps(sorted_modules))
    elif args.output == "json":
        print(json.dumps({"modules": sorted_modules, "count": len(sorted_modules)}))
    else:
        print("\n".join(sorted_modules))


if __name__ == "__main__":
    main()
