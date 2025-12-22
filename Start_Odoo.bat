@echo off
echo 正在启动 Odoo 服务...
echo 项目路径: c:\Users\Lenovo\OneDrive\Desktop\workspace\my_odoo_project

:: 切换到项目目录
cd /d "c:\Users\Lenovo\OneDrive\Desktop\workspace\my_odoo_project"

:: 使用虚拟环境的 Python 启动 Odoo
".\venv\Scripts\python.exe" odoo/odoo-bin -c odoo.conf

:: 如果程序意外退出，暂停显示错误信息
pause
