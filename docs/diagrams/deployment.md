# Deployment

```mermaid
flowchart TB
    Browser[Browser HTTPS] --> CF[Cloudflare Access and Tunnel]
    CF --> Gateway[Gateway host port 3333]
    subgraph Fedora[Fedora Docker host]
        Gateway --> Web[Web private port 80]
        Gateway --> API[API private port 8000]
        API --> PG[(PostgreSQL private 5432)]
        API --> Redis[(Redis private 6379)]
        Worker[Trading worker 2 GiB] --> PG
        Worker --> Redis
        Scheduler[Scheduler] --> PG
        Research[Research 4 GiB bounded] --> PG
        Research --> Files[Parquet volume]
        Monitor[Optional private monitoring] --> API
    end
    Worker --> Venue[Exchange over outbound connection]
```

Research database access is restricted by grants; the edge does not expose PostgreSQL. Host cloudflared uses localhost:3333; container cloudflared uses gateway:3333. See DEPLOYMENT for origin filtering and hybrid-only loopback bindings.
