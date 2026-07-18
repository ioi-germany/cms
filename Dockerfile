# syntax=docker/dockerfile:1
# Supported combinations: ubuntu:noble, debian:bookworm.
ARG BASE_IMAGE=ubuntu:noble
FROM ${BASE_IMAGE} AS builder
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential python3-dev python3-venv python3-pip \
    libcap-dev libffi-dev libpq-dev libyaml-dev

RUN mkdir -p /home/cmsuser/src
COPY install.py constraints.txt /home/cmsuser/src/

WORKDIR /home/cmsuser/src

ENV TZ=UTC
RUN --mount=type=cache,target=/home/cmsuser/.cache/pip,uid=2000 ./install.py \
    --skip-isolate --dir /home/cmsuser/cms venv
COPY --chown=cmsuser:cmsuser . /home/cmsuser/src
RUN --mount=type=cache,target=/home/cmsuser/.cache/pip,uid=2000 ./install.py \
    --skip-isolate --dir /home/cmsuser/cms cms
RUN --mount=type=cache,target=/home/cmsuser/.cache/pip,uid=2000 <<EOF
#!/bin/bash -ex
    /home/cmsuser/cms/bin/pip install 'setuptools<82' pip-autoremove
    PACKAGES=(
        # remove dev dependencies
        beautifulsoup4
        coverage
        pytest
        pytest-cov
        # remove some additional (large) dependencies not needed for task building
        discord.py
        python-telegram-bot
        pyyaml
    )
    /home/cmsuser/cms/bin/pip-autoremove -y "${PACKAGES[@]}"
    /home/cmsuser/cms/bin/pip uninstall setuptools pip-autoremove -y
EOF

########################################
FROM ${BASE_IMAGE} AS base

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked <<EOF
#!/bin/bash -ex
    export DEBIAN_FRONTEND=noninteractive
    # Don't delete all the .deb files after install, as that would make the
    # cache useless.
    rm -f /etc/apt/apt.conf.d/docker-clean
    # Note that we use apt-get here instead of plain apt, because plain apt
    # also deletes .deb files after successful install.
    apt-get update
    PACKAGES=(
        ca-certificates
        curl
        g++
        libcairo2
        postgresql-client
        python3
        shared-mime-info
        sudo
        wait-for-it
    )
    apt-get install -y --no-install-recommends "${PACKAGES[@]}"
EOF

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked <<EOF
#!/bin/bash -ex
    export DEBIAN_FRONTEND=noninteractive
    CODENAME=$(source /etc/os-release; echo $VERSION_CODENAME)
    echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/isolate.asc]" \
        "http://www.ucw.cz/isolate/debian/ ${CODENAME}-isolate main" \
        >/etc/apt/sources.list.d/isolate.list
    curl https://www.ucw.cz/isolate/debian/signing-key.asc \
        >/etc/apt/keyrings/isolate.asc
    apt-get update
    apt-get install -y isolate
    sed -i 's@^cg_root .*@cg_root = /sys/fs/cgroup@' /etc/isolate
EOF

# Create cmsuser user with sudo privileges and access to isolate
RUN <<EOF
#!/bin/bash -ex
    # Need to set user ID manually: otherwise it'd be 1000 on debian
    # and 1001 on ubuntu.
    # 1001 is taken by `isolate`.
    useradd -ms /bin/bash -u 2000 cmsuser
    usermod -aG sudo cmsuser
    usermod -aG isolate cmsuser
    # Disable sudo password
    echo '%sudo ALL=(ALL) NOPASSWD:ALL' >> /etc/sudoers
EOF

ENV LANG=C.UTF-8

########################################
FROM base as tex
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked <<EOF
#!/bin/bash -ex
    export DEBIAN_FRONTEND=noninteractive
    apt-get update
    PACKAGES=(
        ghostscript
        latexmk
        texlive-font-utils
        texlive-latex-extra
        texlive-luatex
        texlive-science
        xz-utils
    )
    apt-get install -y --no-install-recommends "${PACKAGES[@]}"
EOF
# Set cmsuser as default user
USER cmsuser
RUN <<EOF
#!/bin/bash -ex
    tlmgr init-usertree
    TLYEAR=$(tlmgr --version | grep -oP '(?<=version )[0-9]{4}')
    tlmgr option repository https://ftp.tu-chemnitz.de/pub/tug/historic/systems/texlive/${TLYEAR}/tlnet-final
    tlmgr install fira firamath firamath-otf
    texhash
    luaotfload-tool --update
EOF

COPY --from=builder --chown=cmsuser:cmsuser /home/cmsuser/cms /home/cmsuser/cms
ENV PATH="/home/cmsuser/cms/bin:$PATH"
COPY --chown=cmsuser:cmsuser --chmod=644 config/cms.sample.toml /home/cmsuser/cms/etc/cms.toml
RUN <<EOF
#!/bin/bash -ex
    sed -i 's|/cmsuser:your_password_here@localhost:5432/cmsdb"|/postgres:postgres@db:5432/cmsdb"|' /home/cmsuser/cms/etc/cms.toml
    sed -i 's/127.0.0.1/0.0.0.0/' /home/cmsuser/cms/etc/cms.toml
EOF
COPY --chown=cmsuser:cmsuser --chmod=755 docker-entrypoint.sh /home/cmsuser/docker-entrypoint.sh

RUN mkdir /home/cmsuser/tasks
WORKDIR /home/cmsuser/tasks
ENTRYPOINT ["/home/cmsuser/docker-entrypoint.sh"]
CMD ["sleep", "infinity"]

########################################
FROM base as slim
# Set cmsuser as default user
USER cmsuser

COPY --from=builder --chown=cmsuser:cmsuser /home/cmsuser/cms /home/cmsuser/cms
ENV PATH="/home/cmsuser/cms/bin:$PATH"
COPY --chown=cmsuser:cmsuser --chmod=644 config/cms.sample.toml /home/cmsuser/cms/etc/cms.toml
RUN <<EOF
#!/bin/bash -ex
    sed -i 's|/cmsuser:your_password_here@localhost:5432/cmsdb"|/postgres:postgres@db:5432/cmsdb"|' /home/cmsuser/cms/etc/cms.toml
    sed -i 's/127.0.0.1/0.0.0.0/' /home/cmsuser/cms/etc/cms.toml
EOF
COPY --chown=cmsuser:cmsuser --chmod=755 docker-entrypoint.sh /home/cmsuser/docker-entrypoint.sh

RUN mkdir /home/cmsuser/tasks
WORKDIR /home/cmsuser/tasks
ENTRYPOINT ["/home/cmsuser/docker-entrypoint.sh"]
CMD ["sleep", "infinity"]

########################################
FROM base as dev
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked <<EOF
#!/bin/bash -ex
    export DEBIAN_FRONTEND=noninteractive
    # Don't delete all the .deb files after install, as that would make the
    # cache useless.
    rm -f /etc/apt/apt.conf.d/docker-clean
    # Note that we use apt-get here instead of plain apt, because plain apt
    # also deletes .deb files after successful install.
    apt-get update
    PACKAGES=(
        build-essential
        cppreference-doc-en-html
        default-jdk-headless
        fp-compiler
        ghc
        git
        libcap-dev
        libffi-dev
        libpq-dev
        libyaml-dev
        mono-mcs
        php-cli
        pypy3
        python3-dev
        python3-pip
        python3-venv
        rustc
        zip
    )
    apt-get install -y --no-install-recommends "${PACKAGES[@]}"
EOF

# Set cmsuser as default user
USER cmsuser
ENV LANG=C.UTF-8

RUN git config --global user.email "dev@localhost"
RUN git config --global user.name "cms-dev"

RUN mkdir /home/cmsuser/src && mkdir /home/cmsuser/tasks
COPY --chown=cmsuser:cmsuser install.py constraints.txt /home/cmsuser/src/
COPY --chown=cmsuser:cmsuser --chmod=755 docker-entrypoint.sh /home/cmsuser/docker-entrypoint.sh

WORKDIR /home/cmsuser/src

RUN --mount=type=cache,target=/home/cmsuser/.cache/pip,uid=2000 ./install.py venv
ENV PATH="/home/cmsuser/cms/bin:$PATH"

COPY --chown=cmsuser:cmsuser . /home/cmsuser/src

RUN --mount=type=cache,target=/home/cmsuser/.cache/pip,uid=2000 ./install.py cms

RUN <<EOF
#!/bin/bash -ex
    sed 's|/cmsuser:your_password_here@localhost:5432/cmsdb"|/postgres:postgres@db:5432/cmsdb"|' ./config/cms.sample.toml >../cms/etc/cms.toml
    sed 's|/cmsuser:your_password_here@localhost:5432/cmsdb"|/postgres@testdb:5432/cmsdbfortesting"|' \
        ./config/cms.sample.toml >../cms/etc/cms-testdb.toml
    sed -e 's|/cmsuser:your_password_here@localhost:5432/cmsdb"|/postgres@devdb:5432/cmsdb"|' \
        -e 's/127.0.0.1/0.0.0.0/' \
        ./config/cms.sample.toml >../cms/etc/cms-devdb.toml
    sed -i 's/127.0.0.1/0.0.0.0/' ../cms/etc/cms_ranking.toml
    sed -i 's/127.0.0.1/0.0.0.0/' ../cms/etc/cms-testdb.toml
    sed -i 's/127.0.0.1/0.0.0.0/' ../cms/etc/cms.toml
EOF

WORKDIR /home/cmsuser/tasks
ENTRYPOINT ["/home/cmsuser/docker-entrypoint.sh"]

# cws, aws, rws, taskoverview, gertranslate
EXPOSE 8888 8889 8890 8891 8892
CMD ["sleep", "infinity"]
