@echo off
echo ==========================================
echo   正在启动 Odoo (FAST W3 模式)...
echo ==========================================

:: 进入配置文件目录
cd /d "%~dp0.devcontainer"

:: 启动容器 (后台运行) - FAST W3 覆盖模式
docker compose -p my_odoo_project_devcontainer -f docker-compose.yml -f docker-compose.fast.w3.yml up -d

:: Ensure worker dependencies for schema validation are available in container
docker exec my_odoo_project_devcontainer-web-1 python3 -m pip install --break-system-packages --ignore-installed "typing_extensions>=4.14.1" "pydantic>=2,<3" >nul 2>&1

echo.
echo [成功] Odoo 服务已在后台启动!
echo.
echo ------------------------------------------
echo  访问地址: http://localhost:8070
echo  当前模式: FAST W3 (workers=3)
echo ------------------------------------------
echo.
echo 正在显示实时日志 (按 Ctrl+C 可退出日志查看，服务会继续运行)...
echo.

:: 显示 web 容器的日志
docker compose -p my_odoo_project_devcontainer -f docker-compose.yml -f docker-compose.fast.w3.yml logs -f web
