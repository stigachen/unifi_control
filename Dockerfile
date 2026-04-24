FROM python:3.12-alpine

WORKDIR /app

COPY pyproject.toml README.md ./
COPY unifi_control_cli ./unifi_control_cli

RUN pip install --no-cache-dir .

ENV HOST=0.0.0.0 \
    PORT=8787

EXPOSE 8787
USER nobody

CMD ["unifi-control-server"]
