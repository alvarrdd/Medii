"""Compute slide-ready evaluation metrics for Medi experiments."""

from __future__ import annotations

import csv
import time
from pathlib import Path
from statistics import mean

from backend.config import get_settings
from backend.preprocessor import SymptomPreprocessor
from backend.faiss_search import SymptomDiseaseIndexer
from backend.specialist_mapper import SpecialistMapper


def norm(text: str) -> str:
    return " ".join((text or "").strip().lower().split())


def split_specialists(value: str) -> list[str]:
    s = (value or "").replace(" և ", "/")
    return [norm(x) for x in s.split("/") if x.strip()]


def topk_hit(predicted: list[str], truth: str, k: int) -> bool:
    t = norm(truth)
    return any(norm(x) == t for x in predicted[:k])


def specialist_hit(predicted_specialist: str, truth_specialist: str) -> bool:
    p = norm(predicted_specialist)
    parts = split_specialists(truth_specialist)
    return any(part in p or p in part for part in parts)


def evaluate(mode: str, rows: list[dict[str, str]]) -> dict[str, float | str]:
    settings = get_settings()
    pre = SymptomPreprocessor()
    retriever = SymptomDiseaseIndexer(settings)
    mapper = SpecialistMapper.from_csv(settings.disease_specialist_csv)

    if mode == "baseline":
        # Force lexical-style baseline by simulating missing embedding model.
        retriever._settings = type(settings)(
            embedding_model_name="__missing_model__",
            rag_top_k=settings.rag_top_k,
            max_context_chars=settings.max_context_chars,
            similarity_threshold=settings.similarity_threshold,
            gemini_model_name=settings.gemini_model_name,
            gemini_api_key=settings.gemini_api_key,
            gemini_temperature=settings.gemini_temperature,
        )

    top1 = top3 = spec = 0
    latencies: list[float] = []

    for row in rows:
        symptoms = row["symptoms"]
        true_disease = row["true_disease"]
        true_specialist = row["true_specialist"]

        t0 = time.perf_counter()
        cleaned, parts = pre.preprocess(symptoms)

        if mode == "exp2":
            variants = [symptoms]
            if cleaned and cleaned != symptoms:
                variants.append(cleaned)
            if parts:
                joined = " ".join(parts).strip()
                if joined and joined not in variants:
                    variants.append(joined)
            candidates = {}
            for q in variants:
                for c in retriever.predict(q, top_k=8):
                    prev = candidates.get(c.name)
                    if prev is None or c.score > prev.score:
                        candidates[c.name] = c
            preds = sorted(candidates.values(), key=lambda x: x.score, reverse=True)[:5]
        elif mode == "exp1":
            preds = retriever.predict(cleaned or symptoms, top_k=5)
        else:  # baseline
            preds = retriever.predict(cleaned or symptoms, top_k=3)

        predicted_diseases = [p.name for p in preds]
        predicted_specialist = mapper.recommend(predicted_diseases)
        latencies.append((time.perf_counter() - t0) * 1000)

        top1 += int(topk_hit(predicted_diseases, true_disease, 1))
        top3 += int(topk_hit(predicted_diseases, true_disease, 3))
        spec += int(specialist_hit(predicted_specialist, true_specialist))

    n = max(1, len(rows))
    return {
        "Experiment": mode,
        "Top-1 Relevance": round(100 * top1 / n, 1),
        "Top-3 Relevance": round(100 * top3 / n, 1),
        "Specialist Correctness": round(100 * spec / n, 1),
        "Avg Latency (ms)": round(mean(latencies), 1),
    }


def main() -> None:
    eval_file = Path("eval_set.csv")
    if not eval_file.exists():
        raise FileNotFoundError("eval_set.csv not found")

    with eval_file.open("r", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    out_rows = [
        evaluate("baseline", rows),
        evaluate("exp1", rows),
        evaluate("exp2", rows),
    ]

    headers = [
        "Experiment",
        "Top-1 Relevance",
        "Top-3 Relevance",
        "Specialist Correctness",
        "Avg Latency (ms)",
    ]

    out_csv = Path("evaluation_results.csv")
    with out_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(out_rows)

    print("=== MEDI EXPERIMENT SUMMARY ===")
    print(" | ".join(headers))
    for r in out_rows:
        print(" | ".join(str(r[h]) for h in headers))
    print(f"\nSaved: {out_csv.resolve()}")


if __name__ == "__main__":
    main()
