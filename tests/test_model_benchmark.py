import json

from core.model_benchmark import LocalModelBenchmark
from core.models import ModelInfo


class FakeProvider:
    name = "fake"
    def health(self): return True
    def available_models(self): return [ModelInfo("a", "fake"), ModelInfo("b", "fake")]
    def chat(self, messages, model=None, **kwargs): return "x" * (20 if model == "a" else 40)
    def stream_chat(self, messages, model=None, **kwargs):
        size = 20 if model == "a" else 40
        yield "x" * (size // 2)
        yield "x" * (size - size // 2)


class Clock:
    def __init__(self): self.value = 0.0
    def __call__(self):
        current = self.value
        self.value += 0.5
        return current


def test_benchmark_model_reports_first_token_latency_and_throughput():
    bench = LocalModelBenchmark(FakeProvider(), clock=Clock())
    result = bench.benchmark_model("a", runs=2)
    assert result.successful_runs == 2
    assert result.avg_first_token_seconds == 0.5
    assert result.avg_latency_seconds == 1.0
    assert result.approx_output_tokens == 5.0
    assert result.approx_tokens_per_second == 5.0


def test_task_prompt_can_be_selected_without_hardcoding_model_choice():
    bench = LocalModelBenchmark(FakeProvider(), clock=Clock())
    result = bench.benchmark_model("a", task="coding", runs=1)
    assert result.successful_runs == 1


def test_benchmark_all_and_save_v2_report(tmp_path):
    bench = LocalModelBenchmark(FakeProvider(), clock=Clock())
    results = bench.benchmark_all(runs=1, task="general")
    path = bench.save(results, tmp_path / "report.json", task="general")
    data = json.loads(path.read_text())
    assert data["schema"] == 2
    assert data["task"] == "general"
    assert [item["model"] for item in data["results"]] == ["a", "b"]
    assert "avg_first_token_seconds" in data["results"][0]
