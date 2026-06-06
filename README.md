🌤️ Weather ETL Pipeline on AWS

End-to-end data engineering pipeline that ingests real-time weather data from the OpenWeatherMap API, processes it through a Bronze/Silver/Gold medallion architecture on AWS S3, and loads it into a PostgreSQL database on AWS RDS — containerized with Docker and orchestrated via cron on EC2.


🏗️ Architecture
┌─────────────────┐
│  OpenWeather    │  REST API (free tier · 5 cities)
│     API         │
└────────┬────────┘
         │ JSON / HTTP
         ▼
┌─────────────────────────────────┐
│         AWS EC2 t3.micro        │
│  ┌────────────────────────────┐ │
│  │   Docker Container         │ │
│  │   Python 3.12              │ │
│  │   pipeline.py              │ │
│  └────────────────────────────┘ │
│  ┌────────────────────────────┐ │
│  │   Cron Job (every hour)    │ │
│  └────────────────────────────┘ │
└──────┬──────────────────────────┘
       │
       ▼
┌─────────────────────────────────┐
│          AWS S3 Bucket          │
│                                 │
│  bronze/weather/YYYY/MM/DD/     │  ← Raw JSON (as-is from API)
│  silver/weather/YYYY/MM/DD/     │  ← Cleaned Parquet (typed, no nulls)
└──────┬──────────────────────────┘
       │ psycopg2 upsert
       ▼
┌─────────────────────────────────┐
│    AWS RDS PostgreSQL (Gold)    │
│    fact_weather table           │  ← Analytics-ready, idempotent
└─────────────────────────────────┘

🥇 Medallion Architecture
LayerFormatLocationDescriptionBronzeJSONS3 bronze/Raw data exactly as received from API — never modifiedSilverParquetS3 silver/Cleaned, typed, null-handled, deduplicatedGoldPostgreSQL tableRDSAggregated, analytics-ready, upserted idempotently

⚙️ Tech Stack
ComponentTechnologyCloud ProviderAWS (Free Tier)ComputeEC2 t3.micro (Ubuntu 26.04)StorageS3 (Bronze + Silver layers)DatabaseRDS PostgreSQL 16 (db.t3.micro)ContainerizationDockerSchedulingLinux cronLanguagePython 3.12Key Librariesboto3, pandas, pyarrow, psycopg2, tenacityNetworkingVPC with public/private subnets, Security Groups

📁 Project Structure
weather-etl-aws/
│
├── pipeline.py        # Orchestrator — runs extract → transform → load
├── extract.py         # Bronze layer: OpenWeatherMap API → S3 JSON
├── transform.py       # Silver layer: JSON → cleaned Parquet
├── load.py            # Gold layer: Parquet → RDS PostgreSQL (upsert)
├── config.py          # Config from environment variables (validated)
├── Dockerfile         # Python 3.12-slim container
├── requirements.txt   # Dependencies
└── .env.example       # Environment variables template

🛡️ Engineering Best Practices

Zero hardcoded credentials — all secrets via .env / environment variables
Idempotent pipeline — ON CONFLICT DO UPDATE prevents duplicates on re-runs
Retry with exponential backoff — tenacity handles API failures gracefully (3 attempts)
Structured JSON logging — CloudWatch-compatible log format
Rollback on failure — DB transaction rolls back automatically on load error
Connection timeouts — all external connections have explicit timeouts
Schema validation — records validated before transformation
Null checks — critical columns checked before loading to Gold


🗄️ Database Schema (Gold Layer)
sqlCREATE TABLE fact_weather (
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
    UNIQUE (city, measurement_ts)     -- idempotency key
);

🚀 How to Run
Prerequisites

AWS account (Free Tier)
OpenWeatherMap API key (free at openweathermap.org)
Docker installed

1. Clone the repository
bashgit clone https://github.com/CauanCosta7/weather-etl-aws.git
cd weather-etl-aws
2. Configure environment variables
bashcp .env.example .env
# Edit .env with your credentials
nano .env
3. Build and run with Docker
bashdocker build -t weather-etl .
docker run --env-file .env weather-etl
4. Schedule with cron (runs every hour)
bashcrontab -e
# Add the following line:
0 * * * * docker run --env-file /home/ubuntu/weather_etl/.env weather-etl >> /home/ubuntu/weather_etl/pipeline.log 2>&1

🌍 AWS Infrastructure
VPC: weather-etl-vpc (10.0.0.0/16)
├── Public Subnet  (sa-east-1a) → EC2
└── Private Subnet (sa-east-1a) → RDS

Security Group: weather-etl-sg
├── Inbound: SSH (22)   → your IP only
└── Inbound: PG  (5432) → 10.0.0.0/16 (VPC internal only)

RDS is in a private subnet — not accessible from the internet. Only EC2 within the same VPC can connect.


📊 Sample Data
sqlSELECT city, temp_celsius, humidity_pct, weather_description, measurement_ts
FROM fact_weather
ORDER BY measurement_ts DESC
LIMIT 5;
      city      | temp_celsius | humidity_pct | weather_description |     measurement_ts
----------------+--------------+--------------+---------------------+------------------------
 São Paulo      |        15.87 |           87 | broken clouds       | 2026-06-02 22:00:05+00
 Rio de Janeiro |        21.08 |           84 | broken clouds       | 2026-06-02 21:57:00+00
 Brasília       |        17.81 |           78 | overcast clouds     | 2026-06-02 21:58:56+00
 Curitiba       |        11.48 |           86 | clear sky           | 2026-06-02 21:55:58+00
 Salvador       |        29.27 |           67 | overcast clouds     | 2026-06-02 22:00:03+00

💰 Cost
Running on AWS Free Tier — $0/month for 12 months:
ServiceFree TierMonthly costEC2 t3.micro750h/month$0RDS db.t3.micro750h/month$0S35GB$0Data Transfer100GB out$0Total$0

🔮 Next Steps

 Migrate orchestration from cron to Apache Airflow
 Add pytest unit tests for transform layer
 Implement CloudWatch alarms for pipeline failures
 Expand to 50+ cities with parallel extraction (ThreadPoolExecutor)
 Add dbt for data modeling on top of Gold layer
 Migrate to GCP (BigQuery + Cloud Functions) for multi-cloud experience


👤 Author
Cauan Costa

GitHub: @CauanCosta7
Project built as a Data Engineering portfolio project demonstrating cloud-native ETL architecture on AWS.
