# Integrations Guide

This guide covers how to integrate Incident Copilot with your existing monitoring and notification systems.

## Table of Contents

- [Incoming Webhooks (Alert Sources)](#incoming-webhooks)
- [Log Sources](#log-sources)
- [Outgoing Notifications](#outgoing-notifications)
- [AI Providers](#ai-providers)

---

## Incoming Webhooks

Incident Copilot receives alerts via HTTP webhooks. Configure your monitoring system to send alerts to:

```
http://your-server:8080/webhook/{source}
```

### PagerDuty

1. Go to **Services** → **Your Service** → **Integrations**
2. Add a **Generic Webhook (V3)** integration
3. Set the webhook URL to: `http://your-server:8080/webhook/pagerduty`
4. Select events: `incident.triggered`, `incident.resolved`

```yaml
# Example PagerDuty webhook payload
{
  "event": {
    "event_type": "incident.triggered",
    "data": {
      "id": "PT4KHLK",
      "title": "High CPU usage",
      "urgency": "high"
    }
  }
}
```

### Prometheus AlertManager

Add to your `alertmanager.yml`:

```yaml
receivers:
  - name: incident-copilot
    webhook_configs:
      - url: 'http://incident-copilot:8080/webhook/prometheus'
        send_resolved: true

route:
  receiver: incident-copilot
  routes:
    - match:
        severity: critical
      receiver: incident-copilot
```

### Datadog

1. Go to **Integrations** → **Webhooks**
2. Create a new webhook:
   - **Name**: incident-copilot
   - **URL**: `http://your-server:8080/webhook/datadog`
   - **Payload**: Use default or custom JSON

3. Add the webhook to your monitors

### Grafana

1. Go to **Alerting** → **Contact Points**
2. Add a new contact point:
   - **Type**: Webhook
   - **URL**: `http://your-server:8080/webhook/grafana`

3. Create a notification policy to route alerts

### Custom / Generic

Send any JSON payload to: `http://your-server:8080/webhook`

Required fields:
```json
{
  "title": "Alert title",
  "description": "What happened",
  "severity": "critical|high|medium|low|info",
  "labels": {
    "service": "api-gateway",
    "namespace": "production"
  }
}
```

---

## Log Sources

Configure log sources in `config/config.yaml`:

### Kubernetes

```yaml
log_sources:
  - name: k8s-production
    type: kubernetes
    namespaces:
      - production
      - default
    # Optional: specify kubectl context
    context: production-cluster
    # Optional: kubeconfig path
    kubeconfig: ~/.kube/config
```

**Requirements:**
- `kubectl` installed and configured
- Access to target namespaces

### Local Files

```yaml
log_sources:
  - name: app-logs
    type: file
    paths:
      - /var/log/app/*.log
      - /var/log/nginx/error.log
      - /var/log/syslog
```

**Supported formats:**
- ISO timestamps: `2024-01-15T10:30:00`
- Nginx format: `[2024/01/15 10:30:00]`
- Syslog format: `Jan 15 10:30:00`

### Elasticsearch

```yaml
log_sources:
  - name: elasticsearch
    type: elasticsearch
    host: elasticsearch.example.com:9200
    index_pattern: logs-*
    auth:
      username: elastic
      password: ${ELASTIC_PASSWORD}
```

### Loki (Coming Soon)

```yaml
log_sources:
  - name: loki
    type: loki
    endpoint: http://loki:3100
    query: '{namespace="production"}'
```

### Git History

```yaml
log_sources:
  - name: git-changes
    type: git
    repos:
      - /path/to/repo
      - /path/to/another/repo
    max_commits: 20
```

---

## Outgoing Notifications

### Slack

1. Create a Slack App or use an Incoming Webhook
2. Get the webhook URL
3. Configure in `config.yaml`:

```yaml
notifications:
  slack:
    webhook_url: https://hooks.slack.com/services/XXX/YYY/ZZZ
    channel: "#incidents"
    username: "Incident Copilot"
    icon_emoji: ":rotating_light:"
```

**Features:**
- Rich formatted messages with attachments
- Color-coded by severity
- Action buttons (coming soon)

### Microsoft Teams

1. In your Teams channel, add an Incoming Webhook connector
2. Copy the webhook URL
3. Configure:

```yaml
notifications:
  teams:
    webhook_url: https://outlook.office.com/webhook/...
```

### PagerDuty (Outgoing)

Update incident status back to PagerDuty:

```yaml
notifications:
  pagerduty:
    api_key: ${PAGERDUTY_API_KEY}
    # Optional: auto-resolve incidents
    auto_resolve: true
```

### Email (SMTP)

```yaml
notifications:
  email:
    smtp_host: smtp.example.com
    smtp_port: 587
    username: ${SMTP_USERNAME}
    password: ${SMTP_PASSWORD}
    from: incidents@example.com
    to:
      - oncall@example.com
      - team@example.com
```

---

## AI Providers

### Ollama (Local - Recommended)

Free, runs locally, no API keys needed:

```yaml
ai:
  provider: ollama
  endpoint: http://localhost:11434
  model: llama3.2:3b  # or llama3.1:8b for better results
```

**Setup:**
```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull a model
ollama pull llama3.2:3b
```

### OpenAI

```yaml
ai:
  provider: openai
  model: gpt-4o-mini  # or gpt-4o for best results
```

Set environment variable:
```bash
export OPENAI_API_KEY=sk-...
```

### Anthropic Claude

```yaml
ai:
  provider: anthropic
  model: claude-3-haiku-20240307  # or claude-3-sonnet
```

Set environment variable:
```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

### Azure OpenAI

```yaml
ai:
  provider: openai
  endpoint: https://your-resource.openai.azure.com/
  model: your-deployment-name
  api_key: ${AZURE_OPENAI_API_KEY}
```

---

## Docker Compose Example

Complete setup with all integrations:

```yaml
version: '3.8'

services:
  incident-copilot:
    image: tommieseals/incident-copilot:latest
    ports:
      - "8080:8080"
    environment:
      - SLACK_WEBHOOK_URL=${SLACK_WEBHOOK_URL}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    volumes:
      - ./config:/app/config
      - ./incidents.db:/app/incidents.db
    
  ollama:
    image: ollama/ollama
    ports:
      - "11434:11434"
    volumes:
      - ollama-data:/root/.ollama

volumes:
  ollama-data:
```

---

## Kubernetes Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: incident-copilot
spec:
  replicas: 1
  selector:
    matchLabels:
      app: incident-copilot
  template:
    metadata:
      labels:
        app: incident-copilot
    spec:
      containers:
        - name: incident-copilot
          image: tommieseals/incident-copilot:latest
          ports:
            - containerPort: 8080
          env:
            - name: SLACK_WEBHOOK_URL
              valueFrom:
                secretKeyRef:
                  name: incident-copilot-secrets
                  key: slack-webhook
          volumeMounts:
            - name: config
              mountPath: /app/config
      volumes:
        - name: config
          configMap:
            name: incident-copilot-config
---
apiVersion: v1
kind: Service
metadata:
  name: incident-copilot
spec:
  selector:
    app: incident-copilot
  ports:
    - port: 8080
      targetPort: 8080
```

---

## Troubleshooting

### Webhooks not received
1. Check firewall allows incoming connections on port 8080
2. Verify URL is accessible from alerting system
3. Check logs: `docker logs incident-copilot`

### AI analysis failing
1. Verify Ollama is running: `ollama list`
2. Check API key is set correctly
3. Verify network connectivity to AI provider

### Logs not gathered
1. Verify kubectl context: `kubectl config current-context`
2. Check file permissions for local logs
3. Verify Elasticsearch credentials

---

Need help? [Open an issue](https://github.com/tommieseals/incident-copilot/issues)
