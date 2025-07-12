FROM python:3.10-slim

# 시스템 패키지 업데이트 및 필수 패키지 설치
RUN apt-get update && \
    apt-get install -y \
    wget \
    unzip \
    curl \
    gnupg2 \
    chromium \
    chromium-driver \
    && rm -rf /var/lib/apt/lists/*

# 환경변수 설정
ENV CHROME_BIN=/usr/bin/chromium
ENV CHROMEDRIVER_PATH=/usr/bin/chromedriver
ENV PYTHONPATH=/app

# 작업 디렉토리 설정
WORKDIR /app

# Python 의존성 파일 복사 및 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 애플리케이션 파일 복사
COPY . .

# 포트 노출
EXPOSE 8080

# Streamlit 앱 실행 명령어
CMD ["streamlit", "run", "smio_app.py", "--server.port=8080", "--server.address=0.0.0.0"] 