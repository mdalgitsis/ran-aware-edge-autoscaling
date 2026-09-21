FROM python:3.12-slim

RUN useradd --uid 1000 --create-home --shell /usr/sbin/nologin app
WORKDIR /app

COPY requirements.txt /app/
# The telemetry source needs neither the Kubernetes client nor matplotlib.
RUN pip install --no-cache-dir "prometheus_client>=0.19,<1.0"

COPY ue_simulator/ /app/ue_simulator/

USER 1000
EXPOSE 8000

CMD ["python", "-u", "-m", "ue_simulator.simulator"]
