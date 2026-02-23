FROM odoo:19.0

USER root

# 安装开发常用工具和 VS Code server 依赖
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    git \
    curl \
    wget \
    procps \
    python3-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Fix permissions for VS Code Server
RUN mkdir -p /var/lib/odoo/.vscode-server /var/lib/odoo/.vscode-server-insiders \
    && chown -R odoo:odoo /var/lib/odoo

# Switch back to odoo user
# DEV MODE: Run as root to fix permission issues with VS Code Server
# USER odoo
