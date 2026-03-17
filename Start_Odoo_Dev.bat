@echo off
echo ==========================================
echo    正在启动 Odoo (DEV 热重载模式)...
echo ==========================================

:: 进入配置文件目录
cd /d "%~dp0.devcontainer"

:: 启动容器 (后台运行) - DEV 模式
docker compose -p my_odoo_project_devcontainer -f docker-compose.yml -f docker-compose.dev.yml up -d

:: Ensure worker dependencies for schema validation are available in container
docker exec my_odoo_project_devcontainer-web-1 python3 -m pip install --break-system-packages --ignore-installed "typing_extensions>=4.14.1" "pydantic>=2,<3" >nul 2>&1

echo.
echo [成功] Odoo DEV 服务已在后台启动!
echo.
echo ------------------------------------------
echo  访问地址: http://localhost:8070
echo  当前模式: DEV (--dev=all,reload, 备用模式)
echo  注意: DEV 模式优先热重载，chatter 实时推送可能不稳定
echo ------------------------------------------
echo.
echo 正在显示实时日志 (按 Ctrl+C 可退出日志查看，服务会继续运行)...
echo.

:: 显示 web 容器的日志
docker compose -p my_odoo_project_devcontainer -f docker-compose.yml -f docker-compose.dev.yml logs -f web
