@echo off
echo ========================================
echo 清除缓存并重新启动 Odoo
echo ========================================
echo.

REM 激活虚拟环境
call venv\Scripts\activate.bat

echo 正在清除 Odoo 缓存...
if exist "odoo\__pycache__" rmdir /s /q "odoo\__pycache__"
if exist "custom_addons\diecut_custom\__pycache__" rmdir /s /q "custom_addons\diecut_custom\__pycache__"
if exist "custom_addons\diecut_custom\models\__pycache__" rmdir /s /q "custom_addons\diecut_custom\models\__pycache__"

echo.
echo 正在启动 Odoo...
python odoo\odoo-bin -c odoo.conf

pause
