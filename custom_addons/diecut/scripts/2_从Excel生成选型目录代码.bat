@echo off
chcp 65001 >nul
echo =======================================================
echo          从 Excel (CSV) 生成全量 Odoo XML 与 JSON 架构
echo =======================================================
echo.
echo 注意：正在处理当前目录下的 series.csv 与 variants.csv ...
echo.

docker exec my_odoo_project_devcontainer-web-1 python3 /mnt/extra-addons/diecut/scripts/generate_catalog.py

echo.
echo =======================================================
echo 代码生成完毕！现在你可以去 Odoo 界面点击【升级模块】了！
echo =======================================================
pause
