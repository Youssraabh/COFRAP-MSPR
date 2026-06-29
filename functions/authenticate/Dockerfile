FROM python:3.12-alpine

RUN apk add --no-cache gcc musl-dev libffi-dev


COPY --from=ghcr.io/openfaas/of-watchdog:0.11.6 /fwatchdog /usr/bin/fwatchdog

RUN chmod +x /usr/bin/fwatchdog


ENV fprocess="python index.py"
ENV mode="http"
ENV http_upstream_url="http://127.0.0.1:5000"


WORKDIR /home/app

COPY index.py .

COPY function/ function/

RUN pip install --no-cache-dir -r function/requirements.txt

EXPOSE 8080

CMD ["fwatchdog"]