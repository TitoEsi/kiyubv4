"""Rule result types. No module imports (avoids package cycles)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

RuleStatus = Literal["PASS", "FAIL", "WARNING", "UNKNOWN"]


@dataclass
class RuleResult:
    code: str
    status: RuleStatus
    message: str
    source: str = ""
    module: str = "common"

    def as_dict(self) -> dict:
        return {
            "code": self.code,
            "status": self.status,
            "message": self.message,
            "source": self.source,
            "module": self.module,
        }
