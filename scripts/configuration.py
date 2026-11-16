"""Internal interpretation and validation of the user-editable Python settings.

Users: edit analysis_settings.py, NOT this file.
"""
from dataclasses import dataclass, field
from datetime import date, timedelta
from calendar import monthrange
from importlib import import_module


def as_date(value):
    return date.fromisoformat(str(value))


def add_months(d, months):
    """Equivalent to SQL Server DATEADD(month, months, date) for positive months."""
    total = d.year * 12 + d.month - 1 + months
    year, month0 = divmod(total, 12)
    month = month0 + 1
    return date(year, month, min(d.day, monthrange(year, month)[1]))


@dataclass(frozen=True)
class Window:
    name: str
    start_months: int
    end_months: int
    key: str = ""


@dataclass
class Settings:
    name: str
    birth_start: date
    birth_end: date
    exposure_age_start: int
    exposure_age_end: int
    min_rx: int
    rx_mode: str
    excluded_terms: list[str]
    windows: list[Window]
    primary_window: str
    ga_calendar_start: date
    ga_calendar_end: date
    rx_source_start: date
    rx_source_end: date
    ga_source_start: date
    ga_source_end: date
    require_complete_coverage: bool = True
    adjust_for: list[str] = field(default_factory=lambda: ["ethnicity", "deprivation", "birth_year"])
    ci_draws: int = 2500
    seed: int = 20261112

    @property
    def primary(self):
        return next(w for w in self.windows if w.name == self.primary_window)

    def validate(self):
        if self.birth_start > self.birth_end:
            raise ValueError("birth_start must be on or before birth_end")
        if not self.windows:
            raise ValueError("Define at least one GA age window")
        if len({w.key for w in self.windows}) != len(self.windows):
            raise ValueError("The GA windows must use different age boundaries")
        if len({w.name for w in self.windows}) != len(self.windows):
            raise ValueError("The GA windows must use different labels")
        if self.primary_window not in [w.name for w in self.windows]:
            raise ValueError("primary_ga_window must match a name in ga_windows")
        if not (0 <= self.exposure_age_start < self.exposure_age_end <= 240):
            raise ValueError("Check exposure start/end ages (months)")
        if self.min_rx < 1 or self.rx_mode not in ("distinct_dates", "records"):
            raise ValueError("Use min_prescriptions >= 1 and prescription_count_mode 'distinct_dates' or 'records'")
        if any(not (0 <= w.start_months < w.end_months <= 240) for w in self.windows):
            raise ValueError("GA age windows must have increasing month boundaries")
        if not set(self.adjust_for).issubset({"ethnicity", "deprivation", "birth_year"}):
            raise ValueError("Supported adjustment variables: ethnicity, deprivation, birth_year")
        if self.ga_calendar_start > self.ga_calendar_end:
            raise ValueError("ga_calendar_start must be on or before ga_calendar_end")
        if self.ci_draws < 200:
            raise ValueError("For CI simulation, use ci_draws >= 200")
        if self.require_complete_coverage:
            if add_months(self.birth_start, self.exposure_age_start) < self.rx_source_start:
                raise ValueError("Prescription window starts before available source records. Narrow births or exposure ages.")
            if add_months(self.birth_end, self.exposure_age_end) > self.rx_source_end + timedelta(days=1):
                raise ValueError("Prescription window ends after available source records. Narrow births or exposure ages.")
            for w in self.windows:
                if add_months(self.birth_start, w.start_months) < self.ga_source_start:
                    raise ValueError(f"GA window '{w.name}' begins before available GA records. Narrow births or ages.")
                if add_months(self.birth_end, w.end_months) > self.ga_source_end + timedelta(days=1):
                    raise ValueError(f"GA window '{w.name}' ends after available GA records. Narrow births or ages.")
        if not (self.ga_source_start <= self.ga_calendar_start <= self.ga_calendar_end <= self.ga_source_end):
            raise ValueError("Selected GA calendar years must be within source coverage")


def load_settings(module_name="analysis_settings"):
    """Load the Python settings module."""
    if not isinstance(module_name, str):
        module = module_name
    else:
        if module_name.endswith(".py"):
            module_name = module_name[:-3]
        if "/" in module_name or "\\" in module_name:
            raise ValueError("Pass a settings filename in this folder, e.g. analysis_settings")
        module = import_module(module_name)
    windows = [Window(
        name=str(label), start_months=int(start), end_months=int(end),
        key=f"ga_{int(start)}_{int(end)}"
    ) for label, start, end in module.ga_windows]
    cfg = Settings(
        name=str(module.name),
        birth_start=as_date(module.birth_start), birth_end=as_date(module.birth_end),
        exposure_age_start=int(module.exposure_age_start_months),
        exposure_age_end=int(module.exposure_age_end_months),
        min_rx=int(module.min_prescriptions),
        rx_mode=str(module.prescription_count_mode),
        excluded_terms=list(module.exclude_medication_name_contains),
        windows=windows, primary_window=str(module.primary_ga_window),
        ga_calendar_start=as_date(module.ga_calendar_start),
        ga_calendar_end=as_date(module.ga_calendar_end),
        rx_source_start=as_date(module.prescription_source_start),
        rx_source_end=as_date(module.prescription_source_end),
        ga_source_start=as_date(module.ga_source_start),
        ga_source_end=as_date(module.ga_source_end),
        require_complete_coverage=bool(module.require_complete_coverage),
        adjust_for=list(module.adjust_for),
        ci_draws=int(module.ci_draws), seed=int(module.random_seed),
    )
    cfg.validate()
    return cfg
