FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src

# The HTTP service uses only the standard library. Optional Gemini/Streamlit
# dependencies stay out of this image until the agent runtime is enabled.
RUN pip install --no-cache-dir --no-deps .

RUN useradd --create-home --uid 10001 appuser
USER appuser

EXPOSE 8080
CMD ["signalsweep-server"]
