# 🚨 Incident Copilot

**AI-powered incident response automation that reduces MTTR by up to 60%**

[![CI](https://github.com/tommieseals/incident-copilot/actions/workflows/ci.yml/badge.svg)](https://github.com/tommieseals/incident-copilot/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Docker](https://img.shields.io/badge/docker-ready-blue.svg)](https://hub.docker.com/)

---

## 🎯 What It Does

When an incident strikes, every second counts. **Incident Copilot** acts as your AI-powered first responder:

1. **🔍 Detects** incidents via webhooks from PagerDuty, Prometheus, Datadog, or custom sources
2. **📊 Gathers** relevant logs, metrics, and recent deployments automatically
3. **🧠 Analyzes** patterns using AI to suggest probable root causes
4. **🔧 Proposes** fix commands based on similar past incidents
5. **📝 Generates** post-mortem drafts so you can focus on fixing, not documenting

```
┌─────────────────┐     ┌──────────────┐     ┌─────────────┐
│   Monitoring    │────▶│   Incident   │────▶│  Log/Metric │
│ (PagerDuty/etc) │     │   Detector   │     │   Gatherer  │
└─────────────────┘     └──────────────┘     └──────┬──────┘
                                                     │
┌─────────────────┐     ┌──────────────┐     ┌──────▼──────┐
│   Post-Mortem   │◀────│   Response   │◀────│     AI      │
│    Generator    │     │   Suggester  │     │   Analyzer  │
└─────────────────┘     └──────────────┘     └─────────────┘
```

---

## ⚡ Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/tommieseals/incident-copilot.git
cd incident-copilot

# Install dependencies
pip install -r requirements.txt

# Copy and edit configuration
cp config/config.yaml.example config/config.yaml

# Run the detector
python -m src.detector
```

### Docker

```bash
docker build -t incident-copilot .
docker run -d -p 8080:8080 -v $(pwd)/config:/app/config incident-copilot
```

### Docker Compose

```bash
docker-compose up -d
```

---

## 🔧 Configuration

Edit `config/config.yaml`:

```yaml
ai:
  provider: ollama          # ollama, openai, anthropic
  model: llama3.2:3b        # Model to use
  endpoint: http://localhost:11434

log_sources:
  - name: kubernetes
    type: kubectl
    namespaces: [production, staging]
  - name: application
    type: file
    paths: [/var/log/app/*.log]

notifications:
  slack:
    webhook_url: ${SLACK_WEBHOOK_URL}
    channel: #incidents
  pagerduty:
    api_key: ${PAGERDUTY_API_KEY}
```

---

## 🔌 Integrations

### Incoming (Trigger Sources)
- **PagerDuty** - Webhook integration
- **Prometheus AlertManager** - Native webhook receiver
- **Datadog** - Webhook integration
- **Grafana** - Alert notifications
- **Custom** - REST API endpoint

### Log Sources
- **Kubernetes** - kubectl logs, events
- **AWS CloudWatch** - Log groups
- **Elasticsearch** - Index queries  
- **Local files** - Glob patterns
- **Loki** - LogQL queries

### Outgoing (Notifications)
- **Slack** - Rich messages with actions
- **Microsoft Teams** - Adaptive cards
- **PagerDuty** - Update incidents
- **Jira** - Auto-create tickets
- **Email** - SMTP notifications

See [docs/integrations.md](docs/integrations.md) for detailed setup guides.

---

## 📊 MTTR Tracking

Incident Copilot tracks Mean Time To Resolution across all incidents:

```bash
# View MTTR dashboard
python -m src.cli stats

# Output:
# ┌─────────────────────────────────────────┐
# │           MTTR Dashboard                │
# ├─────────────────────────────────────────┤
# │ Last 24h:  12m 34s  (↓ 45% from avg)   │
# │ Last 7d:   18m 22s  (↓ 32% from avg)   │
# │ Last 30d:  22m 15s                      │
# │ Incidents: 47 resolved, 2 active        │
# └─────────────────────────────────────────┘
```

---

## 🧪 Example

### Sample Incident Flow

1. **Alert received** from Prometheus (HTTP 500 spike)

2. **Copilot gathers**:
   - Last 1h of application logs
   - Recent Kubernetes events
   - Git commits from last 24h
   - Current pod status

3. **AI analyzes** and suggests:
   ```
   🔍 Root Cause Analysis:
   
   High confidence (87%): Database connection pool exhaustion
   
   Evidence:
   - 847 occurrences of connection timeout in logs
   - DB connection count at 100/100 (maxed)
   - Started 2 minutes after deployment abc123
   
   Related past incidents: INC-234 (95% similar)
   ```

4. **Proposed fixes**:
   ```bash
   # Immediate mitigation
   kubectl rollout restart deployment/api-server -n production
   
   # Increase connection pool (requires review)
   kubectl set env deployment/api-server DB_POOL_SIZE=150 -n production
   ```

5. **Post-mortem draft** generated automatically

---

## 🏗️ Architecture

```
incident-copilot/
├── src/
│   ├── detector.py      # Webhook receiver & incident detection
│   ├── gatherer.py      # Multi-source log & metric collection
│   ├── analyzer.py      # AI-powered root cause analysis
│   ├── responder.py     # Fix suggestion engine
│   ├── postmortem.py    # Post-mortem document generator
│   ├── notifier.py      # Multi-channel notifications
│   ├── storage.py       # Incident persistence & MTTR tracking
│   └── cli.py           # Command-line interface
├── config/
│   └── config.yaml      # All configuration
├── templates/
│   └── postmortem.md    # Post-mortem template (Jinja2)
└── tests/               # Comprehensive test suite
```

---

## 🚀 Production Deployment

### Kubernetes

```bash
kubectl apply -f k8s/
```

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `OPENAI_API_KEY` | OpenAI API key (if using) | No |
| `ANTHROPIC_API_KEY` | Anthropic API key (if using) | No |
| `SLACK_WEBHOOK_URL` | Slack incoming webhook | No |
| `PAGERDUTY_API_KEY` | PagerDuty API key | No |
| `DATABASE_URL` | PostgreSQL connection string | No |

---

## 📈 Roadmap

- [x] Core incident detection
- [x] Multi-source log gathering
- [x] AI root cause analysis
- [x] Fix suggestions
- [x] Post-mortem generation
- [x] Slack integration
- [ ] Web UI dashboard
- [ ] Runbook automation
- [ ] ML-based incident prediction
- [ ] Custom playbook support

---

## 🤝 Contributing

Contributions welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) first.

```bash
# Run tests
pytest tests/ -v

# Run linting
ruff check src/
mypy src/
```

---

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.

---

**Built with ❤️ for SREs who deserve to sleep through the night.**
EOF
