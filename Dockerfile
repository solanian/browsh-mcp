FROM browsh/browsh:latest

USER root

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        python3 python3-pip python3-venv \
        curl xvfb procps \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /app/venv
ENV PATH="/app/venv/bin:$PATH"

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY mcp_server.py /app/mcp_server.py
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

RUN mkdir -p /home/user/firefox-profile && chown -R user:user /home/user

EXPOSE 4333

USER user
ENTRYPOINT ["/app/entrypoint.sh"]
