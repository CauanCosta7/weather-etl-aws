# 🌤️ Weather ETL Pipeline on AWS

> End-to-end data engineering pipeline that ingests real-time weather data from the OpenWeatherMap API, processes it through a **Bronze/Silver/Gold medallion architecture** on AWS S3, and loads it into a PostgreSQL database on AWS RDS — containerized with Docker and orchestrated via cron on EC2.

![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python)
![AWS](https://img.shields.io/badge/AWS-Free%20Tier-orange?logo=amazonaws)
![Docker](https://img.shields.io/badge/Docker-containerized-blue?logo=docker)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791?logo=postgresql)

---

## 🏗️ Architecture

```
OpenWeather API
      │
      │  REST API (JSON)
      ▼
EC2 t3.micro (Docker + Python 3.12 + cron)
      │
      ├──► S3 bronze/weather/YYYY/MM/DD/   ← Raw JSON (as-is from API)
      │
      ├──► S3 silver/weather/YYYY/MM/DD/   ← Cleaned Parquet
      │
      └──► RDS PostgreSQL - fact_weather   ← Analytics-ready (upsert)
```

---

## 🥇 Medallion Architecture

| Layer | Format | Location | Description |
|-------|--------|----------|-------------|
| **Bronze** | JSON | S3 `bronze/` | Raw data exactly as received from API |
| **Silver** | Parquet | S3 `silver/` | Cleaned, typed, null-handled, deduplicated |
| **Gold** | PostgreSQL | RDS | Aggregated, analytics-ready, upserted idempotently |

---

## ⚙️ Tech Stack

| Component | Technology |
|-----------|-----------|
| Cloud | AWS Free Tier |
| Compute | EC2 t3.micro (Ubuntu 26.04) |
| Storage | S3 (Bronze + Silver) |
| Database | RDS PostgreSQL 16 (db.t3.micro) |
| Container | Docker (Python 3.12-slim) |
| Scheduler | Linux cron |
| Language | Python 3.12 |
| Libraries | boto3, pandas, pyarrow, psycopg2, tenacity |
| Network | VPC, public/private subnets, Security Groups |

---

## 📁 Project Structure

```
weather-etl-aws/
├── pipeline.py       # Orchestrator — runs extract → transform → load
├── extract.py        # Bronze: OpenWeatherMap API → S3 JSON
├── transform.py      # Silver: JSON → cleaned Parquet
├── load.py           # Gold: Parquet → RDS PostgreSQL (upsert)
├── config.py         # Config from environment variables (validated)
├── Dockerfile        # Python 3.12-slim container
├── requirements.txt  # Dependencies
└── .env.example      # Environment variables template
```

---

## 🛡️ Engineering Best Practices

- ✅ **Zero hardcoded credentials** — all secrets via `.env` / environment variables
- ✅ **Idempotent pipeline** — `ON CONFLICT DO UPDATE` prevents duplicates on re-runs
- ✅ **Retry with exponential backoff** — `tenacity` handles API failures (3 attempts)
- ✅ **Structured JSON logging** — CloudWatch-compatible log format
- ✅ **Rollback on failure** — DB transaction rolls back automatically on load error
- ✅ **Connection timeouts** — all external connections have explicit timeouts
- ✅ **Schema validation** — records validated before transformation
- ✅ **Null checks** — critical columns checked before loading to Gold

---

## 🗄️ Database Schema (Gold Layer)

```sql
CREATE TABLE fact_weather (
    id                  SERIAL PRIMARY KEY,
    city                VARCHAR(100)   NOT NULL,
    country             VARCHAR(10),
    lat                 NUMERIC(9,6),
    lon                 NUMERIC(9,6),
    temp_celsius        NUMERIC(5,2),
    feels_like          NUMERIC(5,2),
    temp_min            NUMERIC(5,2),
    temp_max            NUMERIC(5,2),
    humidity_pct        INTEGER,
    pressure_hpa        INTEGER,
    wind_speed_ms       NUMERIC(6,2),
    wind_deg            INTEGER,
    weather_main        VARCHAR(50),
    weather_description VARCHAR(100),
    cloudiness_pct      INTEGER,
    visibility_m        INTEGER,
    measurement_ts      TIMESTAMPTZ    NOT NULL,
    extracted_at        TIMESTAMPTZ,
    loaded_at           TIMESTAMPTZ    DEFAULT NOW(),
    UNIQUE (city, measurement_ts)
);
```

---

## 🚀 How to Run

### Prerequisites
- AWS account (Free Tier)
- OpenWeatherMap API key — [get one free](https://openweathermap.org/api)
- Docker installed

### 1. Clone the repository
```bash
git clone https://github.com/CauanCosta7/weather-etl-aws.git
cd weather-etl-aws
```

### 2. Configure environment variables
```bash
cp .env.example .env
nano .env  # fill in your credentials
```

### 3. Build and run with Docker
```bash
docker build -t weather-etl .
docker run --env-file .env weather-etl
```

### 4. Schedule with cron (every hour)
```bash
crontab -e
# Add:
0 * * * * docker run --env-file /home/ubuntu/weather_etl/.env weather-etl >> /home/ubuntu/weather_etl/pipeline.log 2>&1
```

---

## 🌍 AWS Infrastructure

```
VPC: weather-etl-vpc (10.0.0.0/16)
├── Public Subnet  → EC2 (internet access)
└── Private Subnet → RDS (internal only)

Security Group: weather-etl-sg
├── SSH  (22)   → your IP only
└── PG   (5432) → 10.0.0.0/16 (VPC internal only)
```

> RDS is in a **private subnet** — not accessible from the internet. Only EC2 within the same VPC can connect.

---

## 📊 Sample Output

```
{"time":"2026-06-02 06:04:10","level":"INFO","msg":"pipeline_start"}
{"time":"2026-06-02 06:04:11","level":"INFO","msg":"city_extracted city=Sao Paulo"}
{"time":"2026-06-02 06:04:12","level":"INFO","msg":"city_extracted city=Rio de Janeiro"}
{"time":"2026-06-02 06:04:12","level":"INFO","msg":"bronze_saved records=5"}
{"time":"2026-06-02 06:04:13","level":"INFO","msg":"silver_saved records=5"}
{"time":"2026-06-02 06:04:13","level":"INFO","msg":"load_committed records=5"}
{"time":"2026-06-02 06:04:13","level":"INFO","msg":"pipeline_success records_loaded=5 elapsed_total_s=2.71"}
```

---

## 💰 Cost

Running on **AWS Free Tier — $0/month** for 12 months:

| Service | Free Tier | Cost |
|---------|-----------|------|
| EC2 t3.micro | 750h/month | $0 |
| RDS db.t3.micro | 750h/month | $0 |
| S3 | 5 GB | $0 |
| Data Transfer | 100 GB out | $0 |
| **Total** | | **$0** |

---

## 🔮 Next Steps

- [ ] Migrate orchestration from cron to **Apache Airflow**
- [ ] Add **pytest** unit tests for transform layer
- [ ] Implement **CloudWatch** alarms for pipeline failures
- [ ] Expand to 50+ cities with parallel extraction (ThreadPoolExecutor)
- [ ] Add **dbt** for data modeling on top of Gold layer
- [ ] Migrate to **GCP** (BigQuery + Cloud Functions) for multi-cloud experience

---

## 👤 Author

**Cauan Costa** — [@CauanCosta7](https://github.com/CauanCosta7)

> Portfolio project demonstrating cloud-native ETL architecture on AWS with production-grade engineering practices.
