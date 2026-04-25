FROM odoo:19.0

USER root

ARG NODE_VERSION=22.16.0

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    git \
    curl \
    wget \
    procps \
    python3-dev \
    build-essential \
    xz-utils \
    && rm -rf /var/lib/apt/lists/*

RUN pip3 install --no-cache-dir --break-system-packages pypdfium2

RUN curl -fsSL "https://nodejs.org/dist/v${NODE_VERSION}/node-v${NODE_VERSION}-linux-x64.tar.xz" -o /tmp/node.tar.xz && \
    tar -xJf /tmp/node.tar.xz -C /opt && \
    ln -sf "/opt/node-v${NODE_VERSION}-linux-x64/bin/node" /usr/local/bin/node && \
    ln -sf "/opt/node-v${NODE_VERSION}-linux-x64/bin/npm" /usr/local/bin/npm && \
    ln -sf "/opt/node-v${NODE_VERSION}-linux-x64/bin/npx" /usr/local/bin/npx && \
    npm install -g openclaw --prefix /opt/openclaw-cli && \
    ln -sf /opt/openclaw-cli/bin/openclaw /usr/local/bin/openclaw && \
    rm -f /tmp/node.tar.xz

RUN mkdir -p /var/lib/odoo/.vscode-server /var/lib/odoo/.vscode-server-insiders && \
    chown -R odoo:odoo /var/lib/odoo

COPY start_odoo_with_worker.sh /usr/local/bin/start_odoo_with_worker.sh
RUN chmod +x /usr/local/bin/start_odoo_with_worker.sh
