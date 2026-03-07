@echo off
echo ==========================================
echo       正在停止 Odoo...
echo ==========================================

cd /d "%~dp0.devcontainer"
docker compose -p my_odoo_project_devcontainer -f docker-compose.yml down

echo.
echo [完成] Odoo 服务已停止。
pause
