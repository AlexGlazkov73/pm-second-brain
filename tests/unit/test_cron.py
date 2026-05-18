from pm_second_brain.cron import render_launchd_plist, render_systemd_timer


def test_launchd_renders_with_cron_expr():
    p = render_launchd_plist(
        label="com.pm-second-brain.daily-brief",
        program="/usr/local/bin/opencode",
        args=["run", "--skill", "pm-workflow.pm-daily-brief", "--headless"],
        cron_expr="0 8 * * 1-5",
        log_path="/tmp/db.log",
    )
    assert "<key>Label</key>" in p
    assert "<string>com.pm-second-brain.daily-brief</string>" in p
    assert p.count("<key>Weekday</key>") == 5
    assert "<key>Hour</key>" in p
    assert "<string>/usr/local/bin/opencode</string>" in p
    assert "<string>--headless</string>" in p
    assert "<string>/tmp/db.log</string>" in p


def test_systemd_timer_renders():
    timer, service = render_systemd_timer(
        unit="pm-second-brain-daily-brief",
        exec_start="/usr/local/bin/opencode run --skill pm-workflow.pm-daily-brief --headless",
        cron_expr="0 8 * * 1-5",
    )
    assert "OnCalendar=Mon..Fri 08:00" in timer
    assert "ExecStart=/usr/local/bin/opencode" in service
    assert "[Timer]" in timer
    assert "[Service]" in service
