FROM python:3.12-slim
WORKDIR /app
COPY app ./app
ENV TRAINER_CHECKPOINT=/data/reward-model.json
CMD ["python", "app/main.py", "serve", "--host", "0.0.0.0"]
