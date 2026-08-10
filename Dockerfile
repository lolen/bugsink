# This is the Dockerfile that builds an image form the current directory.
# It is provided as-is; the Bugsink team does not use this in their own
# development. Tips:

# * Configure your database/filestore/etc _outside_ of the current path
#     to avoid copying them into the image.

ARG PYTHON_VERSION=3.12

# Build image: non-slim, in particular to build the mysqlclient wheel
FROM python:${PYTHON_VERSION} AS build

# mysqlclient is not available as a .whl on PyPI, so we need to build it from
# source and store the .whl. This is both the most expensive part of the build
# and the one that is least likely to change, so we do it first.
RUN --mount=type=cache,target=/root/.cache/pip \
    pip wheel --wheel-dir /wheels mysqlclient

# Actual image (based on slim)
FROM python:${PYTHON_VERSION}-slim AS app

ENV PYTHONUNBUFFERED=1

ENV PORT=8000

WORKDIR /app

# Runtime shared library the mysqlclient wheel links against.
RUN apt update && apt install libmariadb3 -y \
 && rm -rf /var/lib/apt/lists/*

# Install all deps and strip native extensions in a single layer, so only the
# stripped binaries are stored (must be same layer to actually shrink the image).
# binutils is installed and purged here; requirements/wheels are bind-mounted,
# not COPYed, so they don't end up in a layer.
RUN --mount=type=cache,target=/root/.cache/pip \
    --mount=type=bind,from=build,source=/wheels,target=/wheels \
    --mount=type=bind,source=requirements.txt,target=/tmp/requirements.txt \
    apt-get update \
 && apt-get install -y --no-install-recommends binutils \
 && pip install --find-links /wheels --no-index mysqlclient \
 && pip install "psycopg[binary]" \
 && pip install -r /tmp/requirements.txt \
 && find /usr/local/lib/python3.12/site-packages -name '*.so' -exec strip --strip-unneeded {} + \
 && apt-get purge -y binutils && apt-get autoremove -y \
 && rm -rf /var/lib/apt/lists/*

COPY . /app/
COPY bugsink/conf_templates/docker.py.template bugsink_conf.py

# git is only needed by setuptools_scm during the editable install; install and
# purge it in the same layer so it stays out of the final image.
RUN --mount=type=cache,target=/root/.cache/pip \
    apt-get update \
 && apt-get install -y --no-install-recommends git \
 && pip install -e . \
 && apt-get purge -y git && apt-get autoremove -y \
 && rm -rf /var/lib/apt/lists/*

RUN groupadd --gid 14237 bugsink \
 && useradd --uid 14237 --gid 14237 bugsink \
 && mkdir -p /data \
 && chown -R bugsink:bugsink /data

USER bugsink

HEALTHCHECK CMD python -c 'import requests; requests.get("http://localhost:8000/health/ready").raise_for_status()'

CMD [ "monofy", "bugsink-show-version", "&&", "bugsink-manage", "check", "--deploy", "--fail-level", "WARNING", "&&", "bugsink-manage", "migrate", "snappea", "--database=snappea", "&&", "bugsink-manage", "migrate", "&&", "bugsink-manage", "prestart", "&&", "gunicorn", "--config", "bugsink/gunicorn.docker.conf.py", "--bind=0.0.0.0:$PORT", "--access-logfile", "-", "bugsink.wsgi", "|||", "bugsink-runsnappea"]

# CI-only stage: adds lint/test tooling on top of the app image. Not used in production.
FROM app AS test

USER root

RUN --mount=type=cache,target=/root/.cache/pip \
    --mount=type=bind,source=requirements.development.txt,target=/tmp/requirements.development.txt \
    pip install -r /tmp/requirements.development.txt

# baked in at build time (not runtime-mounted), so this works the same regardless of
# how/where the CI runner's docker daemon sees the build context's filesystem.
COPY event-samples /event-samples

# stays root: tests write db.sqlite3 into /app, which is root-owned (COPY doesn't chown it);
# this stage is CI-only and never runs in production, so that's an acceptable tradeoff.
CMD ["python", "manage.py", "test"]
