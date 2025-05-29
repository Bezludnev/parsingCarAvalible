FROM python:3.11-slim

# Install Chrome and ChromeDriver
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    unzip \
    curl \
    jq \
    && wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

# Install ChromeDriver (новый метод для Chrome 115+)
RUN CHROME_VERSION=$(google-chrome --version | cut -d ' ' -f3 | cut -d '.' -f1-3) \
    && echo "Chrome version: $CHROME_VERSION" \
    && if [ $(echo $CHROME_VERSION | cut -d '.' -f1) -ge 115 ]; then \
        DRIVER_VERSION=$(curl -s "https://googlechromelabs.github.io/chrome-for-testing/LATEST_RELEASE_$CHROME_VERSION" || echo "stable"); \
        if [ "$DRIVER_VERSION" = "stable" ]; then \
            DRIVER_VERSION=$(curl -s "https://googlechromelabs.github.io/chrome-for-testing/LATEST_RELEASE_STABLE"); \
        fi; \
        echo "Driver version: $DRIVER_VERSION"; \
        wget -O /tmp/chromedriver.zip "https://storage.googleapis.com/chrome-for-testing-public/$DRIVER_VERSION/linux64/chromedriver-linux64.zip"; \
    else \
        wget -O /tmp/chromedriver.zip "https://chromedriver.storage.googleapis.com/LATEST_RELEASE_$CHROME_VERSION/chromedriver_linux64.zip"; \
    fi \
    && unzip /tmp/chromedriver.zip -d /tmp/ \
    && if [ -d "/tmp/chromedriver-linux64" ]; then \
        mv /tmp/chromedriver-linux64/chromedriver /usr/local/bin/; \
    else \
        mv /tmp/chromedriver /usr/local/bin/; \
    fi \
    && chmod +x /usr/local/bin/chromedriver \
    && rm -rf /tmp/chromedriver*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]