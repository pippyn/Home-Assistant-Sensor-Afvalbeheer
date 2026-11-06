"""Keep release metadata and translated configuration schemas consistent."""
import ast
import json
from pathlib import Path
import re

import pytest


ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = ROOT / "custom_components" / "afvalbeheer"


def _keys(value, prefix=""):
    """Return nested keys, including branches, to catch schema drift."""
    result = set()
    for key, child in value.items():
        path = f"{prefix}.{key}" if prefix else key
        result.add(path)
        if isinstance(child, dict):
            result.update(_keys(child, path))
    return result


def test_release_versions_match():
    module = ast.parse((INTEGRATION / "__init__.py").read_text())
    versions = [ast.literal_eval(node.value) for node in module.body
                if isinstance(node, ast.Assign)
                and any(isinstance(target, ast.Name) and target.id == "__version__" for target in node.targets)]
    doc_version = re.search(r"Current Version: (\S+) (\d{8})", ast.get_docstring(module))
    assert doc_version is not None
    versions.extend([
        doc_version.group(1),
        json.loads((INTEGRATION / "manifest.json").read_text())["version"],
        json.loads((ROOT / "custom_components.json").read_text())["sensor.afvalbeheer"]["version"],
    ])
    assert len(set(versions)) == 1, f"Release version mismatch: {versions}"


@pytest.mark.parametrize("translation", sorted((INTEGRATION / "translations").glob("*.json")), ids=lambda p: p.stem)
def test_translation_keys_match_english(translation):
    expected = _keys(json.loads((INTEGRATION / "translations" / "en.json").read_text()))
    actual = _keys(json.loads(translation.read_text()))
    assert actual == expected, f"Missing: {sorted(expected - actual)}; extra: {sorted(actual - expected)}"
