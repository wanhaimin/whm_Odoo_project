@echo off
echo ========================================
echo 升级 diecut_custom 模块
echo ========================================
echo.

REM 激活虚拟环境
call venv\Scripts\activate.bat

echo 正在升级模块...
python odoo\odoo-bin -c odoo.conf -u diecut_custom --stop-after-init

echo.
echo 升级完成!
pause
