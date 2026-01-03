@echo off
TITLE Odoo Shell (Interactive Mode)
cd e:\workspace\my_odoo_project

echo ========================================================
echo Starting Odoo Shell...
echo You can use 'env' to access the database.
echo Example: env['res.partner'].search_count([])
echo Press Ctrl+Z and Enter to exit.
echo ========================================================

REM Activate virtual environment
call .venv\Scripts\activate

REM Add wkhtmltopdf to path (same as your server start script)
set PATH=%PATH%;E:\Program Files\wkhtmltopdf\bin

REM Start Odoo in Shell mode
REM -d: database name
REM --shell-interface: use ipython if available, else standard python
python odoo\odoo-bin shell -c odoo.conf -d odoo_dev_new --shell-interface=python
pause


