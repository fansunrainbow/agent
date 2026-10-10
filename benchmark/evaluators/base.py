from __future__ import annotations

from abc import ABC, abstractmethod

from benchmark.models import BenchmarkCase, CaseOutcome


class Evaluator(ABC):
    suite: str

    @abstractmethod
    def evaluate(self, case: BenchmarkCase) -> CaseOutcome:
        raise NotImplementedError
