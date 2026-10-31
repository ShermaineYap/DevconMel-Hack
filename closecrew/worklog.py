"""The agents' work log: who did what, based on which evidence, and how it was checked."""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class LogEntry:
    at: str
    agent: str
    action: str
    detail: str
    verified: str = ""
    ms: int = 0


@dataclass
class WorkLog:
    run_id: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("run-%Y%m%dT%H%M%SZ"))
    entries: list[LogEntry] = field(default_factory=list)

    def add(self, agent: str, action: str, detail: str = "", verified: str = "", started: float | None = None) -> None:
        ms = int((time.perf_counter() - started) * 1000) if started else 0
        self.entries.append(LogEntry(datetime.now(timezone.utc).isoformat(timespec="seconds"), agent, action,
                                     detail, verified, ms))

    def to_markdown(self, header: str = "") -> str:
        lines = [f"## {self.run_id}" + (f" · {header}" if header else ""), "",
                 "| time (UTC) | agent | action | evidence / detail | verification |", "|---|---|---|---|---|"]
        for e in self.entries:
            cell = lambda s: (s or "").replace("|", "\\|").replace("\n", " ")  # noqa: E731
            lines.append(f"| {e.at[11:19]} | **{e.agent}** | {cell(e.action)} | {cell(e.detail)} | {cell(e.verified)} |")
        return "\n".join(lines) + "\n\n"

    def flush(self, state_dir: Path, header: str = "") -> None:
        state_dir.mkdir(parents=True, exist_ok=True)
        md = state_dir / "AGENT_LOG.md"
        if not md.exists():
            md.write_text("# CloseCrew agent work log\n\nEvery run appends a table: which agent acted, on what "
                          "evidence, and how the result was verified.\n\n", encoding="utf-8")
        with open(md, "a", encoding="utf-8") as f:
            f.write(self.to_markdown(header))
        with open(state_dir / "agent_log.jsonl", "a", encoding="utf-8") as f:
            for e in self.entries:
                f.write(json.dumps({"run": self.run_id, **asdict(e)}) + "\n")
