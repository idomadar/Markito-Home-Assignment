# Bitcoin Price Tracker-Home Assignment

This application continuously monitors Bitcoin prices from the CoinGecko API, calculates statistical metrics, and provides actionable trading recommendations through a web-based dashboard. The system is designed with a modular architecture using Docker containers for scalability and deployment consistency.

## Features

- **Real-time Data Collection**: Fetches Bitcoin price, volume, and market cap data every minute
- **Statistical Analysis**: Calculates running averages, price volatility, and trend analysis
- **Trading Recommendations**: Provides intelligent buy/sell/hold signals based on price movements
- **Web Dashboard**: Professional web interface with real-time data visualization
- **Data Persistence**: SQLite database with Docker volume persistence
- **Containerized Architecture**: Multi-container setup for scalability and maintainability

## Architecture

The application consists of two main services:

1. **Bitcoin Tracker Service**: Core data collection and processing engine
2. **Web Dashboard Service**: Flask-based web interface for data visualization

Both services share data through Docker volumes and are orchestrated using Docker Compose.

## Prerequisites

- Docker Engine (version 20.0 or higher)
- Docker Compose (version 2.0 or higher)

Note: No additional dependencies are required. The application is fully containerized and includes all necessary runtime components.

## Quick Start

### Option 1: Automated Deployment (Recommended)
One-line deployment using Ansible automation:
```bash
# Clone and deploy with single command
git clone https://github.com/idomadar/Markito-Home-Assignment.git && cd Markito-Home-Assignment
ansible-playbook ansible/deploy-bitcoin-tracker.yml --ask-become-pass
```

### Option 2: Manual Docker Deployment
1. **Clone the repository**
   ```bash
   git clone https://github.com/idomadar/Markito-Home-Assignment.git
   cd Markito-Home-Assignment
   ```

2. **Start the application**
   ```bash
   docker-compose up -d
   ```

3. **Access the web dashboard**
   ```
   http://localhost:5000
   ```

## Detailed Setup Instructions

### Step 1: Environment Verification

Ensure Docker is installed and running:
```bash
docker --version
docker-compose --version
```

### Step 2: Application Deployment

Deploy the application stack:
```bash
# Start all services in detached mode
docker-compose up -d

# Verify container status
docker-compose ps
```

Expected output:
```
NAME                    SERVICE           STATUS    PORTS
bitcoin-price-tracker   bitcoin-tracker   Up        
bitcoin-web-dashboard   web-dashboard     Up        0.0.0.0:5000->5000/tcp
```

### Step 3: Service Verification

Check that services are running correctly:
```bash
# View application logs
docker-compose logs bitcoin-tracker
docker-compose logs web-dashboard

# Monitor real-time logs
docker-compose logs -f
```

### Step 4: Access the Dashboard

Open your web browser and navigate to:
```
http://localhost:5000
```

The dashboard provides:
- Current Bitcoin price and market data
- Historical price charts
- Trading recommendations
- System statistics and health metrics

## Management Commands

### Viewing Logs
```bash
# View logs for all services
docker-compose logs

# View logs for specific service
docker-compose logs bitcoin-tracker
docker-compose logs web-dashboard

# Follow logs in real-time
docker-compose logs -f
```

### Container Management
```bash
# Stop all services
docker-compose down

# Restart services
docker-compose restart

# Rebuild and restart (after code changes)
docker-compose up -d --build
```

### Data Management
```bash
# View data volumes
docker volume ls

# Backup database (optional)
docker-compose exec bitcoin-tracker cp /app/data/bitcoin_data.db /app/data/backup.db
```

## Configuration

### Environment Variables

The application supports the following environment variables:

- `PYTHONUNBUFFERED=1`: Ensures real-time log output
- `TZ=UTC`: Sets timezone for consistent timestamps

### Data Persistence

Application data is persisted using Docker volumes:
- `bitcoin_data`: Contains SQLite database files
- `bitcoin_logs`: Contains application log files

Data persists across container restarts and system reboots.

## Development Environment

This application was developed and tested on:
- **Operating System**: Windows 11 with WSL2 (Ubuntu 24.04)
- **Containerization**: Docker Desktop for Windows
- **Orchestration**: Docker Compose v2
- **Automation**: Ansible 9.2.0 for Infrastructure as Code
- **Development Tools**: WSL2 for Linux compatibility


## Automated Deployment

This project includes a complete Ansible automation solution for one-command deployment.

### Prerequisites for Ansible Deployment
- Target system: Linux (Ubuntu/Debian recommended)
- Ansible installed on deployment machine
- SSH access to target system (or local execution)

### One-Line Deployment
```bash
ansible-playbook ansible/deploy-bitcoin-tracker.yml --ask-become-pass
```


### Deployment Output
Upon successful completion, the playbook displays:
```
PLAY RECAP
localhost : ok=17 changed=X unreachable=0 failed=0

Bitcoin Price Tracker deployed successfully!
Main application: Running in Docker container
Web Dashboard: http://localhost:5000
```

### Manual Docker Alternative
For environments without Ansible, standard Docker Compose deployment is available


## Technical Specifications

### API Integration
- **Data Source**: CoinGecko API (https://api.coingecko.com)
- **Update Frequency**: Every 60 seconds
- **Rate Limiting**: Compliant with API limits
- **Error Handling**: Automatic retry with exponential backoff

### Database Schema
```sql
CREATE TABLE bitcoin_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    price REAL NOT NULL,
    volume REAL,
    market_cap REAL,
    recommendation TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);
```
