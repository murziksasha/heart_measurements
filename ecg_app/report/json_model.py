"""Analysis report model shared by cloud (Viatom JSON) and local results."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from ..core.er1_format import REPORT_POS_RATE, SAMPLE_RATE

# code -> (uk, en)
EVENT_NAMES: dict[str, tuple[str, str]] = {
    "10000": ("Шлуночкова екстрасистола", "Ventricular premature beat (PVC)"),
    "13000": ("Максимальна ЧСС", "Maximum heart rate"),
    "13001": ("Мінімальна ЧСС", "Minimum heart rate"),
}
# Vendor Chinese names -> (uk, en), used when the code is unknown.
CN_NAMES: dict[str, tuple[str, str]] = {
    "室性早搏": EVENT_NAMES["10000"],
    "最大心率": EVENT_NAMES["13000"],
    "最小心率": EVENT_NAMES["13001"],
    "房性早搏": ("Передсердна екстрасистола", "Atrial premature beat (PAC)"),
    "室速": ("Шлуночкова тахікардія", "Ventricular tachycardia"),
    "室性心动过速": ("Шлуночкова тахікардія", "Ventricular tachycardia"),
    "房速": ("Передсердна тахікардія", "Atrial tachycardia"),
    "房颤": ("Фібриляція передсердь", "Atrial fibrillation"),
    "心房颤动": ("Фібриляція передсердь", "Atrial fibrillation"),
    "停搏": ("Пауза (асистолія)", "Pause (asystole)"),
    "长RR间期": ("Довгий інтервал RR", "Long RR interval"),
    "心动过缓": ("Брадикардія", "Bradycardia"),
    "心动过速": ("Тахікардія", "Tachycardia"),
    "室性二联律": ("Шлуночкова бігемінія", "Ventricular bigeminy"),
    "室性三联律": ("Шлуночкова тригемінія", "Ventricular trigeminy"),
    "房性二联律": ("Передсердна бігемінія", "Atrial bigeminy"),
    "房性三联律": ("Передсердна тригемінія", "Atrial trigeminy"),
    "成对室早": ("Парні шлуночкові екстрасистоли", "Ventricular couplet"),
    "成对房早": ("Парні передсердні екстрасистоли", "Atrial couplet"),
}
DIAGNOSES: dict[str, tuple[str, str]] = {
    "101": ("Нормальний синусовий ритм", "Normal sinus rhythm"),
    "142": ("Шлуночкова екстрасистолія (ШЕ)", "Premature Ventricular Contraction (PVC)"),
}
COUNTERS = {
    # key in JSON -> (uk, en)
    "ventricularPermatureBeatCount": ("Шлуночкові екстрасистоли", "PVC beats"),
    "coupleVentricularPermatureCount": ("Парні ШЕ", "PVC couplets"),
    "ventricularBigeminyCount": ("Шлуночкова бігемінія", "Ventricular bigeminy"),
    "ventricularTrigeminyCount": ("Шлуночкова тригемінія", "Ventricular trigeminy"),
    "ventricularTachycardiaCount": ("Шлуночкова тахікардія", "Ventricular tachycardia"),
    "atrialPermatureBeatCount": ("Передсердні екстрасистоли", "PAC beats"),
    "coupleAtrialPermatureCount": ("Парні ПЕ", "PAC couplets"),
    "atrialBigeminyCount": ("Передсердна бігемінія", "Atrial bigeminy"),
    "atrialTrigeminyCount": ("Передсердна тригемінія", "Atrial trigeminy"),
    "atrialTachycardiaCount": ("Передсердна тахікардія", "Atrial tachycardia"),
    "afBeatPercent": ("Фібриляція передсердь, % ударів", "AF, % of beats"),
    "longRRPeriodCount": ("Довгі інтервали RR", "Long RR intervals"),
    "asystoleRRPeriodCount": ("Паузи (асистолія)", "Pauses (asystole)"),
    "abnormalBeatCount": ("Аномальні удари", "Abnormal beats"),
}


def _int(v, default=0) -> int:
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return default


def _dt(v) -> Optional[datetime]:
    try:
        return datetime.strptime(str(v), "%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError):
        return None


def _pick(pair: tuple[str, str], lang: str) -> str:
    return pair[0] if lang == "uk" else pair[1]


@dataclass
class Diagnosis:
    code: str
    text: str  # vendor text (English)

    def label(self, lang: str = "uk") -> str:
        pair = DIAGNOSES.get(self.code)
        return _pick(pair, lang) if pair else f"{self.text} [{self.code}]"


@dataclass
class ReportEvent:
    code: str
    raw_name: str
    time: Optional[datetime]
    start_pos: int  # report position units (REPORT_POS_RATE Hz)
    end_pos: int
    hr: Optional[int] = None
    pos_rate: int = REPORT_POS_RATE

    @property
    def known(self) -> bool:
        return self.code in EVENT_NAMES

    def label(self, lang: str = "uk") -> str:
        pair = EVENT_NAMES.get(self.code) or CN_NAMES.get(self.raw_name)
        if pair and self.known:
            return _pick(pair, lang)
        base = _pick(pair, lang) if pair else (self.raw_name or "?")
        return f"{base} [{self.code}]"

    def sample_range(self, fs: int = SAMPLE_RATE) -> tuple[int, int]:
        """Event range as PCM sample indexes."""
        k = fs / self.pos_rate
        return int(self.start_pos * k), int(self.end_pos * k)


@dataclass
class Report:
    source: str  # "cloud" | "local"
    report_time: Optional[datetime] = None
    data_start: Optional[datetime] = None
    data_end: Optional[datetime] = None
    total_s: int = 0
    valid_s: int = 0
    avg_hr: Optional[int] = None
    max_hr: Optional[int] = None
    max_hr_time: Optional[datetime] = None
    min_hr: Optional[int] = None
    min_hr_time: Optional[datetime] = None
    beat_count: int = 0
    counters: dict = field(default_factory=dict)
    diagnoses: list = field(default_factory=list)
    events: list = field(default_factory=list)
    pdf_url: Optional[str] = None
    ok: bool = True
    message: str = ""

    def unknown_codes(self) -> set:
        return {e.code for e in self.events if not e.known}

    def event_codes(self) -> list:
        return sorted({e.code for e in self.events})


def parse_cloud_report(payload: dict) -> Report:
    d = payload.get("data") or {}
    rep = Report(
        source="cloud",
        ok=_int(payload.get("code"), 0) == 200,
        message=str(payload.get("msg") or ""),
        report_time=_dt(d.get("reportTime")),
        data_start=_dt(d.get("dataStartTime")),
        data_end=_dt(d.get("dataEndTime")),
        total_s=_int(d.get("totalDuration")),
        valid_s=_int(d.get("validDuration")),
        avg_hr=_int(d.get("averageHeartRate"), None),
        max_hr=_int(d.get("maxHeartRate"), None),
        max_hr_time=_dt(d.get("maxHeartRateTime")),
        min_hr=_int(d.get("minHeartRate"), None),
        min_hr_time=_dt(d.get("minHeartRateTime")),
        beat_count=_int(d.get("beatCount")),
        counters={k: d[k] for k in COUNTERS if k in d},
        diagnoses=[Diagnosis(str(x.get("code", "")), str(x.get("diagnoseInfo", "")))
                   for x in d.get("diagnoseList") or []],
        pdf_url=d.get("analysisReport") or None,
    )
    seen = set()
    for e in (d.get("allEventList") or []) + (d.get("eventList") or []):
        code = str(e.get("eventCode", ""))
        key = (code, str(e.get("startPos")))
        if key in seen:
            continue
        seen.add(key)
        hr = rep.max_hr if code == "13000" else rep.min_hr if code == "13001" else _int(e.get("hr"), None)
        rep.events.append(ReportEvent(code=code, raw_name=str(e.get("eventName", "")), time=_dt(e.get("eventTime")),
                                      start_pos=_int(e.get("startPos")), end_pos=_int(e.get("endPos")), hr=hr))
    rep.events.sort(key=lambda e: e.start_pos)
    return rep


def parse_result(source: str, payload: dict) -> Report:
    """Entry point for analysis_results rows; local results (step 5/6) will store
    the same Viatom-like shape, so they parse identically."""
    rep = parse_cloud_report(payload)
    rep.source = source
    return rep
