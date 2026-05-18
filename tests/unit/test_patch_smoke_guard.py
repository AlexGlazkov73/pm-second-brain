from pathlib import Path
from pm_second_brain.patch import apply_with_smoke_guard

TRIVIAL = """--- a/SKILL.md
+++ b/SKILL.md
@@ -1,1 +1,1 @@
-hello   
+hello
"""

def fake_smoke_ok(_): return True
def fake_smoke_fail(_): return False

def test_smoke_pass_keeps_change(tmp_path):
    f = tmp_path / "SKILL.md"
    f.write_text("hello   \n")
    apply_with_smoke_guard(f, TRIVIAL, history_root=tmp_path/"_h", smoke=fake_smoke_ok)
    assert f.read_text() == "hello\n"

def test_smoke_fail_auto_reverts(tmp_path):
    f = tmp_path / "SKILL.md"
    f.write_text("hello   \n")
    apply_with_smoke_guard(f, TRIVIAL, history_root=tmp_path/"_h", smoke=fake_smoke_fail)
    assert f.read_text() == "hello   \n"
