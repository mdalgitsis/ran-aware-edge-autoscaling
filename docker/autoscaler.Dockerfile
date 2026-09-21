FROM python:3.12-slim

RUN useradd --uid 1000 --create-home --shell /usr/sbin/nologin app
WORKDIR /app

COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY autoscaler/ /app/autoscaler/
COPY ue_simulator/ /app/ue_simulator/

USER 1000
EXPOSE 9110

CMD ["python", "-u", "-m", "autoscaler.controller"]
