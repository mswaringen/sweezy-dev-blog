Title: Deploying Cookiecutter Django on Fly.io
Date: 2024-5-22 14:00
Category: devops

#### _with Celery, Postgres, Redis, and S3 storage with Tigris_

[Cookiecutter Django](https://github.com/cookiecutter/cookiecutter-django) is awesome but it can be difficult to deploy the entire stack apart from the officially supported options. With a few small tweaks we can deploy on Fly.io with everything included. Hopefully this can save others some time with configuration.



## Steps

1) Create/update three config files: `fly.toml`, `release.sh`, `Dockerfile`

2) Modify settings to accept Fly-provided secrets

3) `fly launch` & import secrets

4) (Optional) Deploy via GH Actions


Lets go!


## 1) Create fly.toml, release script, Dockerfile

_[Full description](https://fly.io/docs/apps/launch/) of the Fly launch and deploy process_

Before running `fly launch` create your own `fly.toml`, `release.sh`, and `Dockerfile`. All three should be in the project root directory.

### Custom fly.toml

As the primary config file, fly.toml here is modifed here to match varible names in the Dockerfile, add a Celery worker process, and run a custom release script.

The following variables require user input: `app, primary_region`
> Note the number of workers can be set under `processes/app` (default is 1)

_fly.toml_
```
app = 'fly-cookiecutter-django-2'
primary_region = 'mad'
console_command = '/code/manage.py shell'

[build]

[deploy]
  release_command = 'sh /code/release.sh'

[env]
  PORT = '8000'

[processes]
  app = 'python -m gunicorn --bind :8000 --workers 1 config.wsgi'
  worker = 'python -m celery -A config.celery_app:app worker -l DEBUG'

[http_service]
  internal_port = 8000
  force_https = true
  auto_stop_machines = true
  auto_start_machines = true
  min_machines_running = 0
  processes = ['app']

[[vm]]
  memory = '1gb'
  cpu_kind = 'shared'
  cpus = 1

[[statics]]
  guest_path = '/code/static'
  url_prefix = '/static/'

```

### Release script
We need to run both `collectstatic` and `migrate` as release commands, thus we need a script. 
> The release_command is done in a pre-deploy VM that has access to production environment variables

_release.sh_
```
#!/usr/bin/env sh

python manage.py collectstatic --noinput 
python manage.py migrate

# exit 123
```
### Custom Dockerfile

This is a version of the Dockerfile found in `compose/production/django/Dockerfile`, the main change is to remove the entrypoint scripts.

_Dockerfile_
```
# define an alias for the specific python version used in this file.
FROM docker.io/python:3.12.3-slim-bookworm as python

# Python build stage
FROM python as python-build-stage

ARG BUILD_ENVIRONMENT=production

# Install apt packages
RUN apt-get update && apt-get install --no-install-recommends -y \
  # dependencies for building Python packages
  build-essential \
  # psycopg dependencies
  libpq-dev

# Requirements are installed here to ensure they will be cached.
COPY ./requirements .

# Create Python Dependency and Sub-Dependency Wheels.
RUN pip wheel --wheel-dir /usr/src/app/wheels  \
  -r ${BUILD_ENVIRONMENT}.txt


# Python 'run' stage
FROM python as python-run-stage

ARG BUILD_ENVIRONMENT=production
ARG APP_HOME=/code

ENV PYTHONUNBUFFERED 1
ENV PYTHONDONTWRITEBYTECODE 1
ENV BUILD_ENV ${BUILD_ENVIRONMENT}

WORKDIR ${APP_HOME}

RUN addgroup --system django \
    && adduser --system --ingroup django django


# Install required system dependencies
RUN apt-get update && apt-get install --no-install-recommends -y \
  # psycopg dependencies
  libpq-dev \
  # Translations dependencies
  gettext \
  # cleaning up unused files
  && apt-get purge -y --auto-remove -o APT::AutoRemove::RecommendsImportant=false \
  && rm -rf /var/lib/apt/lists/*

# All absolute dir copies ignore workdir instruction. All relative dir copies are wrt to the workdir instruction
# copy python dependency wheels from python-build-stage
COPY --from=python-build-stage /usr/src/app/wheels  /wheels/

# use wheels to install python dependencies
RUN pip install --no-cache-dir --no-index --find-links=/wheels/ /wheels/* \
  && rm -rf /wheels/

COPY . /code

EXPOSE 8000

CMD ["gunicorn", "--bind", ":8000", "--workers", "1", "config.wsgi"]
```

## 2) Modify settings to accept Fly-assigned environment variables

Fly will automatically assign several environment variables as you add services
```
DATABASE_URL - Postgres
REDIS_URL - Redis

AWS_REGION - Tigris
AWS_ENDPOINT_URL_S3 - Tigris
AWS_ACCESS_KEY_ID - Tigris
AWS_SECRET_ACCESS_KEY - Tigris
```

Modify both `settings/production.py` and `.envs/.production/.django` to accomodate these variables

_relevant section of production.py_
```
# STORAGES
# ------------------------------------------------------------------------------
# https://django-storages.readthedocs.io/en/latest/#installation
INSTALLED_APPS += ["storages"]
# https://django-storages.readthedocs.io/en/latest/backends/amazon-S3.html#settings
AWS_ACCESS_KEY_ID = env("DJANGO_AWS_ACCESS_KEY_ID", default=None) or env("AWS_ACCESS_KEY_ID", default=None)
# https://django-storages.readthedocs.io/en/latest/backends/amazon-S3.html#settings
AWS_SECRET_ACCESS_KEY = env("DJANGO_AWS_SECRET_ACCESS_KEY", default=None) or env("AWS_SECRET_ACCESS_KEY", default=None)
# https://django-storages.readthedocs.io/en/latest/backends/amazon-S3.html#settings
AWS_STORAGE_BUCKET_NAME = env("DJANGO_AWS_STORAGE_BUCKET_NAME", default=None) or env("BUCKET_NAME", default=None)
# https://django-storages.readthedocs.io/en/latest/backends/amazon-S3.html#settings
AWS_QUERYSTRING_AUTH = False
# DO NOT change these unless you know what you're doing.
_AWS_EXPIRY = 60 * 60 * 24 * 7
# https://django-storages.readthedocs.io/en/latest/backends/amazon-S3.html#settings
AWS_S3_OBJECT_PARAMETERS = {
    "CacheControl": f"max-age={_AWS_EXPIRY}, s-maxage={_AWS_EXPIRY}, must-revalidate",
}
# https://django-storages.readthedocs.io/en/latest/backends/amazon-S3.html#settings
AWS_S3_MAX_MEMORY_SIZE = env.int(
    "DJANGO_AWS_S3_MAX_MEMORY_SIZE",
    default=100_000_000,  # 100MB
)
# https://django-storages.readthedocs.io/en/latest/backends/amazon-S3.html#settings
AWS_S3_REGION_NAME = env("DJANGO_AWS_S3_REGION_NAME", default=None) or env("AWS_REGION", default=None)
# https://django-storages.readthedocs.io/en/latest/backends/amazon-S3.html#cloudfront
AWS_S3_ENDPOINT_URL = env("AWS_ENDPOINT_URL_S3", default=None)
AWS_S3_CUSTOM_DOMAIN = env("DJANGO_AWS_S3_CUSTOM_DOMAIN", default=None)

# Parse the endpoint URL to get the domain without protocol
if AWS_S3_ENDPOINT_URL:
    parsed_url = urlparse(AWS_S3_ENDPOINT_URL)
    endpoint_domain = parsed_url.netloc
else:
    endpoint_domain = None

aws_s3_domain = AWS_S3_CUSTOM_DOMAIN or endpoint_domain or f"{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com"
```

_relevant section of .envs/.production/.django_
```
# comment out these vars

# AWS
# ------------------------------------------------------------------------------
# DJANGO_AWS_ACCESS_KEY_ID=
# DJANGO_AWS_SECRET_ACCESS_KEY=
# DJANGO_AWS_STORAGE_BUCKET_NAME=

# Redis
# ------------------------------------------------------------------------------
# REDIS_URL=
```

## 3) Launch and Import Secrets

### Launch wizard
Run `fly launch` from the root directory

```
- YES to copy config to new app
- NO to overwriting Dockerfile
- YES to modifying configuration, click to open setting page, select Postgres, Redis, Tigris
```

### Import secrets
Run the following command to import the secrets to Fly:

   ```
   cat .envs/.production/.django | fly secrets import
   ```

### First Deploy

Run `fly deploy`

If deployment was successful, create a superuser via `fly ssh console`

## 4) (Optional) Deploy with Github Actions
_Fly docs on [Deploy with Github Actions](https://fly.io/docs/app-guides/continuous-deployment-with-github-actions/)_

1) From the project source directory, get a Fly API deploy token by running 

```
fly tokens create deploy -x 999999h
```

Copy the output, including the FlyV1 and space at the beginning.

2) Go to your repository on GitHub and select Settings. Under Secrets and variables, select Actions, and then create a new repository secret called FLY_API_TOKEN, paste the value previously created in step 1.

3) Back in your project source directory, create `.github/workflows/fly.yml` with these contents:
```
name: Fly Deploy
on:
  push:
    branches:
      - master    # change to main if needed
jobs:
  deploy:
    name: Deploy app
    runs-on: ubuntu-latest
    concurrency: deploy-group    # optional: ensure only one action runs at a time
    steps:
      - uses: actions/checkout@v4
      - uses: superfly/flyctl-actions/setup-flyctl@master
      - run: flyctl deploy --remote-only
        env:
          FLY_API_TOKEN: ${{ secrets.FLY_API_TOKEN }}

```

4) Push changes to start automatic deployment

## Example Code
Stuck on something? Check out the [Example code on Github](https://github.com/mswaringen/fly-cookiecutter-django)