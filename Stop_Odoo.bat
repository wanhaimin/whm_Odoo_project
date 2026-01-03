@echo off
echo ==========================================
echo       正在停止 Odoo...
echo ==========================================

cd .devcontainer
docker-compose down

echo.
echo [完成] Odoo 服务已停止。
pause
