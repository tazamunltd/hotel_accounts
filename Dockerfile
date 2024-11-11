# Use the official Python slim image as a base image
FROM python:3.10.15-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

# Install system dependencies, PostgreSQL, and wkhtmltopdf-compatible libraries
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
    xvfb \
    vim \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

RUN wget http://security.debian.org/debian-security/pool/updates/main/o/openssl/libssl1.1_1.1.1n-0+deb10u6_amd64.deb \
    && apt-get update && apt-get install -y ./libssl1.1_1.1.1n-0+deb10u6_amd64.deb \
    && rm libssl1.1_1.1.1n-0+deb10u6_amd64.deb \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install wkhtmltopdf using the buster version, which is more compatible with the base image
RUN wget https://github.com/wkhtmltopdf/packaging/releases/download/0.12.6-1/wkhtmltox_0.12.6-1.buster_amd64.deb \
    && apt-get update && apt-get install -y ./wkhtmltox_0.12.6-1.buster_amd64.deb \
    && rm wkhtmltox_0.12.6-1.buster_amd64.deb

RUN mkdir -p /opt/odoo-tazamun
WORKDIR /opt/odoo-tazamun

# Install Python dependencies
COPY requirements.txt /opt/odoo-tazamun/
RUN pip install --upgrade pip setuptools wheel \
    && pip install -r /opt/odoo-tazamun/requirements.txt
RUN pip install bcrypt    


# Create and set permissions for Odoo user and configuration
RUN useradd -m -d /opt/odoo -U -r -s /bin/bash odoo \
    && chown -R odoo:odoo /opt/odoo-tazamun/

# Create a session directory with correct permissions
RUN mkdir -p /var/lib/odoo/.local && chown -R odoo:odoo /var/lib/odoo

USER root

# Copy Odoo source files and custom modules
COPY . /opt/odoo-tazamun/

# Odoo configuration
COPY odoo.conf /etc/odoo.conf

# Expose Odoo port
EXPOSE 8069 8071

# Expose PostgreSQL port
EXPOSE 5432


# Run Odoo
CMD ["python", "/opt/odoo-tazamun/odoo-bin", "-c", "/opt/odoo-tazamun/odoo.conf", "-i", "base"]