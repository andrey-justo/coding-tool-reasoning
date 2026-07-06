from __future__ import annotations

import re


class ComplexityMetricsStrategy:
    """Complexity metrics based on lightweight static heuristics."""

    @staticmethod
    def _strip_comments(line: str) -> str:
        line = re.sub(r"//.*$", "", line)
        line = re.sub(r"#.*$", "", line)
        return line

    @staticmethod
    def _non_empty_lines(code: str) -> list[str]:
        lines: list[str] = []
        for raw in code.splitlines():
            line = raw.rstrip()
            if line.strip():
                lines.append(line)
        return lines

    def cyclomatic_complexity(self, code: str) -> int:
        """Approximate cyclomatic complexity using decision-point counting."""
        decision_pattern = re.compile(
            r"\b(if|elif|for|while|case|catch|except|when)\b|\?|&&|\|\|",
            re.IGNORECASE,
        )
        complexity = 1
        for line in self._non_empty_lines(code):
            clean = self._strip_comments(line)
            complexity += len(decision_pattern.findall(clean))
        return complexity

    def cognitive_complexity(self, code: str) -> int:
        """Approximate cognitive complexity with nesting penalties."""
        control_pattern = re.compile(
            r"\b(if|elif|else if|for|while|case|catch|except|switch|when)\b",
            re.IGNORECASE,
        )
        boolean_pattern = re.compile(r"&&|\|\||\band\b|\bor\b", re.IGNORECASE)

        score = 0
        brace_depth = 0
        indent_stack: list[int] = [0]

        for raw in self._non_empty_lines(code):
            line = self._strip_comments(raw)
            stripped = line.lstrip()
            if not stripped:
                continue

            indent = len(line) - len(stripped)
            while len(indent_stack) > 1 and indent < indent_stack[-1]:
                indent_stack.pop()
            if indent > indent_stack[-1]:
                indent_stack.append(indent)

            nesting = max(brace_depth, len(indent_stack) - 1)

            control_matches = len(control_pattern.findall(stripped))
            if control_matches:
                score += control_matches * (1 + nesting)

            score += len(boolean_pattern.findall(stripped))

            opens = stripped.count("{")
            closes = stripped.count("}")
            brace_depth = max(0, brace_depth + opens - closes)

        return score

    def compute(self, code: str) -> dict[str, int]:
        return {
            "cognitive_complexity": self.cognitive_complexity(code),
            "cyclomatic_complexity": self.cyclomatic_complexity(code),
        }
