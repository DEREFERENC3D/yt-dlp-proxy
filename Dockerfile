FROM python:3.12-alpine

RUN apk --no-cache add ffmpeg

WORKDIR /app

COPY requirements.txt ./

RUN pip install -r requirements.txt

COPY . .

EXPOSE 8000

ENTRYPOINT ["fastapi", "run", "main.py"]
