"""Regression tests for review-model routing in web_app.py.

Run with:
    python -m unittest tests/test_review_model_routing.py
"""

from __future__ import annotations

import ast
from pathlib import Path
import unittest


WEB_APP_PATH = Path(__file__).resolve().parents[1] / "web_app.py"


def load_tree() -> ast.Module:
    return ast.parse(WEB_APP_PATH.read_text(encoding="utf-8"), filename=str(WEB_APP_PATH))


def literal_assignments(tree: ast.Module) -> dict[str, object]:
    assignments: dict[str, object] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name):
            continue
        try:
            assignments[target.id] = ast.literal_eval(node.value)
        except (ValueError, TypeError):
            continue
    return assignments


def find_function(tree: ast.Module, name: str) -> ast.FunctionDef | ast.AsyncFunctionDef:
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    raise AssertionError(f"Function {name!r} was not found")


def complete_model_names(function: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str | None]:
    models: list[str | None] = []
    for node in ast.walk(function):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Attribute) or node.func.attr != "complete":
            continue
        if not isinstance(node.func.value, ast.Name) or node.func.value.id != "llm":
            continue

        model_keyword = next((keyword for keyword in node.keywords if keyword.arg == "model"), None)
        if model_keyword is None:
            models.append(None)
        elif isinstance(model_keyword.value, ast.Name):
            models.append(model_keyword.value.id)
        else:
            models.append(ast.unparse(model_keyword.value))
    return models


class ReviewModelRoutingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tree = load_tree()
        cls.assignments = literal_assignments(cls.tree)

    def test_quick_review_model_remains_deepseek_flash(self) -> None:
        self.assertEqual(self.assignments.get("QUICK_REVIEW_MODEL"), "deepseek-v4-flash")

    def test_detail_review_model_is_gemini_flash(self) -> None:
        self.assertEqual(self.assignments.get("DETAIL_REVIEW_MODEL"), "gemini-2.5-flash")

    def test_quick_review_uses_quick_review_model(self) -> None:
        function = find_function(self.tree, "review_homework")
        self.assertEqual(complete_model_names(function), ["QUICK_REVIEW_MODEL"])

    def test_explain_in_detail_uses_detail_review_model(self) -> None:
        function = find_function(self.tree, "explain_deep")
        self.assertEqual(complete_model_names(function), ["DETAIL_REVIEW_MODEL"])

    def test_help_me_improve_uses_detail_review_model(self) -> None:
        function = find_function(self.tree, "improve_practice")
        self.assertEqual(complete_model_names(function), ["DETAIL_REVIEW_MODEL"])


if __name__ == "__main__":
    unittest.main()
