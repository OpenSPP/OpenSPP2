#!/usr/bin/env python3
"""
Odoo 19 Compatibility Checker for OpenSPP

Validates code against Odoo 19 compatibility requirements:
- Command API: Detects (0, 0, ...) tuples, suggests Command.create() etc.
- Search view groups: Detects <group expand=...> or <group string=...> in search views
- XPath selectors: Detects @title in xpath expressions
- group_expand signature: Detects old 3-parameter _read_group_* methods

Features:
- Auto-fix support for Command API tuples (--fix)
- Dry-run mode to preview changes (--fix --dry-run)
- Multiple output formats (text, json, github)
- Configuration via .openspp-lint.yaml

Exit codes:
    0: No violations found (or --fix applied successfully)
    1: Violations found (errors or warnings based on config)

See: docs/principles/odoo19-compatibility.md
"""

import argparse
import ast
import re
import sys
from pathlib import Path

# Try lxml for better line number tracking, fall back to stdlib
try:
    from lxml import etree as ET

    LXML_AVAILABLE = True
except ImportError:
    from xml.etree import ElementTree as ET

    LXML_AVAILABLE = False

# Import common utilities
try:
    from .common import LintConfig, OutputFormatter, Severity, Violation, add_common_args, print_summary
except ImportError:
    from common import LintConfig, OutputFormatter, Severity, Violation, add_common_args, print_summary


# Command API tuple patterns
# Maps tuple first element to Command method
COMMAND_MAPPING = {
    0: ("Command.create", "vals"),  # (0, 0, vals) -> Command.create(vals)
    1: ("Command.update", "id, vals"),  # (1, id, vals) -> Command.update(id, vals)
    2: ("Command.delete", "id"),  # (2, id, 0) -> Command.delete(id)
    3: ("Command.unlink", "id"),  # (3, id, 0) -> Command.unlink(id)
    4: ("Command.link", "id"),  # (4, id, 0) -> Command.link(id)
    5: ("Command.clear", ""),  # (5, 0, 0) -> Command.clear()
    6: ("Command.set", "ids"),  # (6, 0, ids) -> Command.set(ids)
}

# Regex patterns for detection
TUPLE_PATTERN = re.compile(
    r"\(\s*([0-6])\s*,\s*"  # First element: 0-6
    r"([^,)]+)\s*,\s*"  # Second element
    r"([^)]+)\s*\)"  # Third element
)

# Search view group attributes pattern
SEARCH_GROUP_ATTRS = re.compile(r"<group\s+[^>]*(expand|string)\s*=", re.IGNORECASE)

# XPath @title pattern
XPATH_TITLE_PATTERN = re.compile(r"@title\s*[=\]]")

# group_expand old signature pattern
GROUP_EXPAND_PATTERN = re.compile(
    r"def\s+(_read_group_\w+|_group_expand_\w+)\s*\(\s*self\s*,\s*\w+\s*,\s*\w+\s*,\s*\w+\s*\)"
)


class CommandTupleVisitor(ast.NodeVisitor):
    """AST visitor to find Command API tuple patterns."""

    def __init__(self, source_lines: list[str]):
        self.violations: list[tuple[int, int, str, str]] = []  # (line, col, old, new)
        self.source_lines = source_lines

    def visit_Tuple(self, node: ast.Tuple):
        """Check if tuple matches Command API pattern."""
        if len(node.elts) != 3:
            self.generic_visit(node)
            return

        first = node.elts[0]
        # Check for integer constant (exclude booleans - bool is subclass of int)
        if not isinstance(first, ast.Constant) or not isinstance(first.value, int) or isinstance(first.value, bool):
            self.generic_visit(node)
            return

        cmd_num = first.value
        if cmd_num not in COMMAND_MAPPING:
            self.generic_visit(node)
            return

        # Found a potential Command API tuple
        method, _ = COMMAND_MAPPING[cmd_num]
        suggestion = self._build_suggestion(node, cmd_num)

        if suggestion:
            # Get the original source text for this tuple
            try:
                line_start = node.lineno - 1
                col_start = node.col_offset
                # For multi-line tuples, we need to handle carefully
                original = self._extract_source(node)
                self.violations.append((node.lineno, col_start, original, suggestion))
            except Exception:
                # If we can't extract source, still report the violation
                self.violations.append((node.lineno, col_start, "", suggestion))

        self.generic_visit(node)

    def _extract_source(self, node: ast.Tuple) -> str:
        """Extract original source code for a tuple node."""
        if hasattr(node, "end_lineno") and hasattr(node, "end_col_offset"):
            if node.lineno == node.end_lineno:
                # Single line
                line = self.source_lines[node.lineno - 1]
                return line[node.col_offset : node.end_col_offset]
            else:
                # Multi-line - extract all lines
                lines = []
                for i in range(node.lineno - 1, node.end_lineno):
                    if i == node.lineno - 1:
                        lines.append(self.source_lines[i][node.col_offset :])
                    elif i == node.end_lineno - 1:
                        lines.append(self.source_lines[i][: node.end_col_offset])
                    else:
                        lines.append(self.source_lines[i])
                return "\n".join(lines)
        return ""

    def _build_suggestion(self, node: ast.Tuple, cmd_num: int) -> str:
        """Build the Command.* replacement string."""
        method, _ = COMMAND_MAPPING[cmd_num]

        if cmd_num == 0:
            # (0, 0, vals) -> Command.create(vals)
            vals = ast.unparse(node.elts[2])
            return f"{method}({vals})"
        elif cmd_num == 1:
            # (1, id, vals) -> Command.update(id, vals)
            record_id = ast.unparse(node.elts[1])
            vals = ast.unparse(node.elts[2])
            return f"{method}({record_id}, {vals})"
        elif cmd_num in (2, 3, 4):
            # (2|3|4, id, 0) -> Command.delete|unlink|link(id)
            record_id = ast.unparse(node.elts[1])
            return f"{method}({record_id})"
        elif cmd_num == 5:
            # (5, 0, 0) -> Command.clear()
            return f"{method}()"
        elif cmd_num == 6:
            # (6, 0, ids) -> Command.set(ids)
            ids = ast.unparse(node.elts[2])
            return f"{method}({ids})"

        return ""


class Odoo19Checker:
    """Checks for Odoo 19 compatibility issues."""

    def __init__(self, config: LintConfig = None):
        self.config = config or LintConfig.load()

        # Load config settings
        rule_config = self.config.get_rule_config("odoo19")
        self.command_tuple_severity = Severity(rule_config.get("command_tuple_severity", "warning"))
        self.exclude_tests = rule_config.get("exclude_tests_from_command_check", True)

    def check_python_file(self, file_path: str) -> list[Violation]:
        """Check a Python file for Odoo 19 issues."""
        violations = []
        path = Path(file_path)

        if not path.exists() or path.suffix != ".py":
            return violations

        # Check if file should be ignored
        if self.config.should_ignore(file_path):
            return violations

        # Skip test files if configured
        if self.exclude_tests and "/tests/" in file_path:
            return violations

        try:
            with open(file_path, encoding="utf-8") as f:
                source = f.read()
                source_lines = source.splitlines()
        except Exception:
            return violations

        # Check Command API tuples using AST
        try:
            tree = ast.parse(source)
            visitor = CommandTupleVisitor(source_lines)
            visitor.visit(tree)

            for line, col, original, suggestion in visitor.violations:
                violations.append(
                    Violation(
                        file_path=file_path,
                        line=line,
                        column=col,
                        message=f"Use Command API instead of tuple: {suggestion}",
                        rule_id="odoo19.command_tuple",
                        severity=self.command_tuple_severity,
                        suggestion=f"Replace with: {suggestion}",
                        doc_link="docs/principles/odoo19-compatibility.md#command-api-odoo-19-pattern",
                    )
                )
        except SyntaxError:
            pass  # Skip files with syntax errors

        # Check group_expand signature using regex
        for i, line in enumerate(source_lines, 1):
            match = GROUP_EXPAND_PATTERN.search(line)
            if match:
                violations.append(
                    Violation(
                        file_path=file_path,
                        line=i,
                        message=f"group_expand method '{match.group(1)}' uses old 3-parameter signature",
                        rule_id="odoo19.group_expand_signature",
                        severity=Severity.ERROR,
                        suggestion="Remove 'order' parameter: def method(self, stages, domain)",
                        doc_link="docs/principles/odoo19-compatibility.md#group-expand-method-signature",
                    )
                )

        return violations

    def check_xml_file(self, file_path: str) -> list[Violation]:
        """Check an XML file for Odoo 19 issues."""
        violations = []
        path = Path(file_path)

        if not path.exists() or path.suffix != ".xml":
            return violations

        # Check if file should be ignored
        if self.config.should_ignore(file_path):
            return violations

        # Skip non-view files
        if not self._is_view_file(path):
            return violations

        try:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()
                lines = content.splitlines()
        except Exception:
            return violations

        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
        except Exception:  # Handle both lxml.etree.XMLSyntaxError and xml.etree.ParseError
            return violations

        # Check search view group attributes
        violations.extend(self._check_search_view_groups(file_path, root, lines))

        # Check XPath @title
        violations.extend(self._check_xpath_title(file_path, root, lines))

        return violations

    def _is_view_file(self, path: Path) -> bool:
        """Check if XML file contains view definitions."""
        return "views" in path.parts or "view" in path.name.lower() or "wizard" in path.parts

    def _check_search_view_groups(self, file_path: str, root: ET.Element, lines: list[str]) -> list[Violation]:
        """Check for <group expand=...> or <group string=...> in search views."""
        violations = []

        # Find search views
        for record in root.findall(".//record[@model='ir.ui.view']"):
            for arch in record.findall(".//field[@name='arch']"):
                for search in arch.findall(".//search"):
                    # Check groups inside search
                    for group in search.findall(".//group"):
                        expand = group.get("expand")
                        string = group.get("string")

                        if expand is not None or string is not None:
                            # Find line number by searching for the pattern
                            line_num = self._find_element_line(lines, group)
                            attrs = []
                            if expand is not None:
                                attrs.append(f'expand="{expand}"')
                            if string is not None:
                                attrs.append(f'string="{string}"')

                            violations.append(
                                Violation(
                                    file_path=file_path,
                                    line=line_num,
                                    message=f"Search view <group> has invalid attributes: {', '.join(attrs)}",
                                    rule_id="odoo19.search_group_attrs",
                                    severity=Severity.ERROR,
                                    suggestion="Remove expand/string attributes from <group> in search views",
                                    doc_link="docs/principles/odoo19-compatibility.md#search-view-groups",
                                )
                            )

        return violations

    def _check_xpath_title(self, file_path: str, root: ET.Element, lines: list[str]) -> list[Violation]:
        """Check for @title in xpath expressions."""
        violations = []

        for xpath in root.findall(".//xpath"):
            expr = xpath.get("expr", "")
            if XPATH_TITLE_PATTERN.search(expr):
                line_num = self._find_element_line(lines, xpath)
                violations.append(
                    Violation(
                        file_path=file_path,
                        line=line_num,
                        message=f"XPath uses @title selector: {expr}",
                        rule_id="odoo19.xpath_title",
                        severity=Severity.ERROR,
                        suggestion="Use name, class, or other valid attributes instead of @title",
                        doc_link="docs/principles/odoo19-compatibility.md#view-inheritance-selectors",
                    )
                )

        return violations

    def _find_element_line(self, lines: list[str], element: ET.Element) -> int:
        """Find line number for an XML element.

        Uses lxml's sourceline attribute if available, otherwise falls back
        to text-based search (which may be less accurate for multi-line elements).
        """
        # Try lxml's sourceline attribute first (most accurate)
        if hasattr(element, "sourceline") and element.sourceline:
            return element.sourceline

        # Fallback: search by tag and attributes in text
        # Note: This may be inaccurate if attributes span multiple lines
        tag = element.tag
        attrs = element.attrib

        for i, line in enumerate(lines, 1):
            if f"<{tag}" in line:
                # Check if key attributes match on this line
                match = True
                for key, value in attrs.items():
                    if f'{key}="{value}"' not in line and f"{key}='{value}'" not in line:
                        match = False
                        break
                if match:
                    return i

        return 0


class Odoo19Fixer:
    """Auto-fixer for Odoo 19 compatibility issues."""

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.files_modified = 0
        self.fixes_applied = 0

    def fix_python_file(self, file_path: str) -> tuple[bool, list[str]]:
        """
        Fix Command API tuples in a Python file.

        Returns:
            (success, changes): Whether fix was applied and list of changes made
        """
        path = Path(file_path)
        if not path.exists() or path.suffix != ".py":
            return False, []

        try:
            with open(file_path, encoding="utf-8") as f:
                original_content = f.read()
                source_lines = original_content.splitlines()
        except Exception as e:
            return False, [f"Error reading file: {e}"]

        # Parse and find tuples
        try:
            tree = ast.parse(original_content)
        except SyntaxError as e:
            return False, [f"Syntax error: {e}"]

        visitor = CommandTupleVisitor(source_lines)
        visitor.visit(tree)

        if not visitor.violations:
            return False, []

        changes = []
        modified_content = original_content

        # Check if Command is already imported
        has_command_import = self._has_command_import(original_content)

        # Apply fixes in reverse order (to preserve line numbers)
        sorted_violations = sorted(visitor.violations, key=lambda x: (-x[0], -x[1]))

        for line, col, original, suggestion in sorted_violations:
            if original and suggestion:
                # Replace the tuple with Command call
                modified_content = self._replace_in_content(modified_content, original, suggestion)
                changes.append(f"Line {line}: {original.strip()} -> {suggestion}")
                self.fixes_applied += 1

        # Add Command import if needed
        if not has_command_import and changes:
            modified_content = self._add_command_import(modified_content)
            changes.insert(0, "Added: from odoo import Command")

        if changes:
            if not self.dry_run:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(modified_content)
                self.files_modified += 1

            return True, changes

        return False, []

    def _has_command_import(self, content: str) -> bool:
        """Check if file already imports Command from odoo."""
        # Check for various import patterns
        patterns = [
            r"from\s+odoo\s+import\s+.*\bCommand\b",
            r"from\s+odoo\s+import\s+Command\b",
            r"from\s+odoo\.fields\s+import\s+Command\b",
        ]
        for pattern in patterns:
            if re.search(pattern, content):
                return True
        return False

    def _add_command_import(self, content: str) -> str:
        """Add Command to existing odoo import or create new import."""
        lines = content.splitlines(keepends=True)

        # Try to find existing "from odoo import ..." line
        for i, line in enumerate(lines):
            match = re.match(r"(from\s+odoo\s+import\s+)(.+)", line)
            if match:
                prefix, imports = match.groups()
                # Check if it's not a multi-line import or already has Command
                if "Command" not in imports and "(" not in imports:
                    # Add Command to imports
                    imports = imports.rstrip()
                    if imports.endswith(","):
                        new_line = f"{prefix}{imports} Command\n"
                    else:
                        new_line = f"{prefix}Command, {imports}\n"
                    lines[i] = new_line
                    return "".join(lines)

        # No existing import found, add after other odoo imports
        insert_idx = 0
        for i, line in enumerate(lines):
            if line.startswith("from odoo") or line.startswith("import odoo"):
                insert_idx = i + 1
            elif insert_idx > 0 and not line.startswith(("from", "import", "#", "\n")):
                break

        if insert_idx == 0:
            # No odoo imports, add after other imports or at start
            for i, line in enumerate(lines):
                if line.startswith(("from", "import")):
                    insert_idx = i + 1

        lines.insert(insert_idx, "from odoo import Command\n")
        return "".join(lines)

    def _replace_in_content(self, content: str, old: str, new: str) -> str:
        """Replace old pattern with new in content."""
        # Try direct replacement first (most common case)
        if old in content:
            return content.replace(old, new, 1)

        # Build a regex pattern that matches with flexible whitespace
        # Split by whitespace, escape each part, join with \s*
        old_normalized = r"\s*".join(map(re.escape, re.split(r"\s+", old.strip())))
        pattern = re.compile(old_normalized)

        # Try regex replacement for whitespace variations
        match = pattern.search(content)
        if match:
            return content[: match.start()] + new + content[match.end() :]

        return content


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Check files for Odoo 19 compatibility issues",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Check Python files
  python check_odoo19.py spp_programs/models/*.py

  # Check XML files
  python check_odoo19.py --xml spp_programs/views/*.xml

  # Auto-fix Command API tuples
  python check_odoo19.py --fix spp_programs/models/*.py

  # Dry-run to preview fixes
  python check_odoo19.py --fix --dry-run spp_programs/models/*.py
        """,
    )

    add_common_args(parser)
    parser.add_argument("files", nargs="*", help="Files to check")
    parser.add_argument("--xml", action="store_true", help="Check XML files for search view issues")
    parser.add_argument("--fix", action="store_true", help="Auto-fix Command API tuples")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be fixed without making changes")
    parser.add_argument("--module", help="Check all files in a module")

    args = parser.parse_args()

    # Load configuration
    config = LintConfig.load(args.config) if args.config else LintConfig.load()
    checker = Odoo19Checker(config)

    # Collect files to check
    files_to_check = []

    if args.module:
        module_path = Path(args.module)
        if not module_path.exists():
            module_path = Path.cwd() / args.module

        if args.xml:
            files_to_check.extend(module_path.glob("views/*.xml"))
            files_to_check.extend(module_path.glob("wizard/*.xml"))
        else:
            files_to_check.extend(module_path.glob("models/*.py"))
            files_to_check.extend(module_path.glob("wizard/*.py"))

    if args.files:
        files_to_check.extend(Path(f) for f in args.files)

    if not files_to_check:
        print("No files to check", file=sys.stderr)
        return 0

    # Fix mode
    if args.fix:
        fixer = Odoo19Fixer(dry_run=args.dry_run)

        for file_path in files_to_check:
            if str(file_path).endswith(".py"):
                success, changes = fixer.fix_python_file(str(file_path))
                if changes:
                    prefix = "[DRY-RUN] " if args.dry_run else ""
                    print(f"\n{prefix}{file_path}:")
                    for change in changes:
                        print(f"  {change}")

        if args.dry_run:
            print(f"\n[DRY-RUN] Would fix {fixer.fixes_applied} issues in {fixer.files_modified} files")
        else:
            print(f"\nFixed {fixer.fixes_applied} issues in {fixer.files_modified} files")

        return 0

    # Check mode
    all_violations = []

    for file_path in files_to_check:
        file_str = str(file_path)
        if args.xml or file_str.endswith(".xml"):
            violations = checker.check_xml_file(file_str)
        else:
            violations = checker.check_python_file(file_str)
        all_violations.extend(violations)

    # Filter by severity if specified
    if args.severity != "all":
        min_severity = Severity(args.severity)
        severity_order = [Severity.INFO, Severity.WARNING, Severity.ERROR]
        min_idx = severity_order.index(min_severity)
        all_violations = [v for v in all_violations if severity_order.index(v.severity) >= min_idx]

    # Output results
    formatter = OutputFormatter(args.format)
    output = formatter.format(all_violations, show_summary=args.summary)
    print(output)

    if args.summary:
        print_summary(all_violations)

    # Exit with error if violations found
    has_errors = any(v.severity == Severity.ERROR for v in all_violations)
    return 1 if has_errors else 0


if __name__ == "__main__":
    sys.exit(main())
