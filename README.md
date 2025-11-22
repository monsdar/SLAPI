# TeamSL API

## Overview

This project provides a RESTful API for the German DBB [TeamSL website](https://www.basketball-bund.net/static/#/ligaauswahl). It can be used to get information about basketball teams, standings and scores.

## Features

* Get data about available leagues
* Get data about the standings
* Get scheduled matches
* Get match outcomes

The app provides a `/docs` endpoint to get detailed information about the specific API endpoints.

# Installation
## Tech Stack

This project is built with the following technologies:
- Python 3.12.6
- Django
- django-ninja
- Docker

## Getting Started

1. Create and activate a virtual environment.
2. Install the dependencies with `pip install -r requirements.txt`.
3. Copy `env.example` to `.env` (or set the variables however you prefer) and adjust the values for your environment.
4. Run the development server with `python manage.py runserver`.

### Environment Variables

| Name | Description | Default |
| ---- | ----------- | ------- |
| `DJANGO_SECRET_KEY` | Secret key for Django | `insecure-development-key` |
| `DJANGO_DEBUG` | Enables Django debug mode | `true` |
| `DJANGO_ALLOWED_HOSTS` | Comma separated hostnames | `localhost,127.0.0.1` |
| `SLAPI_CACHE_DIRECTORY` | Directory used for cached upstream data | `<project-root>/cache` |
| `SLAPI_UPSTREAM_BASE_URL` | Base URL for the TeamSL upstream page | `https://www.basketball-bund.net/static/#/ligaauswahl` |
| `SLAPI_ADMIN_USER` | Default admin user to access the admin panel |
| `SLAPI_ADMIN_PASSWORD` | Default admin password to access the admin panel |
| `SLAPI_API_TOKEN` | API token for authenticating API requests (optional) | None |
| `CACHE_RETENTION_TIME_MIN` | Cache retention time in minutes | `2` |

Cache data is stored in local files within the cache directory. Configure `SLAPI_CACHE_DIRECTORY` to change location and configure a volume to persist the cache throughout redeployments. Cached responses automatically expire after `CACHE_RETENTION_TIME_MIN` minutes to ensure fresh data while avoiding redundant fast-cycle calls.

### Authentication

The API supports Bearer token authentication. To enable authentication, set the `SLAPI_API_TOKEN` environment variable. If this variable is not set, authentication is disabled and all requests are allowed (useful for development).

When authentication is enabled, all API endpoints (except `/health`) require a valid Bearer token in the Authorization header:

```
Authorization: Bearer your-secret-api-token-here
```

The `/health` endpoint is always public and does not require authentication.

### Tests

Run the project’s unit tests (including API and caching layers) with:

```
python manage.py test
```

## API Surface

| Endpoint | Description |
| -------- | ----------- |
| `GET /health` | Lightweight health probe to verify the service is reachable. |
| `GET /leagues` | Returns the cached-or-fetched list of leagues (placeholder data until the scraper is completed). |

Interactive documentation is available at `/docs`.

## Architecture

- **Django + django-ninja** provide routing, schema validation, and documentation generation.
- **api.services** contains the caching, upstream fetching, and normalization layers so the API remains stable even if the scraper changes.
- **File-based cache** ensures upstream responses are persisted between deployments and can be swapped for a different backend through the `FileCache` abstraction.
