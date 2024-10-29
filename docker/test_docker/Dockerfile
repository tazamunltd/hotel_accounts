# Use the official Python slim image as a base image
FROM python:3.10.15-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

# Install system dependencies, PostgreSQL, and wkhtmltopdf-compatible libraries
RUN apt-get update && apt-get install -y \
    git \
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

# Create and set permissions for Odoo user and configuration
RUN useradd -m -d /opt/odoo -U -r -s /bin/bash odoo \
    && chown -R odoo:odoo /opt/odoo-tazamun/

RUN git clone https://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@github.com/hajikhan/tazamun_internal.git .

# Install Python dependencies
# COPY requirements.txt /opt/odoo-tazamun/
RUN pip install --upgrade pip setuptools wheel \
    && pip install -r /opt/odoo-tazamun/requirements.txt

# Create a directory for Odoo


# Switch to root user to create and set permissions for Odoo user and configuration


# Create a session directory with correct permissions
RUN mkdir -p /var/lib/odoo/.local && chown -R odoo:odoo /var/lib/odoo

USER odoo

# Copy Odoo source files and custom modules
# COPY . /opt/odoo-tazamun/

# Odoo configuration
COPY odoo.conf /opt/odoo-tazamun/odoo.conf

# Expose Odoo port
EXPOSE 8069

# Expose PostgreSQL port
EXPOSE 5432


# Run Odoo
CMD ["python", "/opt/odoo-tazamun/odoo-bin", "-c", "/opt/odoo-tazamun/odoo.conf", "-i", "base"]

#COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf
# Find and use the correct path for supervisord

# Copy entrypoint script and make it executable
#COPY entrypoint.sh /entrypoint.sh

#RUN apt-get update && apt-get install -y dos2unix && dos2unix /entrypoint.sh

#RUN chmod +x /entrypoint.sh

# Switch to the odoo user
#USER root

# Install supervisor separately to ensure it is available
#RUN apt-get update && apt-get install -y supervisor


# Run both PostgreSQL and Odoo
#CMD service postgresql start && python /opt/odoo-tazamun/odoo-bin -c /etc/odoo.conf
# Configure supervisor to manage both PostgreSQL and Odoo


# Set entrypoint
#ENTRYPOINT ["/entrypoint.sh"]

# Start supervisor
#CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]


