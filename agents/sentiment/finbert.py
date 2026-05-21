from dataclasses import dataclass

try:
    from transformers import pipeline
    _TRANSFORMERS_AVAILABLE = True
except ImportError:
    _TRANSFORMERS_AVAILABLE = False


@dataclass
class SentimentResult:
    label: str       # "positive" | "negative" | "neutral"
    score: float     # confidence 0.0–1.0
    compound: float  # -score for negative, +score for positive, 0.0 for neutral


_LABEL_SIGN = {"positive": 1.0, "negative": -1.0, "neutral": 0.0}


class FinBertSentiment:
    MODEL = "ProsusAI/finbert"

    def __init__(self):
        self._pipe = None

    def _load(self):
        if self._pipe is None and _TRANSFORMERS_AVAILABLE:
            self._pipe = pipeline(
                "text-classification",
                model=self.MODEL,
                truncation=True,
                max_length=512,
            )

    def analyze(self, text: str) -> SentimentResult:
        self._load()
        if self._pipe is None:
            return SentimentResult(label="neutral", score=0.5, compound=0.0)
        result = self._pipe(text)[0]
        label = result["label"].lower()
        score = float(result["score"])
        return SentimentResult(label=label, score=score, compound=_LABEL_SIGN.get(label, 0.0) * score)

    def batch_analyze(self, texts: list[str]) -> list[SentimentResult]:
        self._load()
        if self._pipe is None:
            return [SentimentResult("neutral", 0.5, 0.0) for _ in texts]
        raw = self._pipe(texts)
        results = []
        for r in raw:
            label = r["label"].lower()
            score = float(r["score"])
            results.append(SentimentResult(label=label, score=score, compound=_LABEL_SIGN.get(label, 0.0) * score))
        return results
