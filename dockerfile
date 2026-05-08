FROM python:3.11

RUN apt update && apt install -y ffmpeg

WORKDIR /app

COPY . .

RUN pip install -r champu-bot/requirements.txt

CMD ["python", "champu-bot/vc_bot.py"]