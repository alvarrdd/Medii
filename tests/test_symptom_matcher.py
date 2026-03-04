from __future__ import annotations

import csv
from pathlib import Path
import sys

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.symptom_matcher import SymptomMatcher


class DummyEmbedder:
    """Simple deterministic embedder for tests."""

    def encode(
        self,
        texts,
        *,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False,
    ):
        vectors = []
        for text in texts:
            t = text.lower()
            vec = np.array(
                [
                    int("head" in t or "գլխ" in t),
                    int("fever" in t or "ջերմ" in t),
                    int("cough" in t or "հազ" in t),
                    int("stomach" in t or "որովայն" in t),
                ],
                dtype=np.float32,
            )
            if normalize_embeddings:
                norm = float(np.linalg.norm(vec))
                if norm > 0:
                    vec = vec / norm
            vectors.append(vec)
        return np.stack(vectors, axis=0)


def write_csv(path: Path, rows, header=None):
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        if header:
            writer.writerow(header)
        writer.writerows(rows)


def test_find_top_k_returns_ranked_diseases(tmp_path: Path):
    csv_path = tmp_path / "symptoms.csv"
    write_csv(
        csv_path,
        [
            ["headache with fever", "Flu"],
            ["dry cough and fever", "Flu"],
            ["stomach pain", "Gastritis"],
            ["chronic headache", "Migraine"],
        ],
        header=["symptom", "disease"],
    )
    matcher = SymptomMatcher(csv_path, embedder=DummyEmbedder())
    top = matcher.find_top_k("fever and cough", 2)
    assert top[0] == "Flu"
    assert len(top) == 2


def test_find_top_k_deduplicates_same_disease(tmp_path: Path):
    csv_path = tmp_path / "symptoms.csv"
    write_csv(
        csv_path,
        [
            ["headache", "Migraine"],
            ["severe headache", "Migraine"],
            ["stomach pain", "Gastritis"],
        ],
        header=["symptom", "disease"],
    )
    matcher = SymptomMatcher(csv_path, embedder=DummyEmbedder())
    top = matcher.find_top_k("headache", 2)
    assert top[0] == "Migraine"
    assert top.count("Migraine") == 1


def test_missing_csv_raises():
    with pytest.raises(FileNotFoundError):
        SymptomMatcher("/tmp/does-not-exist.csv", embedder=DummyEmbedder())


def test_empty_csv_raises(tmp_path: Path):
    csv_path = tmp_path / "empty.csv"
    write_csv(csv_path, [], header=["symptom", "disease"])
    with pytest.raises(ValueError, match="no valid"):
        SymptomMatcher(csv_path, embedder=DummyEmbedder())


def test_invalid_k_raises(tmp_path: Path):
    csv_path = tmp_path / "symptoms.csv"
    write_csv(csv_path, [["headache", "Migraine"]], header=["symptom", "disease"])
    matcher = SymptomMatcher(csv_path, embedder=DummyEmbedder())
    with pytest.raises(ValueError, match="positive integer"):
        matcher.find_top_k("headache", 0)


def test_empty_symptoms_raises(tmp_path: Path):
    csv_path = tmp_path / "symptoms.csv"
    write_csv(csv_path, [["headache", "Migraine"]], header=["symptom", "disease"])
    matcher = SymptomMatcher(csv_path, embedder=DummyEmbedder())
    with pytest.raises(ValueError, match="non-empty"):
        matcher.find_top_k("   ", 1)


def test_headerless_csv_supported(tmp_path: Path):
    csv_path = tmp_path / "symptoms_no_header.csv"
    write_csv(
        csv_path,
        [
            ["հազ և ջերմություն", "Flu"],
            ["որովայնի ցավ", "Gastritis"],
        ],
        header=None,
    )
    matcher = SymptomMatcher(csv_path, has_header=False, embedder=DummyEmbedder())
    top = matcher.find_top_k("հազ", 1)
    assert top == ["Flu"]
