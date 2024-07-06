import asyncio
from datetime import datetime, timedelta
from typing import Annotated, List, Tuple

import pytest

from swiftbots import PeriodTrigger, depends, task
from swiftbots.functions import resolve_function_args
from swiftbots.tasks import SimpleScheduler


class Test:
    @pytest.mark.timeout(3)
    def test_dependency_injection(self):
        def dep2(s2: int):
            return s2 ** 3

        def dep1(s1: int, d2: Annotated[int, depends(dep2)]):
            return s1 ** 2, d2

        def caller(c: int, d1: Annotated[int, depends(dep1)]):
            return c, *d1

        data = {'s2': 5, 's1': 32, 'c': 12}
        args = resolve_function_args(caller, data)
        assert caller(**args) == (12, 32 ** 2, 5 ** 3)

    @pytest.mark.timeout(8)
    def test_simple_scheduler(self):
        logs: List[Tuple[str, int]] = []

        def get_now() -> datetime:
            return datetime.now()

        def compute_delta(now: Annotated[datetime, depends(get_now)], start_time_point: datetime) -> timedelta:
            return now - start_time_point

        @task(PeriodTrigger(seconds=2), run_at_start=False)
        async def logger1(logger_num: str, delta: Annotated[timedelta, depends(compute_delta)]):
            await asyncio.sleep(0)
            logs.append((logger_num, int(delta.total_seconds())))

        @task(PeriodTrigger(seconds=3), run_at_start=True)
        async def logger2(logger_num: str, delta: Annotated[timedelta, depends(compute_delta)]):
            await asyncio.sleep(0)
            logs.append((logger_num, int(delta.total_seconds())))

        start_point = datetime.now()
        data1 = {'logger_num': '1', 'start_time_point': start_point}
        data2 = {'logger_num': '2', 'start_time_point': start_point}

        def caller1():
            func = logger1.func
            args = resolve_function_args(func, data1)
            return func(**args)

        def caller2():
            func = logger2.func
            args = resolve_function_args(func, data2)
            return func(**args)

        sched = SimpleScheduler()
        sched.add_task(logger1, caller1)
        sched.add_task(logger2, caller2)

        async def start():
            task_logger = asyncio.create_task(sched.start())
            try:
                await asyncio.wait_for(task_logger, timeout=5.0)
            except asyncio.TimeoutError:
                return

        asyncio.run(start())
        assert tuple(logs) == (
            ('2', 0),
            ('1', 2),
            ('2', 3),
            ('1', 4)
        )


