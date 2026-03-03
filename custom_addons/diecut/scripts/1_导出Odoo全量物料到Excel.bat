@echo off
chcp 65001 >nul
echo =======================================================
echo              从 Odoo 导出系列和型号到 Excel (CSV)
echo =======================================================
echo.
echo 正在连接到 Docker 容器提取数据...
echo.

docker exec my_odoo_project_devcontainer-web-1 python3 /mnt/extra-addons/diecut/scripts/export_from_db.py

echo.
echo =======================================================
echo 提取完成！请在当前目录下查看 series.csv 和 variants.csv
echo =======================================================
pause
