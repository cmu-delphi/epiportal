# EpiPortal Documentation

EpiPortal is a web application for browsing, filtering, and exporting infectious disease indicators from the [Delphi Epidata API](https://cmu-delphi.github.io/delphi-epidata/). It supports multiple data sources (COVIDcast, FluView, FluSurv, NIDSS Flu/Dengue) and geographic levels (US states, counties, HRR, MSA, HHS regions, and more).

## Table of Contents

- [Tech Stack](#tech-stack)
- [Prerequisites](#prerequisites)
- [Environment Configuration](#environment-configuration)
- [Running with Docker (Recommended)](#running-with-docker-recommended)
- [Running Locally (Without Docker)](#running-locally-without-docker)
- [Importing Data](#importing-data)
- [Exporting Data](#exporting-data)
- [Project Structure](#project-structure)
- [Key URLs and Endpoints](#key-urls-and-endpoints)
- [Custom Management Commands](#custom-management-commands)

---

## Tech Stack


| Layer            | Technology                                         |
| ---------------- | -------------------------------------------------- |
| Backend          | Django 5.0.7, Python 3.10                          |
| Database         | MySQL                                              |
| Cache            | Redis                                              |
| WSGI Server      | Gunicorn                                           |
| Reverse Proxy    | Nginx                                              |
| Frontend         | jQuery, Bootstrap 5, Select2, DataTables, Chart.js |
| Containerization | Docker, Docker Compose                             |
| External APIs    | Delphi Epidata API, Epivis                         |
| Error Tracking   | Sentry (optional)                                  |


---

## Prerequisites

### Docker Setup (recommended)

- [Docker](https://docs.docker.com/get-docker/) (v20+)
- [Docker Compose](https://docs.docker.com/compose/install/) (v2+)

### Native Setup

- Python 3.10
- [Pipenv](https://pipenv.pypa.io/en/latest/)
- MySQL server (5.7+ or 8.x)
- Redis server (6+)
- System packages: `gcc`, `default-libmysqlclient-dev`, `pkg-config` (required by `mysqlclient`)

---

## Environment Configuration

The application reads configuration from environment variables. A `.env` file at the project root is loaded by Docker Compose automatically.

**To get started, copy the CI env template and adjust it for your local environment:**

```bash
cp .ci.env .env
```

### Required Variables


| Variable              | Description                           | Default (dev)                |
| --------------------- | ------------------------------------- | ---------------------------- |
| `MYSQL_DATABASE`      | MySQL database name                   | `mysql_database`             |
| `MYSQL_USER`          | MySQL username                        | `mysql_user`                 |
| `MYSQL_PASSWORD`      | MySQL password                        | `mysql_password`             |
| `MYSQL_ROOT_PASSWORD` | MySQL root password                   | `mysql_root_password`        |
| `MYSQL_HOST`          | MySQL host                            | `db` (Docker) / `localhost`  |
| `MYSQL_PORT`          | MySQL port                            | `3306`                       |
| `SECRET_KEY`          | Django secret key (required in prod)  | Auto-generated in debug mode |
| `DEBUG`               | Enable debug mode                     | `True`                       |
| `ALLOWED_HOSTS`       | Comma-separated list of allowed hosts | `''`                         |


### Optional Variables


| Variable                    | Description                           | Default                               |
| --------------------------- | ------------------------------------- | ------------------------------------- |
| `REDIS_HOST_NAME`           | Redis hostname                        | `localhost`                           |
| `REDIS_PORT`                | Redis port                            | `6379`                                |
| `REDIS_DB`                  | Redis database number                 | `0`                                   |
| `EPIDATA_URL`               | Delphi Epidata API base URL           | `https://api.delphi.cmu.edu/epidata/` |
| `EPIDATA_API_KEY`           | Epidata API key                       | `''`                                  |
| `EPIVIS_URL`                | Epivis visualization URL              | `https://delphi.cmu.edu/epivis/`      |
| `ADMIN_USERNAME`            | Auto-created superuser username       | `admin`                               |
| `ADMIN_EMAIL`               | Auto-created superuser email          | `admin@andrew.cmu.edu`                |
| `ADMIN_PASSWORD`            | Auto-created superuser password       | `admin123`                            |
| `CORS_ORIGIN_WHITELIST`     | Comma-separated CORS origins          | `''`                                  |
| `CSRF_TRUSTED_ORIGINS`      | Comma-separated CSRF trusted origins  | `''`                                  |
| `SENTRY_DSN`                | Sentry DSN (enables Sentry when set)  | -                                     |
| `SENTRY_ENVIRONMENT`        | Sentry environment label              | `development`                         |
| `SENTRY_TRACES_SAMPLE_RATE` | Sentry traces sample rate             | `1.0`                                 |
| `PAGE_SIZE`                 | Default pagination page size          | `10`                                  |
| `CACHE_TIME`                | Cache TTL in seconds                  | `86400` (24 hours)                    |
| `MAIN_PAGE`                 | URL prefix (for sub-path deployments) | `'epiportal'`                         |
| `PROXY_DEPTH`               | Number of trusted reverse proxies     | `4`                                   |
| `REGISTRY`                  | Docker image registry prefix (CI)     | `""`                                  |
| `TAG`                       | Docker image tag suffix (CI)          | `""`                                  |


---

## Running with Docker (Recommended)

### 1. Create the environment file

```bash
cp .ci.env .env
```

Edit `.env` if you need to customize database credentials or other settings.

### 2. Build and start the services

```bash
docker-compose up --build
```

This starts four services:


| Service    | Container            | Port | Description         |
| ---------- | -------------------- | ---- | ------------------- |
| `db`       | `epiportal-db`       | 3306 | MySQL database      |
| `redis`    | `epiportal-redis`    | 6379 | Redis cache         |
| `epwebapp` | `epiportal-epwebapp` | 8000 | Django application  |
| `epnginx`  | `epiportal-epnginx`  | 80   | Nginx reverse proxy |


### 3. What happens on startup

The `epwebapp` service runs the following steps automatically:

1. **Migrate** the database (`manage.py migrate --noinput`)
2. **Collect static files** (`manage.py collectstatic --noinput`)
3. **Load fixture data** (`manage.py loaddata ./fixtures/*.json`) -- 18 JSON fixtures with geographies, indicator types, pathogens, etc.
4. **Create admin superuser** (`manage.py initadmin`) -- from `ADMIN_USERNAME`/`ADMIN_EMAIL`/`ADMIN_PASSWORD` env vars
5. **Start the dev server** on port 8000

### 4. Access the application

- **Direct (Django):** [http://localhost:8000/epiportal](http://localhost:8000)
- **Via Nginx:** [http://localhost/epiportal](http://localhost)
- **Django Admin:** [http://localhost:8000/epiportal/admin/](http://localhost:8000/admin/)

### Stopping the services

```bash
docker-compose down
```

To also remove database volumes (full reset):

```bash
docker-compose down -v
```

---

## Running Locally (Without Docker)

### 1. Install system dependencies

**macOS:**

```bash
brew install mysql pkg-config redis
```

**Ubuntu/Debian:**

```bash
sudo apt-get install -y gcc default-libmysqlclient-dev pkg-config mysql-server redis-server
```

### 2. Install Python dependencies

```bash
pip install pipenv
pipenv install --dev
```

### 3. Configure environment

```bash
cp .ci.env .env
```

Edit `.env` and set `MYSQL_HOST=localhost` (instead of `db`, which is the Docker service name).

### 4. Start MySQL and Redis

Make sure both services are running:

```bash
# macOS (Homebrew)
brew services start mysql
brew services start redis

# Ubuntu/Debian
sudo systemctl start mysql
sudo systemctl start redis
```

Create the database and user matching your `.env` values:

```sql
CREATE DATABASE mysql_database;
CREATE USER 'mysql_user'@'localhost' IDENTIFIED BY 'mysql_password';
GRANT ALL PRIVILEGES ON mysql_database.* TO 'mysql_user'@'localhost';
FLUSH PRIVILEGES;
```

### 5. Run database migrations

```bash
pipenv run python src/manage.py migrate
```

### 6. Load initial fixture data

```bash
pipenv run python src/manage.py loaddata src/fixtures/*.json
```

### 7. Create a superuser

Using the `initadmin` command (reads from env vars):

```bash
pipenv run python src/manage.py initadmin
```

Or interactively:

```bash
pipenv run python src/manage.py createsuperuser
```

### 8. Collect static files

```bash
pipenv run python src/manage.py collectstatic --noinput
```

### 9. Start the development server

```bash
pipenv run python src/manage.py runserver
```

The application will be available at [http://localhost:8000/epiportal](http://localhost:8000).

---

## Importing Data

EpiPortal supports multiple ways to populate data.

### Fixtures (Initial/Seed Data)

The `src/fixtures/` directory contains 18 JSON fixture files with geographic definitions, indicator types, pathogens, and other reference data:

```
src/fixtures/
├── census_regions.json
├── counties.json
├── format_types.json
├── geographic_granularities.json
├── geographic_scopes.json
├── hhs.json
├── hrr.json
├── hsa_nci.json
├── indicator_categories.json
├── indicator_types.json
├── msa.json
├── nation.json
├── ny_minus_jfk.json
├── pathogens.json
├── severity_pyramid_rungs.json
├── state.json
├── us_cities.json
└── us_territory.json
```

Load all fixtures at once:

```bash
python src/manage.py loaddata src/fixtures/*.json
```

Or load a specific fixture:

```bash
python src/manage.py loaddata src/fixtures/pathogens.json
```

### Admin: Data Import from Spreadsheets

Each supported model's admin change list page provides three buttons for importing data:

#### Option A: "Import data from spreadsheet" (direct, no diff)

Clicking **"Import data from spreadsheet"** fetches the CSV directly from the linked Google Sheet and applies the changes immediately. This is the fastest method, but you will **not** see a diff/preview of what will change before it is applied.

#### Option B: "Download source file" + "Import" (with diff preview)

For more control, use a two-step process:

1. Click **"Download source file"** to download the CSV from the Google Sheet to your machine.
2. Click the standard **"Import"** button (provided by django-import-export), select the downloaded CSV file, and submit.
3. Django will show an **import preview/diff** displaying which rows will be created, updated, or deleted. Review the changes and confirm.

This approach lets you inspect exactly what will change before committing the import.

#### Supported Models

| Model                          | Admin App             | Downloaded Filename                            |
| ------------------------------ | --------------------- | ---------------------------------------------- |
| SourceSubdivision              | Datasources           | `Source_Subdivisions.csv`                      |
| OtherEndpointSourceSubdivision | Datasources           | `Other_Endpoint_Source_Subdivisions.csv`       |
| Indicator                      | Indicators            | `Indicators.csv`                               |
| OtherEndpointIndicator         | Indicators            | `Other_Endpoint_Indicators.csv`                |
| NonDelphiIndicator             | Indicators            | `Non_Delphi_Indicators.csv`                    |
| USStateIndicator               | Indicators            | `US_State_Indicators.csv`                      |
| IndicatorSet                   | Indicator Sets        | `Indicator_Sets.csv`                           |
| NonDelphiIndicatorSet          | Indicator Sets        | `Non_Delphi_Indicator_Sets.csv`                |
| USStateIndicatorSet            | Indicator Sets        | `US_State_Indicator_Sets.csv`                  |
| ColumnDescription              | Indicator Sets        | `Indicator_Sets_Table_Column_Descriptions.csv` |
| FilterDescription              | Indicator Sets        | `Indicator_Sets_Table_Filter_Descriptions.csv` |
| ExpressViewIndicator           | Alternative Interface | `Express_View_Indicators.csv`                  |

The Google Sheet URLs backing these imports are configured in `src/epiportal/settings.py` under `SPREADSHEET_URLS`.

#### Important: Indicator Import Order

The **Indicator** model (COVIDcast indicators) requires a two-pass import because some indicators reference other indicators via the `base` field. When importing Indicators, you must use the resources in this order:

1. **First import** -- select **IndicatorResource** from the resource dropdown. This creates all indicator records with their full set of fields.
2. **Second import** -- select **IndicatorBaseResource** from the resource dropdown (using the same CSV file). This populates the `base` field, linking indicators to their base indicators that were created in the first pass.

If you skip the second step, the `base` relationships between indicators will not be set.

### Admin: Manual CSV/Excel File Import

The **"Import"** button on each model's admin page also accepts any local CSV or Excel file -- not only those downloaded via "Download source file". This is useful when you have manually prepared or edited data. The import preview/diff is always shown before confirming.

---

## Exporting Data

### User-Facing Export

Navigate to `/export/` in the web interface. Select indicators, geographies, and date ranges to generate `wget`/`curl` commands that fetch data directly from the Delphi Epidata API in CSV format.

### Admin Export

All models with import support also support export. In the Django admin, use the **"Export"** button to download data as CSV, Excel, or other supported formats.

---

## Project Structure

```
epiportal/
├── .ci.env                         # CI environment template
├── .github/workflows/              # CI/CD pipeline
├── docker-compose.yaml             # Docker services definition
├── Dockerfile                      # Main app image (Ubuntu 22.04 + Python 3.10)
├── Pipfile                         # Python dependencies (Pipenv)
├── Pipfile.lock                    # Locked dependency versions
├── gunicorn/
│   └── gunicorn.py                 # Gunicorn WSGI config
├── nginx/
│   ├── Dockerfile                  # Nginx image
│   └── default.conf.template       # Nginx site config
└── src/
    ├── manage.py                   # Django CLI entry point
    ├── fixtures/                   # 18 JSON seed data files
    ├── templates/                  # HTML templates
    ├── assets/                     # Static assets (CSS, JS, vendor libs)
    ├── epiportal/                  # Project configuration
    │   ├── settings.py             # Django settings
    │   ├── urls.py                 # Root URL routing
    │   ├── wsgi.py                 # WSGI application
    │   ├── middleware.py           # Request logging middleware
    │   └── management/commands/
    │       └── initadmin.py        # Auto-create superuser command
    ├── base/                       # Shared models and utilities
    │   ├── models.py               # Pathogen, Geography, GeographyUnit, etc.
    │   ├── views.py                # Epidata API proxy, error views
    │   ├── urls.py                 # /epidata/<endpoint>/ routing
    │   └── utils.py                # Spreadsheet import helpers
    ├── datasources/                # Data source definitions
    │   ├── models.py               # SourceSubdivision
    │   ├── resources.py            # Import/export resources
    │   └── admin.py                # Admin with spreadsheet import
    ├── indicators/                 # Indicator definitions
    │   ├── models.py               # Indicator, IndicatorType, Category, etc.
    │   ├── resources.py            # Import/export resources
    │   └── admin.py                # Admin with spreadsheet import
    ├── indicatorsets/              # Indicator set catalog
    │   ├── models.py               # IndicatorSet, FilterDescription, ColumnDescription
    │   ├── views.py                # Main list view, export, preview, code gen
    │   ├── urls.py                 # Catalog and API routes
    │   ├── utils.py                # Epidata helpers, export URL generation
    │   ├── filters.py              # IndicatorSet search/filter
    │   ├── resources.py            # Import/export resources
    │   └── admin.py                # Admin with spreadsheet import
    └── alternative_interface/      # Express dashboard
        ├── models.py               # ExpressViewIndicator
        ├── views.py                # Dashboard view, AJAX endpoints
        ├── utils.py                # Chart data fetching and preparation
        ├── helper.py               # COVIDcast/FluView geo mapping
        ├── urls.py                 # Express interface routes
        ├── resources.py            # Import/export resources
        └── admin.py                # Admin with spreadsheet import
```

### Application Modules


| Module                  | Purpose                                                                                                      |
| ----------------------- | ------------------------------------------------------------------------------------------------------------ |
| `epiportal`             | Django project configuration: settings, root URL routing, WSGI, middleware, management commands              |
| `base`                  | Shared models (Pathogen, Geography, GeographyUnit, SeverityPyramidRung), Epidata API proxy, import utilities |
| `datasources`           | Data source and source subdivision definitions (COVIDcast sources, FluView, etc.)                            |
| `indicators`            | Individual indicator models with types, categories, formats, and geographic coverage                         |
| `indicatorsets`         | Indicator set catalog -- the main browsing interface with filtering, preview, export, and code generation    |
| `alternative_interface` | Simplified "Express" dashboard for comparing disease indicators across pathogens and geographies with charts |


---

## Key URLs and Endpoints

### `GET /` -- Indicator Set Catalog (main page)

Renders the indicator set catalog with filtering support. Accepts `format=json` to return JSON instead of HTML.

| Query Parameter        | Type            | Description                                                          |
| ---------------------- | --------------- | -------------------------------------------------------------------- |
| `pathogens`            | multi-select    | Filter by pathogen IDs (repeatable)                                  |
| `geographic_scope`     | multi-select    | Filter by geographic scope                                           |
| `geographic_levels`    | multi-select    | Filter by geographic levels                                          |
| `severity_pyramid_rungs` | multi-select  | Filter by surveillance categories                                    |
| `original_data_provider` | multi-select  | Filter by original data provider                                     |
| `temporal_granularity` | multi-select    | Filter by time granularity (`Daily`, `Weekly`, `Monthly`, `Annually`, `Hourly`, `Other`) |
| `temporal_scope_end`   | string          | Filter by temporal scope end (`Ongoing` for active surveillance)     |
| `hosted_by_delphi`     | boolean         | If `true`/`on`/`1`, show only Delphi-hosted indicator sets           |
| `location_search`      | multi-select    | Filter by specific geographic locations (geo_type:geo_id pairs)      |
| `format`               | string          | Set to `json` to get JSON response instead of HTML                   |

### `POST /epivis/` -- Epivis Visualization

Builds an Epivis visualization URL from selected indicators and geographies. Request body is JSON.

| Body Field                  | Type     | Description                                       |
| --------------------------- | -------- | ------------------------------------------------- |
| `indicators`                | array    | List of indicator objects (each with `_endpoint`, `data_source`, `indicator`, etc.) |
| `covidCastGeographicValues` | array    | Selected COVIDcast geographic values               |
| `fluviewLocations`          | array    | Selected FluView locations                         |
| `nidssFluLocations`         | array    | Selected NIDSS Flu locations                       |
| `nidssDengueLocations`      | array    | Selected NIDSS Dengue locations                    |
| `flusurvLocations`          | array    | Selected FluSurv locations                         |

**Response:** `{ "epivis_url": "<url>" }`

### `POST /export/` -- Generate Export URLs

Generates wget/curl download commands for the selected indicators and geographies.

| Body Field                  | Type     | Description                                       |
| --------------------------- | -------- | ------------------------------------------------- |
| `indicators`                | array    | List of indicator objects                          |
| `covidCastGeographicValues` | array    | Selected COVIDcast geographic values               |
| `fluviewLocations`          | array    | Selected FluView locations                         |
| `nidssFluLocations`         | array    | Selected NIDSS Flu locations                       |
| `nidssDengueLocations`      | array    | Selected NIDSS Dengue locations                    |
| `flusurvLocations`          | array    | Selected FluSurv locations                         |
| `start_date`                | string   | Start date for the data range                      |
| `end_date`                  | string   | End date for the data range                        |
| `apiKey`                    | string   | Epidata API key (optional)                         |

**Response:** `{ "data_export_block": "<html>", "data_export_commands": ["<cmd>", ...] }`

### `POST /preview_data/` -- Preview Indicator Data

Fetches a preview of data from the Epidata API for the selected indicators.

| Body Field                  | Type     | Description                                       |
| --------------------------- | -------- | ------------------------------------------------- |
| `indicators`                | array    | List of indicator objects                          |
| `covidCastGeographicValues` | array    | Selected COVIDcast geographic values               |
| `fluviewLocations`          | array    | Selected FluView locations                         |
| `nidssFluLocations`         | array    | Selected NIDSS Flu locations                       |
| `nidssDengueLocations`      | array    | Selected NIDSS Dengue locations                    |
| `flusurvLocations`          | array    | Selected FluSurv locations                         |
| `start_date`                | string   | Start date for the data range                      |
| `end_date`                  | string   | End date for the data range                        |
| `apiKey`                    | string   | Epidata API key (optional)                         |

**Response:** JSON array of data rows.

### `POST /create_query_code/` -- Generate Code Snippets

Generates Python and R code snippets for querying the Epidata API.

| Body Field                  | Type     | Description                                       |
| --------------------------- | -------- | ------------------------------------------------- |
| `indicators`                | array    | List of indicator objects                          |
| `covidCastGeographicValues` | array    | Selected COVIDcast geographic values               |
| `fluviewLocations`          | array    | Selected FluView locations                         |
| `nidssFluLocations`         | array    | Selected NIDSS Flu locations                       |
| `nidssDengueLocations`      | array    | Selected NIDSS Dengue locations                    |
| `flusurvLocations`          | array    | Selected FluSurv locations                         |
| `start_date`                | string   | Start date for the data range                      |
| `end_date`                  | string   | End date for the data range                        |

**Response:** `{ "python_code_blocks": [...], "r_code_blocks": [...] }`

### `POST /get_available_geos/` -- Available Geographies

Returns available geographic regions for the selected COVIDcast indicators.

| Body Field   | Type   | Description                                                    |
| ------------ | ------ | -------------------------------------------------------------- |
| `indicators` | array  | List of indicator objects (with `data_source` and `indicator`) |

**Response:** `{ "geographic_granularities": [{ "text": "<geo_level>", "children": [...] }, ...] }`

### `GET /get_related_indicators/` -- Related Indicators

Returns all indicators belonging to indicator sets matching the current filter. Accepts the same query parameters as the main catalog (`/`).

**Response:** `{ "related_indicators": [{ "id", "display_name", "name", "source", "endpoint", ... }, ...] }`

### `GET /get_table_stats_info/` -- Table Statistics

Returns counts of indicator sets, indicators, and locations matching the current filter. Accepts the same query parameters as the main catalog (`/`).

**Response:** `{ "num_of_indicator_sets": <int>, "num_of_indicators": <int>, "num_of_locations": <int> }`

### `GET /check_fluview_geo_coverage/` -- FluView Coverage Check

Checks which FluView/FluView Clinical indicators have no data for a given geography.

| Query Parameter | Type   | Description                                                 |
| --------------- | ------ | ----------------------------------------------------------- |
| `geo`           | string | Geographic region identifier                                |
| `indicators`    | string | JSON-encoded array of indicator objects (`data_source`, `indicator`) |

**Response:** `{ "not_covered_indicators": [...] }`

### `GET /epidata/<endpoint>/` -- Epidata API Proxy

Proxies requests to the Delphi Epidata API. The `<endpoint>` path segment specifies the Epidata endpoint (e.g., `covidcast`, `fluview`, `flusurv`, `nidss_flu`, `nidss_dengue`). All query parameters are forwarded to the upstream API. The server automatically appends the configured `EPIDATA_API_KEY`.

### `GET /alternative_interface` -- Express Dashboard

Simplified dashboard for comparing disease indicators with charts.

| Query Parameter | Type   | Description                                              |
| --------------- | ------ | -------------------------------------------------------- |
| `pathogen`      | string | Pathogen/menu item to filter by (e.g., `Influenza`, `COVID-19`, `RSV`, `Influenza-Like Illness (ILI)`) |
| `geography`     | string | Geographic region to display chart data for              |

### `GET /api/get_available_geos` -- Express: Available Geographies

Returns available geographies for a selected pathogen in the Express dashboard.

| Query Parameter | Type   | Description                              |
| --------------- | ------ | ---------------------------------------- |
| `pathogen`      | string | Pathogen/menu item to get geographies for |

**Response:** `{ "available_geos": [...] }`

### `GET /api/get_chart_data` -- Express: Chart Data

Returns chart data for a selected pathogen and geography in the Express dashboard.

| Query Parameter | Type   | Description                             |
| --------------- | ------ | --------------------------------------- |
| `pathogen`      | string | Pathogen/menu item                      |
| `geography`     | string | Geographic region                       |

**Response:** `{ "chart_data": { ... } }`

### Other Endpoints

| URL          | Description                          |
| ------------ | ------------------------------------ |
| `/admin/`    | Django admin panel                   |
| `/__debug__/`| Django Debug Toolbar (debug mode only) |


---

## Custom Management Commands

### `initadmin`

Automatically creates a Django superuser from environment variables. Skips creation if the user already exists.

```bash
python src/manage.py initadmin
```


| Env Variable     | Default                |
| ---------------- | ---------------------- |
| `ADMIN_USERNAME` | `admin`                |
| `ADMIN_EMAIL`    | `admin@andrew.cmu.edu` |
| `ADMIN_PASSWORD` | `admin123`             |



