# Use a Debian-based image as the base
FROM debian:bookworm

# Install system dependencies
RUN apt update && \
    apt install -y \
        make \
        zip \
        curl \
        unzip \
        openjdk-17-jdk \
        perl \
        perl-base \
        uuid-dev \
        build-essential

# Install Jena (Apache Jena 5.2.0)
RUN mkdir -p /jena && \
    curl -L https://archive.apache.org/dist/jena/binaries/apache-jena-5.2.0.zip -o /jena/jena.zip && \
    unzip /jena/jena.zip -d /jena && \
    rm /jena/jena.zip && \
    ln -s /jena/apache-jena-5.2.0/bin/riot /usr/local/bin/riot.bat && \
    ln -s /jena/apache-jena-5.2.0/bin/update /usr/local/bin/update.bat

# Install cpanminus (CPAN module manager)
RUN curl -L https://cpanmin.us | perl - App::cpanminus

# Install Perl modules
RUN cpanm -n warnings autodie UUID Getopt::Std

# Set environment variables
ENV PATH="/usr/local/bin:$PATH"

# Add data refreshement sctipt
COPY refresh-data.sh /refresh-data.sh
RUN chmod +x /refresh-data.sh
COPY drop.ru /drop.ru
