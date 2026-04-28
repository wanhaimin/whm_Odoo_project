# -*- coding: utf-8 -*-
"""diecut_knowledge 开发闭环

把「升级模块 → 跑 Playwright 冒烟测试」串起来，一条命令完成开发验证。

用法：
    cd E:/workspace/my_odoo_project
    .venv/Scripts/python.exe custom_addons/diecut_knowledge/scripts/dev_loop.py [选项]

选项：
    --skip-upgrade     跳过 docker exec 升级模块（只跑 Playwright）
    --skip-e2e         只升级模块，不跑 Playwright
    --headed           可视化运行 Playwright（默认 headless）
    --slowmo MS        Playwright 操作放慢毫秒数

退出码：
    0  全部通过
    1  e2e 失败
    2  模块升级失败
"""

from __future__ import annotations

import argparse
import io
import os
import shutil
import subprocess
import sys
from pathlib import Path

if sys.platform.startswith("win"):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    else:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parents[3]
SMOKE_SCRIPT = PROJECT_ROOT / "custom_addons" / "diecut_knowledge" / "tests" / "e2e" / "smoke.py"

CONTAINER = os.environ.get("ODOO_CONTAINER", "my_odoo_project_devcontainer-web-1")
DB_NAME = os.environ.get("ODOO_DB", "odoo")
DB_HOST = os.environ.get("ODOO_DB_HOST", "db")
DB_USER = os.environ.get("ODOO_DB_USER", "odoo")
DB_PASSWORD = os.environ.get("ODOO_DB_PASSWORD", "odoo")
MODULE = "diecut_knowledge"


def _section(title: str):
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60, flush=True)


def upgrade_module() -> int:
    _section(f"Upgrading module: {MODULE}")
    cmd = [
        "docker", "exec", CONTAINER,
        "odoo", "-d", DB_NAME, "-u", MODULE,
        "--stop-after-init", "--no-http",
        f"--db_host={DB_HOST}", f"--db_user={DB_USER}", f"--db_password={DB_PASSWORD}",
    ]
    print("  $ " + " ".join(cmd))
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    output = (proc.stdout or "") + (proc.stderr or "")
    last = output.strip().splitlines()[-12:]
    for line in last:
        print("  " + line)

    has_critical = any(
        marker in output
        for marker in ("CRITICAL", "Failed to load registry", "Failed to initialize database",
                       "MissingDependency", "ParseError", "ValidationError")
    )
    if proc.returncode != 0 or has_critical:
        print(f"\n[FAIL] module upgrade failed (returncode={proc.returncode})")
        return 2
    print("\n[OK] module upgraded cleanly")
    return 0


def run_e2e(headed: bool = False, slowmo: int = 0) -> int:
    _section(f"Running Playwright smoke: {SMOKE_SCRIPT.relative_to(PROJECT_ROOT)}")
    if not SMOKE_SCRIPT.is_file():
        print(f"[FAIL] smoke script not found: {SMOKE_SCRIPT}")
        return 1

    python_exe = sys.executable
    venv_python = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
    if venv_python.exists() and shutil.which(python_exe) != str(venv_python):
        python_exe = str(venv_python)

    env = os.environ.copy()
    env["HEADLESS"] = "0" if headed else "1"
    env["SLOWMO_MS"] = str(slowmo)

    cmd = [python_exe, str(SMOKE_SCRIPT)]
    print(f"  $ HEADLESS={env['HEADLESS']} SLOWMO_MS={env['SLOWMO_MS']} {python_exe} {SMOKE_SCRIPT.name}")
    proc = subprocess.run(cmd, env=env)
    return proc.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="diecut_knowledge dev loop")
    parser.add_argument("--skip-upgrade", action="store_true", help="跳过模块升级")
    parser.add_argument("--skip-e2e", action="store_true", help="跳过 Playwright e2e")
    parser.add_argument("--headed", action="store_true", help="可视化运行 Playwright")
    parser.add_argument("--slowmo", type=int, default=0, help="Playwright 操作放慢毫秒")
    args = parser.parse_args()

    if not args.skip_upgrade:
        rc = upgrade_module()
        if rc != 0:
            return rc

    if not args.skip_e2e:
        rc = run_e2e(headed=args.headed, slowmo=args.slowmo)
        if rc != 0:
            return rc

    _section("ALL GREEN")
    print("  ✓ module upgraded")
    print("  ✓ e2e smoke passed")
    print("\n下一步建议：检查 output/playwright/diecut_knowledge/ 下的截图")
    return 0


if __name__ == "__main__":
    sys.exit(main())
