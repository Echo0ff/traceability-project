FROM tiangolo/uvicorn-gunicorn-fastapi:python3.10

WORKDIR /app/

# Copy the requirements file into the container
COPY ./requirements.txt /app/

# Install dependencies using pip and Tsinghua mirror
RUN pip install --upgrade pip \
    && pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple \
    && pip install -r requirements.txt

ENV PYTHONPATH=/app

COPY ./scripts/ /app/

COPY ./alembic.ini /app/

COPY ./prestart.sh /app/

COPY ./tests-start.sh /app/

COPY ./app /app/app

# COPY ./uploads /app/uploads