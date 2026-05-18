"""Cron-expression renderers for macOS launchd and Linux systemd timers."""
from dataclasses import dataclass


@dataclass(frozen=True)
class CronExpr:
    minute: str
    hour: str
    dow: str


_DOW_NAMES = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]


def _parse_cron(expr: str) -> CronExpr:
    parts = expr.split()
    if len(parts) != 5:
        raise ValueError("cron expr must have 5 fields: minute hour dom month dow")
    return CronExpr(minute=parts[0], hour=parts[1], dow=parts[4])


def _expand_dow(dow: str) -> list[int]:
    if dow == "*":
        return list(range(0, 7))
    if "-" in dow:
        a, b = dow.split("-")
        return list(range(int(a), int(b) + 1))
    return [int(x) for x in dow.split(",")]


def render_launchd_plist(
    label: str,
    program: str,
    args: list[str],
    cron_expr: str,
    log_path: str,
) -> str:
    """Render a launchd plist for a calendar-scheduled job."""
    c = _parse_cron(cron_expr)
    intervals = []
    for d in _expand_dow(c.dow):
        intervals.append(
            "        <dict>\n"
            f"            <key>Weekday</key><integer>{d}</integer>\n"
            f"            <key>Hour</key><integer>{int(c.hour)}</integer>\n"
            f"            <key>Minute</key><integer>{int(c.minute)}</integer>\n"
            "        </dict>"
        )
    args_xml = "".join(f"        <string>{a}</string>\n" for a in [program, *args])
    intervals_xml = "\n".join(intervals)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<plist version="1.0">\n'
        "<dict>\n"
        f"    <key>Label</key><string>{label}</string>\n"
        "    <key>ProgramArguments</key>\n"
        "    <array>\n"
        f"{args_xml}"
        "    </array>\n"
        "    <key>StartCalendarInterval</key>\n"
        "    <array>\n"
        f"{intervals_xml}\n"
        "    </array>\n"
        f"    <key>StandardOutPath</key><string>{log_path}</string>\n"
        f"    <key>StandardErrorPath</key><string>{log_path}</string>\n"
        "</dict>\n"
        "</plist>\n"
    )


def render_systemd_timer(
    unit: str,
    exec_start: str,
    cron_expr: str,
) -> tuple[str, str]:
    """Return (timer_unit, service_unit) text for systemd."""
    c = _parse_cron(cron_expr)
    days = _expand_dow(c.dow)
    if days == list(range(1, 6)):
        day_str = "Mon..Fri"
    elif days == list(range(0, 7)):
        day_str = "*"
    else:
        day_str = ",".join(_DOW_NAMES[d] for d in days)
    on_calendar = f"{day_str} {int(c.hour):02d}:{int(c.minute):02d}"
    timer = (
        f"[Unit]\nDescription={unit}\n\n"
        f"[Timer]\nOnCalendar={on_calendar}\nPersistent=true\n\n"
        "[Install]\nWantedBy=timers.target\n"
    )
    service = (
        f"[Unit]\nDescription={unit}\n\n"
        f"[Service]\nType=oneshot\nExecStart={exec_start}\n"
    )
    return timer, service
