@echo off
echo ==========================================
echo   正在启动 Odoo (FAST 模式)...
echo ==========================================

:: 进入配置文件目录
cd /d "%~dp0.devcontainer"

:: 启动容器 (后台运行) - FAST 模式
docker compose -p my_odoo_project_devcontainer -f docker-compose.fast.yml up -d

echo.
echo [成功] Odoo 服务已在后台启动!
echo.
echo ------------------------------------------
echo  访问地址: http://localhost:8070
echo  当前模式: FAST (无 --dev, 日常使用更快)
echo  如需开发热重载，请运行 Start_Odoo_Dev.bat
echo ------------------------------------------
echo.
echo 正在显示实时日志 (按 Ctrl+C 可退出日志查看，服务会继续运行)...
echo.

:: 显示 web 容器的日志
docker compose -p my_odoo_project_devcontainer -f docker-compose.fast.yml logs -f web
