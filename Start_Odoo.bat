@echo off
echo ==========================================
echo       正在启动 Odoo (Docker模式)...
echo ==========================================

:: 进入配置文件目录
cd .devcontainer

:: 启动容器 (后台运行)
docker-compose up -d

echo.
echo [成功] Odoo 服务已在后台启动!
echo.
echo ------------------------------------------
echo  访问地址: http://localhost:8070
echo ------------------------------------------
echo.
echo 正在显示实时日志 (按 Ctrl+C 可退出日志查看，服务会继续运行)...
echo.

:: 显示 web 容器的日志
docker-compose logs -f web
