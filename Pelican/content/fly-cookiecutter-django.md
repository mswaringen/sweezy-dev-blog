Title: Deploying Cookiecutter Django on Fly.io
Date: 2024-5-21 16:00
Category: devops

# Deploying Cookiecutter Django on Fly.io
### _with Celery, Postgres, Redis, and S3 storage with Tigris_



## tl;dr
Cookiecutter Django is awesome but can be difficult to deploy the entire stack apart from the officially supported options. With a few small tweaks we can deploy on Fly.io with everything included (Celery workers, PG, Redis, S3 storage)

> Note: We will be using the celery_django_results package to save job status to Postgres and view results in Django Admin. This is used as a replacement for Flower in production.

## Steps

1) Generate project locally for Docker

2) Add new Dockerfile + fly.toml

3) Inject secrets from CLI

4) Fly launch + fly deploy


Now lets dive in...

## 1) Generate project locally with Docker

Prereqs: Docker, Cookiecutter

Follow the [instructions](https://cookiecutter-django.readthedocs.io/en/latest/developing-locally-docker.html) to setup a local project with Docker. 

### _Optional_ 

#### _A) Create test-task view_

This view will trigger a worker action upon GET request, letting us easily observe the entire system in action.

1) Add the following function to `config/celery_app.py` 

```
   @app.task(bind=True, ignore_result=False)
   def example_task(self):
      print("You've triggered the example task!")
```

2) Create `test_views.py` in the `config` directory and add the following code

```
   from django.http import HttpResponse
   from .celery_app import example_task

   def test_task(request):
      example_task.delay()
      return HttpResponse("Task triggered, see Celery logs")
```

3) Now modify `url_patterns ` in `config/urls.py` with the line

```
   path("test-task/", test_views.test_task, name="test_task"),
```

   After importing the view with

```
   from config import test_views
```

#### _B) Install [celery-django-results](https://github.com/celery/django-celery-results)_
This allows us to view the results of Celery worker tasks in the database with Django Admin

1) Add `django-celery-results==2.5.1` to `requirements/base.txt`

2) Add `"django_celery_results",` to `INSTALLED_APPS` in `config/settings/base.py`

3) Further modify `base.py` with the following additions

```
   CELERY_RESULT_BACKEND = env.str("CELERY_RESULT_BACKEND", "django-db”), 
   CELERY_TASK_TRACK_STARTED = True
```

   Modify the following line to allow CELERY_BROKER_URL to access REDIS_URL directly (this will be set by Fly automatically)

```
   CELERY_BROKER_URL = env('CELERY_BROKER_URL', default=env('REDIS_URL'))
```


4) Build and migrate

```
   docker compose -f local.yml build
   docker compose -f local.yml build
   docker compose -f local.yml run --rm django python manage.py migrate
```

#### _C) Test locally with Flower and Django Admin_

Run the stack and create superuser

```
   export COMPOSE_FILE=local.yml
   docker compose up
   docker compose run --rm django python manage.py createsuperuser
```

In a browser open up three tabs:

   1) Flower (Celery worker monitor): [http://localhost:5555/](http://localhost:5555/)
   > _Note: the login credentials are set in .envs/.local/.django_

   2) Django Admin: [http://localhost:8000/admin](http://localhost:8000/admin)

   3) Web test-task: [http://localhost:8000/test-task](http://localhost:8000/test-task)

> The test-task GET request kicks off a worker task. Check the activity in the Flower tab, and then check again in Django Admin under `Celery Results / Task Results`
>> _If you see Task State: SUCCESS you are ready to move to deployment!_ 

## 2) Create fly.toml and custom Dockerfile

_[Full description](https://fly.io/docs/apps/launch/) of the Fly launch and deploy process_

Prereqs: flytmcl

Running `fly launch` will create generic fly.toml and Dockerfile required for deployment, however we need custom files for Cookiecutter Django

### Custom Dockerfile

This is a version of the Dockerfile found in `compose/production/django/Dockerfile` modified to fit Fly's build process.

> add notes about injecting dummy vars to run collect

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

# Set dummy vars for building purposes
ENV DJANGO_SETTINGS_MODULE "config.settings.production"
ENV DATABASE_URL "temp"
ENV DJANGO_SECRET_KEY "non-secret-key-for-building-purposes"
ENV REDIS_URL "temp"
ENV DJANGO_ADMIN_URL "temp"
ENV DJANGO_ALLOWED_HOSTS "temp"
ENV MAILJET_API_KEY "temp"
ENV MAILJET_SECRET_KEY "temp"
ENV SENTRY_DSN ""
ENV DJANGO_AWS_ACCESS_KEY_ID "temp"
ENV DJANGO_AWS_SECRET_ACCESS_KEY "temp"
ENV DJANGO_AWS_STORAGE_BUCKET_NAME "temp"

RUN python manage.py collectstatic --noinput

EXPOSE 8000

CMD ["gunicorn", "--bind", ":8000", "--workers", "1", "config.wsgi"]

```

### Custom fly.toml

As the primary config file, fly.toml here is modifed here to match varible names in the Dockerfile, add a Celery worker process, and run migrate on deploy.

The following variables require user input: `app, primary_region`
> Note the number of workers can be set under `processes/app` (default is 1)

_fly.toml_
```
# fly.toml app configuration file generated for fly-cookiecutter-django-1 on 2024-05-01T15:44:30+01:00
#
# See https://fly.io/docs/reference/configuration/ for information about how to use this file.
#

app = 'fly-cookiecutter-django-1'
primary_region = 'mad'
console_command = '/code/manage.py shell'

[build]

[deploy]
  release_command = 'python manage.py migrate'

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

## 3) Launch and Deploy

### Launch
Run `fly launch` from the root directory

_Launch wizard_
```
- YES to copy config to new app
- NO to overwriting Dockerfile
- YES to modifying configuration, click to open setting page, select Postgres and Redis instances
```

### Import secrets
- DATABASE_URL and REDIS_URL are set by `fly launch`, all others need to be imported
- Modify `.envs/.production/.django` as needed, if a service isnt ready just leave a temp value
- You must comment out `REDIS_URL`

Run the following command to import the secrets to Fly:

   ```
   cat .envs/.production/.django | fly secrets import
   ```

### Deploy

Run `fly deploy`

If deployment was successful, create a superuser via ssh console

```
fly ssh console
python manage.py createsuperuser
```

Now open tabs for Django Admin and test-task to verify the system is working.

--------------------

#### If you've gotten this far congratulations you are now live on Fly.io!

### Resources
- [Example code on Github](https://github.com/mswaringen/fly-cookiecutter-django)
- [Deploy with Github Actions](https://fly.io/docs/app-guides/continuous-deployment-with-github-actions/)  