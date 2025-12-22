@echo off
echo ========================================
echo 重启 Odoo 并强制更新 diecut_custom 模块
echo ========================================
echo.

REM 激活虚拟环境
call venv\Scripts\activate.bat

echo 正在停止 Odoo 服务...
echo (如果有正在运行的 Odoo 进程,请手动关闭)
timeout /t 3

echo.
echo 正在启动 Odoo 并更新模块...
python odoo\odoo-bin -c odoo.conf -u diecut_custom --stop-after-init

echo.
echo ========================================
echo 模块更新完成!
echo 现在正常启动 Odoo...
echo ========================================
echo.

python odoo\odoo-bin -c odoo.conf

pause
