# Use the official Python slim image as a base image.
# This image is based on Debian 11 (Bullseye).
FROM python:3.10.15-slim

# Set environment variables.
ENV PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    TZ=Asia/Riyadh

# Set timezone to Riyadh.
# This creates a symbolic link for the timezone and updates /etc/timezone.
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Add Debian Bullseye security repository to sources.list.
# This ensures that apt can find security updates and packages like libssl1.1.
RUN echo "deb http://security.debian.org/debian-security bullseye-security main contrib non-free" >> /etc/apt/sources.list

# Install system dependencies, PostgreSQL client, and wkhtmltopdf-compatible libraries.
# libssl1.1 is available in Debian 11 (Bullseye) repositories and will be installed.
# xfonts-base and xfonts-75dpi are crucial for wkhtmltopdf to render correctly.
RUN apt-get update && apt-get install -y \
    postgresql-client \
    libpq-dev \
    build-essential \
    libldap2-dev \
    libsasl2-dev \
    curl \
    gnupg2 \
    libx11-6 \
    libxext6 \
    libxrender1 \
    libfreetype6 \
    libjpeg62-turbo \
    libpng-dev \
    fontconfig \
    xfonts-base \
    xfonts-75dpi \
    wget \
    git \
    xvfb \
    fonts-noto \
    fonts-noto-cjk \
    fonts-noto-extra \
    nodejs \
    npm \
    # Ensure libssl1.1 is explicitly installed for wkhtmltox dependency
    libssl1.1 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install wkhtmltopdf using the bullseye version, which is compatible with the base image.
# We download the .deb package and then use apt-get install -y ./<package>.deb
# This method handles dependencies automatically.
RUN wget https://github.com/wkhtmltopdf/packaging/releases/download/0.12.6.1-2/wkhtmltox_0.12.6.1-2.bullseye_amd64.deb \
    && apt-get update \
    && apt-get install -y ./wkhtmltox_0.12.6.1-2.bullseye_amd64.deb \
    && rm wkhtmltox_0.12.6.1-2.bullseye_amd64.deb \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /opt/odoo-tazamun
WORKDIR /opt/odoo-tazamun

# Create and set permissions for Odoo user and configuration
RUN useradd -m -d /opt/odoo -U -r -s /bin/bash odoo \
    && chown -R odoo:odoo /opt/odoo-tazamun/

#RUN git clone https://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@github.com/hajikhan/tazamun_internal.git .

# Install Python dependencies
RUN pip install --upgrade pip setuptools wheel Cython==3.0.0a10

COPY requirements.txt /opt/odoo-tazamun/requirements.txt

RUN pip install gevent
RUN pip install hijri_converter
RUN pip install -r /opt/odoo-tazamun/requirements.txt

# Create a session directory with correct permissions
RUN mkdir -p /var/lib/odoo/.local && chown -R odoo:odoo /var/lib/odoo

USER root

# Copy Odoo source files and custom modules
COPY . /opt/odoo-tazamun/

# Odoo configuration
COPY odoo.conf /opt/odoo-tazamun/odoo.conf

# Expose Odoo and PostgreSQL ports.
EXPOSE 8059 8072
EXPOSE 5432

# Run Odoo
# CMD ["python", "/opt/odoo-tazamun/odoo-bin", "-c", "/opt/odoo-tazamun/odoo.conf", "-i", "base"]
