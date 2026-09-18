"""Portable local-model benchmark harness for Trinity's Mac runtime.

The benchmark deliberately measures performance rather than pretending to score
model intelligence. Run it on the actual M6 Mac mini 32 GB hardware, then use the report plus
response quality review to finalize Trinity's fast/general/reasoning/coding
routes.
"""
from __future__ import annotations

import argparse
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import mean
from typing import Callable, Iterable, Sequence

from core.models import ChatMessage, LocalModelProvider, OllamaProvider


@dataclass(frozen=True)
class BenchmarkResult:
    model: str
    provider: str
    runs: int
    successful_runs: int
    avg_latency_seconds: float | None
    avg_first_token_seconds: float | None
    approx_output_tokens: float | None
    approx_tokens_per_second: float | None
    error: str | None = None


class LocalModelBenchmark:
    """Measure local inference latency/throughput without runtime lock-in."""

    DEFAULT_PROMPT = (
        "Explain why a local AI assistant should separate memory from the language model "
        "in three concise bullet points."
    )

    TASK_PROMPTS = {
        "fast": "Reply with only the result: 37 + 58.",
        "general": DEFAULT_PROMPT,
        "reasoning": (
            "A service has three sequential stages with success probabilities 0.98, 0.97, "
            "and 0.99. Explain the end-to-end success probability and one reliability improvement."
        ),
        "coding": (
            "Write a concise Python function that deduplicates strings while preserving order, "
            "and include one assert-based test."
        ),
    }

    def __init__(
        self,
        provider: LocalModelProvider,
        *,
        clock: Callable[[], float] = time.perf_counter,
    ) -> None:
        self.provider = provider
        self.clock = clock

    @staticmethod
    def _approx_tokens(text: str) -> float:
        return max(1.0, len(text) / 4.0)

    def _stream_once(self, model: str, prompt: str) -> tuple[str, float, float]:
        start = self.clock()
        first_token: float | None = None
        chunks: list[str] = []
        stream = getattr(self.provider, "stream_chat", None)
        if callable(stream):
            for chunk in stream([ChatMessage("user", prompt)], model=model):
                if chunk and first_token is None:
                    first_token = max(self.clock() - start, 0.0)
                if chunk:
                    chunks.append(str(chunk))
            elapsed = max(self.clock() - start, 1e-9)
            if chunks:
                return "".join(chunks), elapsed, first_token or elapsed

        # Compatibility fallback for providers that do not expose streaming.
        text = self.provider.chat([ChatMessage("user", prompt)], model=model)
        elapsed = max(self.clock() - start, 1e-9)
        return str(text), elapsed, elapsed

    def benchmark_model(
        self,
        model: str,
        *,
        prompt: str | None = None,
        task: str | None = None,
        runs: int = 3,
    ) -> BenchmarkResult:
        if prompt is None:
            prompt = self.TASK_PROMPTS.get(task or "", self.DEFAULT_PROMPT)
        latencies: list[float] = []
        first_tokens: list[float] = []
        tokens: list[float] = []
        errors: list[str] = []

        for _ in range(max(1, runs)):
            try:
                text, elapsed, first = self._stream_once(model, prompt)
                latencies.append(elapsed)
                first_tokens.append(first)
                tokens.append(self._approx_tokens(text))
            except Exception as exc:
                errors.append(str(exc))

        if not latencies:
            return BenchmarkResult(
                model=model,
                provider=self.provider.name,
                runs=max(1, runs),
                successful_runs=0,
                avg_latency_seconds=None,
                avg_first_token_seconds=None,
                approx_output_tokens=None,
                approx_tokens_per_second=None,
                error=errors[-1] if errors else "benchmark failed",
            )

        avg_latency = mean(latencies)
        avg_tokens = mean(tokens)
        return BenchmarkResult(
            model=model,
            provider=self.provider.name,
            runs=max(1, runs),
            successful_runs=len(latencies),
            avg_latency_seconds=round(avg_latency, 4),
            avg_first_token_seconds=round(mean(first_tokens), 4),
            approx_output_tokens=round(avg_tokens, 2),
            approx_tokens_per_second=round(avg_tokens / avg_latency, 2),
            error=errors[-1] if errors else None,
        )

    def benchmark_all(
        self,
        models: Iterable[str] | None = None,
        *,
        prompt: str | None = None,
        task: str | None = None,
        runs: int = 3,
    ) -> list[BenchmarkResult]:
        if models is None:
            models = [item.name for item in self.provider.available_models()]
        return [
            self.benchmark_model(model, prompt=prompt, task=task, runs=runs)
            for model in models
        ]

    @staticmethod
    def save(
        results: Iterable[BenchmarkResult],
        path: str | Path,
        *,
        task: str | None = None,
    ) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema": 2,
            "task": task,
            "results": [asdict(result) for result in results],
        }
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        return path


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Benchmark Trinity local Ollama models")
    parser.add_argument("--models", nargs="*", help="Model names; default: all installed models")
    parser.add_argument("--task", choices=["fast", "general", "reasoning", "coding"], default="general")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--output", default="memory/runtime/model_benchmark.json")
    parser.add_argument("--base-url", default="http://127.0.0.1:11434")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    provider = OllamaProvider(base_url=args.base_url)
    if not provider.health():
        print(f"Ollama is not available at {args.base_url}")
        return 1
    benchmark = LocalModelBenchmark(provider)
    results = benchmark.benchmark_all(
        models=args.models or None,
        task=args.task,
        runs=max(1, args.runs),
    )
    path = benchmark.save(results, args.output, task=args.task)
    for result in results:
        print(
            f"{result.model}: first={result.avg_first_token_seconds}s "
            f"total={result.avg_latency_seconds}s approx={result.approx_tokens_per_second} tok/s "
            f"({result.successful_runs}/{result.runs} runs)"
        )
    print(f"Saved benchmark report: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
