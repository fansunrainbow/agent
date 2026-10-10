from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta
import re
from typing import Any

from agent.models import GroundedCondition
from agent.services.metadata_store import MetadataStore


class TimeParser:
    """Normalize explicit time expressions without inventing a reference date."""

    _CN_NUMBERS = {
        "一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6,
        "七": 7, "八": 8, "九": 9, "十": 10,
    }

    def __init__(self, store: MetadataStore | None = None):
        self.store = store or MetadataStore()
        self.source = self.store.source("time_semantics.yaml")

    @staticmethod
    def _year(value: str) -> int:
        number = int(value)
        return number + 2000 if number < 100 else number

    @staticmethod
    def _iso(year: int, month: int, day: int) -> str:
        return date(year, month, day).isoformat()

    @staticmethod
    def _reference_date(context: dict[str, Any] | None) -> date | None:
        if not context:
            return None
        for key in ("reference_date", "context_date", "current_date"):
            value = context.get(key)
            if isinstance(value, date):
                return value
            if isinstance(value, str):
                try:
                    return datetime.fromisoformat(value[:10]).date()
                except ValueError:
                    continue
        return None

    def _resolved(self, condition_id: str, surface: str, value: dict[str, Any]) -> GroundedCondition:
        return GroundedCondition(
            condition_id=condition_id,
            original_surface=surface,
            semantic_type="time",
            target=value["type"],
            value=value,
            source=self.source,
            confidence=1.0,
            patch_action="CHANGE_TIME_RANGE",
        )

    def _ambiguous(self, condition_id: str, surface: str, reason: str, question: str) -> GroundedCondition:
        return GroundedCondition(
            condition_id=condition_id,
            original_surface=surface,
            semantic_type="time",
            source=self.source,
            confidence=0.0,
            status="ambiguous",
            reason=reason,
            question=question,
        )

    def parse(
        self,
        query: str,
        condition_id: str = "c1",
        context: dict[str, Any] | None = None,
    ) -> GroundedCondition | None:
        # Explicit date ranges have priority over their component dates/months.
        range_pattern = re.compile(
            r"(?P<y1>\d{2,4})[年/-](?P<m1>1[0-2]|0?[1-9])[月/-](?P<d1>3[01]|[12]\d|0?[1-9])日?"
            r"\s*(?:到|至|~|—|－|-)\s*"
            r"(?:(?P<y2>\d{2,4})[年/-])?(?P<m2>1[0-2]|0?[1-9])[月/-](?P<d2>3[01]|[12]\d|0?[1-9])日?"
        )
        match = range_pattern.search(query)
        if match:
            y1 = self._year(match.group("y1"))
            y2 = self._year(match.group("y2")) if match.group("y2") else y1
            try:
                value = {
                    "type": "date_range",
                    "start": self._iso(y1, int(match.group("m1")), int(match.group("d1"))),
                    "end": self._iso(y2, int(match.group("m2")), int(match.group("d2"))),
                }
            except ValueError:
                return self._ambiguous(condition_id, match.group(0), "日期范围包含无效日期。", "请提供有效的开始日期和结束日期。")
            return self._resolved(condition_id, match.group(0), value)

        iso_range = re.search(r"(?P<start>\d{4}-\d{2}-\d{2})\s*(?:到|至|~|—|－)\s*(?P<end>\d{4}-\d{2}-\d{2})", query)
        if iso_range:
            try:
                date.fromisoformat(iso_range.group("start"))
                date.fromisoformat(iso_range.group("end"))
            except ValueError:
                return self._ambiguous(condition_id, iso_range.group(0), "日期范围包含无效日期。", "请提供有效的 ISO 日期范围。")
            return self._resolved(condition_id, iso_range.group(0), {
                "type": "date_range", "start": iso_range.group("start"), "end": iso_range.group("end"),
            })

        month_range = re.search(
            r"(?P<year>\d{2,4})年(?P<start>1[0-2]|0?[1-9])月\s*(?:到|至|~|—|－|-)\s*(?P<end>1[0-2]|0?[1-9])月",
            query,
        )
        if month_range:
            year = self._year(month_range.group("year"))
            start_month, end_month = int(month_range.group("start")), int(month_range.group("end"))
            if end_month < start_month:
                return self._ambiguous(condition_id, month_range.group(0), "同一年内结束月份早于开始月份。", "请确认月份范围或分别提供起止年份。")
            return self._resolved(condition_id, month_range.group(0), {
                "type": "date_range",
                "start": self._iso(year, start_month, 1),
                "end": self._iso(year, end_month, calendar.monthrange(year, end_month)[1]),
            })

        absolute = re.search(r"(?P<year>\d{2,4})[年/-](?P<month>1[0-2]|0?[1-9])[月/-](?P<day>3[01]|[12]\d|0?[1-9])日?", query)
        if absolute:
            try:
                value = self._iso(self._year(absolute.group("year")), int(absolute.group("month")), int(absolute.group("day")))
            except ValueError:
                return self._ambiguous(condition_id, absolute.group(0), "日期无效。", "请提供有效日期。")
            return self._resolved(condition_id, absolute.group(0), {"type": "absolute_date", "date": value})

        quarter = re.search(
            r"(?:(?P<year>\d{2,4})年?)?(?:[Qq](?P<q1>[1-4])|第?(?P<q2>[一二三四1-4])季度)",
            query,
        )
        if quarter:
            raw_q = quarter.group("q1") or quarter.group("q2")
            q = self._CN_NUMBERS.get(raw_q, int(raw_q) if raw_q.isdigit() else 0)
            if quarter.group("year"):
                period: dict[str, Any] = {"type": "quarter", "year": self._year(quarter.group("year")), "quarter": q}
            else:
                reference = self._reference_date(context)
                if reference is None:
                    return self._ambiguous(
                        condition_id, quarter.group(0), "季度表达缺少年份，且上下文没有可靠参考日期。",
                        "请补充季度对应的年份，例如“2026年Q1”。",
                    )
                period = {"type": "quarter", "year": reference.year, "quarter": q}
            wrapper = "end_of_period" if re.search(r"(?:末|期末)", query[quarter.start():quarter.end() + 3]) else (
                "start_of_period" if re.search(r"(?:初|期初)", query[quarter.start():quarter.end() + 3]) else None
            )
            value = {"type": wrapper, "period": period} if wrapper else period
            return self._resolved(condition_id, quarter.group(0), value)

        month = re.search(r"(?:(?P<year>\d{2,4})年)?(?P<month>1[0-2]|0?[1-9])月", query)
        if month:
            if month.group("year"):
                year = self._year(month.group("year"))
            else:
                reference = self._reference_date(context)
                if reference is None:
                    return self._ambiguous(
                        condition_id, month.group(0), "月份表达缺少年份，且上下文没有可靠参考日期。",
                        "请补充月份对应的年份，例如“2026年3月”。",
                    )
                year = reference.year
            return self._resolved(condition_id, month.group(0), {"type": "month", "year": year, "month": int(month.group("month"))})

        relative = re.search(r"(?:最近|近)(?P<n>\d+|[一二三四五六七八九十]+)(?P<unit>天|日|个?月)", query)
        if relative:
            raw_n = relative.group("n")
            n = int(raw_n) if raw_n.isdigit() else self._CN_NUMBERS.get(raw_n)
            if n is None:
                return self._ambiguous(condition_id, relative.group(0), "无法可靠解析相对时间数量。", "请使用阿拉伯数字说明时间窗口，例如“最近30天”。")
            reference = self._reference_date(context)
            if reference is None:
                return self._ambiguous(
                    condition_id, relative.group(0), "相对时间需要参考日期，但当前上下文未提供可靠参考日期。",
                    f"“{relative.group(0)}”需要计算基准。请提供参考日期或改用明确的起止日期。",
                )
            if "月" in relative.group("unit"):
                total = reference.year * 12 + reference.month - 1 - n
                start_year, start_month0 = divmod(total, 12)
                start = date(start_year, start_month0 + 1, min(reference.day, calendar.monthrange(start_year, start_month0 + 1)[1]))
            else:
                start = reference - timedelta(days=n - 1)
            return self._resolved(condition_id, relative.group(0), {
                "type": "date_range", "start": start.isoformat(), "end": reference.isoformat(),
            })

        reference = self._reference_date(context)
        for marker in ("本季度", "上季度", "本月", "上月"):
            if marker not in query:
                continue
            if reference is None:
                return self._ambiguous(
                    condition_id, marker, f"“{marker}”依赖当前参考日期，但上下文未提供。",
                    f"请提供参考日期，或把“{marker}”改写为明确的年份和月份/季度。",
                )
            if "季度" in marker:
                quarter_no = (reference.month - 1) // 3 + 1
                year = reference.year
                if marker == "上季度":
                    quarter_no -= 1
                    if quarter_no == 0:
                        year -= 1
                        quarter_no = 4
                return self._resolved(condition_id, marker, {"type": "quarter", "year": year, "quarter": quarter_no})
            year, month_no = reference.year, reference.month
            if marker == "上月":
                month_no -= 1
                if month_no == 0:
                    year -= 1
                    month_no = 12
            return self._resolved(condition_id, marker, {"type": "month", "year": year, "month": month_no})

        year = re.search(r"(?P<year>\d{2,4})年", query)
        if year:
            return self._resolved(condition_id, year.group(0), {"type": "year", "year": self._year(year.group("year"))})

        if "最新" in query or "当前" in query:
            marker = "最新" if "最新" in query else "当前"
            return self._resolved(condition_id, marker, {"type": "latest"})
        if "近期" in query or re.search(r"最近(?!\d|[一二三四五六七八九十])", query):
            marker = "近期" if "近期" in query else "最近"
            return self._ambiguous(
                condition_id, marker, "相对时间窗口没有明确长度。",
                f"请明确“{marker}”的时间窗口，例如“最近30天”，并提供参考日期；也可以直接给出起止日期。",
            )
        return None
