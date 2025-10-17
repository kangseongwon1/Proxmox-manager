# 시스템 아키텍처 (Mermaid)

```mermaid
graph TB
    subgraph "Frontend Layer"
        A[WEB UI<br/>Frontend]
    end
    
    subgraph "Backend Layer"
        B[Flask AI<br/>Backend]
        C[Redis<br/>Message Queue]
        D[Celery 워커<br/>Task Processor]
    end
    
    subgraph "Database Layer"
        E[PostgreSQL<br/>Database]
    end
    
    subgraph "Monitoring Layer"
        F[Grafana<br/>Monitoring]
        G[Prometheus<br/>Metrics]
        H[Node Exporter<br/>Agents]
    end
    
    subgraph "Infrastructure Layer"
        I[Vault<br/>Secrets]
        J[Terraform<br/>Infrastructure]
        K[Ansible<br/>Config 설정 및 패키지 설치]
    end
    
    subgraph "Virtualization Layer"
        L[Proxmox VE<br/>Hypervisor]
        M[Virtual Machines]
        N[Docker<br/>Containers]
    end
    
    %% Connections
    A <--> B
    B <--> C
    C <--> D
    B --> E
    E --> L
    
    A --> F
    F <--> G
    G <--> H
    H --> L
    
    C --> J
    J --> I
    I --> L
    
    D --> K
    K --> L
    
    L --> M
    L --> N
```

## 주요 데이터 흐름

### 1. 사용자 요청 → VM 작업
```
WEB UI → Flask AI → Redis → Celery 워커 → Terraform/Ansible → Proxmox VE → Virtual Machines
```

### 2. 모니터링 데이터 흐름
```
Node Exporter → Prometheus → Grafana → WEB UI
```

### 3. 데이터 저장
```
Flask AI → PostgreSQL ← Proxmox VE
```

### 4. 비밀 관리
```
Terraform → Vault → Proxmox VE
```

### 5. 실시간 알림 시스템
```
Celery 워커 → PostgreSQL → SSE 스트림 → WEB UI → 실시간 UI 업데이트
```

### 6. 인프라 자동화
```
Redis → Terraform → Vault → Proxmox VE
```

### 7. 설정 관리
```
Celery 워커 → Ansible → Proxmox VE
```
