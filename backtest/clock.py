from datetime import datetime, timedelta
from typing import Iterator


class BacktestClock:
    def __init__(self, start: datetime, end: datetime, step_seconds: int):
        self.start = start
        self.end = end
        self.step_seconds = step_seconds

    def ticks(self) -> Iterator[datetime]:
        current = self.start
        while current <= self.end:
            yield current
            current += timedelta(seconds=self.step_seconds)

    def __len__(self) -> int:
        if self.end < self.start:
            return 0
        return int((self.end - self.start).total_seconds() / self.step_seconds) + 1
