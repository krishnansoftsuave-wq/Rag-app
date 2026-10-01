import sys
import os
import json
import time

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import datetime
from app.services import hybrid_retriever_service, vector_store_service, chunk_text_with_spans
from app.agents.rag_agent import AdaptiveRAGAgent
from app.evaluation.evaluator import evaluate_answer

novacloud_text = """
NovaTech Cloud Platform
10-Page Synthetic Document for RAG Evaluation
Designed to test semantic retrieval, exact retrieval, multi-hop reasoning, numerical reasoning, comparisons, negative questions, timelines, and long-context retrieval.

Page 1 — Company Overview
NovaTech Cloud Platform
NovaTech Systems is a fictional technology company founded in 2018 with its headquarters in Austin, Texas. The company develops cloud-based software for medium-sized businesses. Its primary product, NovaCloud, provides infrastructure management, application deployment, monitoring, security, and data analytics through a unified platform.
NovaCloud was initially launched as an internal infrastructure management tool. In 2019, NovaTech released the first commercial version of the platform. The initial version supported only virtual machines and basic monitoring. Over the following years, NovaTech expanded the platform to support containers, Kubernetes clusters, serverless applications, managed databases, object storage, and event-driven architectures.
The company currently organizes NovaCloud into five major product areas: Compute Services, Data Services, Application Services, Security Services, and Observability Services.
Compute Services are responsible for running workloads. Data Services provide managed databases, object storage, caching, and data processing. Application Services provide APIs, message queues, scheduled jobs, and application deployment functionality. Security Services manage authentication, authorization, secrets, encryption, vulnerability scanning, and audit logs. Observability Services collect metrics, logs, traces, and application events.
NovaCloud follows a regional architecture. Customers select a primary region when creating their account. Data is stored in the customer's selected region unless a customer explicitly enables cross-region replication.
NovaCloud currently supports four primary regions: US East, US West, Europe Central, and Asia Pacific. The US East region is the oldest region and hosts the largest number of customers. Europe Central was introduced in 2021, while Asia Pacific became available in 2023.
NovaTech's primary goal is to provide developers with a single platform for deploying and operating cloud applications without requiring them to manage individual infrastructure components manually.

Page 2 — Compute Services
Compute Services
NovaCloud Compute provides three primary compute options: Virtual Machines, Container Clusters, and Serverless Functions.
Virtual Machines
NovaVM allows customers to create virtual machines with configurable CPU, memory, storage, and networking. Available machine families include General Purpose, Compute Optimized, Memory Optimized, and Storage Optimized. General Purpose machines are recommended for common web applications and APIs. Compute Optimized machines are designed for CPU-intensive workloads such as video processing and scientific calculations. Memory Optimized machines are intended for applications that maintain large datasets in memory. Storage Optimized machines are designed for workloads requiring high disk throughput.
Customers can resize virtual machines without rebuilding them. However, changing the machine family requires the VM to be stopped before resizing.
Container Clusters
NovaCluster provides managed Kubernetes clusters. Each cluster consists of a control plane and one or more worker node pools. NovaTech manages the Kubernetes control plane, while customers are responsible for configuring workloads and node pools.
A cluster can contain up to 500 worker nodes. Each node pool can contain between 1 and 100 nodes. NovaCluster supports automatic node scaling. The autoscaler increases the number of nodes when workloads cannot be scheduled because of insufficient resources. It decreases the node count when nodes remain underutilized for a sustained period.
Serverless Functions
NovaFunction allows developers to execute short-lived functions without managing servers. Functions can be triggered by HTTP requests, scheduled events, message queues, object-storage events, or database events.
The maximum execution time for a NovaFunction is 15 minutes. NovaFunction automatically scales based on incoming requests. Customers are charged based on execution duration and allocated memory. For latency-sensitive applications, NovaTech recommends keeping frequently executed functions small and avoiding unnecessary initialization work.

Page 3 — Data Services
Data Services
NovaCloud Data Services provide managed storage and database products.
NovaSQL
NovaSQL is a managed PostgreSQL-compatible relational database. Customers can create databases with between 1 and 128 virtual CPUs and up to 1 TB of memory. NovaSQL automatically performs backups every six hours. Backup retention can be configured between 7 and 35 days. Point-in-time recovery allows customers to restore a database to any supported timestamp within the configured retention period.
NovaDocument
NovaDocument is a managed MongoDB-compatible document database. It is designed for applications that store flexible JSON-like documents. NovaDocument automatically distributes documents across storage nodes. Unlike NovaSQL, NovaDocument does not provide relational joins.
NovaCache
NovaCache is a managed Redis-compatible caching service. It supports key-value caching, session storage, distributed locks, and pub/sub messaging. NovaCache data is stored in memory. Customers should not use NovaCache as the only persistent storage mechanism for critical business data.
NovaObject
NovaObject provides object storage for files, backups, media, and large datasets. Objects can be up to 5 TB in size. NovaObject provides three storage classes: Standard, Infrequent Access, and Archive. Standard storage is designed for frequently accessed data. Infrequent Access provides lower storage costs but higher retrieval charges. Archive provides the lowest storage cost and is intended for data that is rarely accessed. NovaObject supports versioning, lifecycle policies, encryption, and cross-region replication.

Page 4 — Application Services
Application Services
NovaCloud Application Services are designed to simplify application development.
NovaAPI
NovaAPI is a managed API gateway. It provides request routing, authentication, rate limiting, request validation, API versioning, and access logging. A single NovaAPI gateway can manage multiple backend services. NovaAPI supports REST and WebSocket APIs.
The default API rate limit is 1,000 requests per second per customer. Customers can request higher limits after completing a capacity review.
NovaQueue
NovaQueue is a managed message queue used for asynchronous communication between services. A queue can retain messages for up to 14 days. NovaQueue supports visibility timeouts. When a consumer receives a message, the message becomes temporarily invisible to other consumers. If the consumer fails to acknowledge the message before the visibility timeout expires, the message becomes available again.
The default visibility timeout is 30 seconds. NovaQueue supports dead-letter queues. Messages that repeatedly fail processing can be moved to a dead-letter queue for investigation.
NovaScheduler
NovaScheduler allows customers to execute jobs at specific times or intervals. Supported schedules include every minute, hourly, daily, weekly, and monthly. NovaScheduler uses UTC for schedule evaluation. For example, a job configured for 09:00 UTC executes at that UTC time regardless of the customer's local timezone.

Page 5 — Security Architecture
Security Architecture
Security is a core component of NovaCloud. NovaCloud uses a layered security model consisting of identity management, authorization, encryption, network controls, and auditing.
NovaIdentity
NovaIdentity provides authentication for users and services. It supports password authentication, multi-factor authentication, SSO, OAuth 2.0, and API credentials. Multi-factor authentication can use authenticator applications or hardware security keys.
Authorization
NovaCloud uses role-based access control. The three default roles are Viewer, Developer, and Administrator. Viewer can view resources and configuration but cannot modify them. Developer can create and modify application resources but cannot change organization-level security settings. Administrator has full access to the organization. Organizations can create custom roles with more granular permissions.
Encryption
Data stored in NovaCloud is encrypted at rest using AES-256. Data transmitted between services uses TLS 1.3 where supported. Customers can optionally provide their own encryption keys through NovaKey Management Service.
Audit Logs
NovaAudit records administrative and security-related events. Audit logs include user identity, timestamp, source IP, action, resource, and result. Audit logs are retained for 90 days by default. Enterprise customers can increase retention to up to seven years.

Page 6 — Networking
Networking
NovaCloud Networking allows customers to build isolated virtual networks. Each customer can create multiple NovaVPC networks. A NovaVPC can contain public subnets, private subnets, route tables, security groups, and network gateways.
Public subnets can communicate directly with the internet through an internet gateway. Private subnets do not accept inbound internet connections by default. Applications running in private subnets can access the internet through a managed NAT gateway.
Security Groups
Security groups provide stateful network filtering. Rules can control traffic based on protocol, port, source IP, and destination IP. Security groups are associated with compute resources.
Private Connectivity
NovaLink allows private communication between NovaCloud resources without using the public internet. NovaLink can connect resources across different NovaVPC networks. Cross-region NovaLink connections are supported but may incur additional network charges.
Load Balancing
NovaLoad provides managed load balancing and supports HTTP, HTTPS, and TCP. NovaLoad distributes incoming requests across healthy backend servers. Health checks are performed every 10 seconds by default. If a backend fails three consecutive health checks, NovaLoad removes it from active rotation. Once the backend passes two consecutive health checks, it can return to active traffic.

Page 7 — Observability
Observability
NovaCloud Observability provides centralized monitoring for applications and infrastructure. The platform consists of three primary components: NovaMetrics, NovaLogs, and NovaTrace.
NovaMetrics
NovaMetrics collects numerical measurements such as CPU utilization, memory usage, request count, and latency. Metrics are stored for 15 months. Customers can create alerts based on metric thresholds. For example, an organization can create an alert when CPU utilization remains above 80% for five consecutive minutes.
NovaLogs
NovaLogs collects application and infrastructure logs. Logs can be searched using fields such as timestamp, service, host, severity, and request ID. Logs are retained for 30 days by default. Enterprise customers can configure retention up to two years.
NovaTrace
NovaTrace provides distributed tracing. A trace represents an end-to-end request across multiple services. Each trace contains one or more spans. For example, an API request might contain spans for API Gateway, Authentication Service, Order Service, Database, and Payment Service. NovaTrace helps developers identify which service contributes the most latency to a request. Trace data is retained for 30 days.

Page 8 — Pricing and Limits
Pricing
NovaCloud uses usage-based pricing. Customers are billed monthly based on their consumption of compute, storage, networking, and managed services.
Compute Pricing
NovaVM pricing is based on CPU hours and memory allocation. NovaFunction pricing is based on execution duration and memory allocated. NovaCluster pricing includes a control-plane fee and the cost of worker nodes.
Storage Pricing
NovaObject Standard storage costs $0.023 per GB per month. Infrequent Access storage costs $0.012 per GB per month. Archive storage costs $0.004 per GB per month. Retrieving data from Archive storage may incur additional charges.
Network Pricing
Data transferred into NovaCloud is generally free. Data transferred out of NovaCloud is charged based on destination and volume. Cross-region data transfer is also charged.
Account Limits
A new NovaCloud account has the following default limits: NovaVM instances — 100; NovaCluster — 20; NovaVPC — 50; NovaObject buckets — 100; NovaAPI requests/sec — 1,000; NovaQueue queues — 200. Customers can request quota increases through the administration console. Quota increases are subject to capacity availability and security review.

Page 9 — Disaster Recovery and Reliability
Reliability
NovaCloud provides several mechanisms for improving application reliability.
Availability Zones
Each region contains multiple availability zones. Customers can distribute workloads across zones to reduce the impact of infrastructure failures. NovaTech recommends deploying production workloads across at least two availability zones.
Database Backups
NovaSQL performs automatic backups every six hours. Customers can configure backup retention from 7 to 35 days. Enterprise customers can additionally replicate backups to another region.
Cross-Region Replication
NovaObject supports asynchronous cross-region replication. Replication is not instantaneous. The replication delay depends on object size, network conditions, and destination-region capacity. NovaDocument also supports cross-region replication. NovaSQL supports cross-region read replicas but does not automatically promote a read replica during a regional outage.
Recovery Objectives
RPO (Recovery Point Objective) is the maximum acceptable amount of data loss measured in time. RTO (Recovery Time Objective) is the maximum acceptable time required to restore service. For example, an application with an RPO of 15 minutes should be designed so that no more than 15 minutes of data is lost during a disaster.
NovaCloud does not automatically guarantee a specific RPO or RTO for every service. Customers must select appropriate backup and replication configurations according to their requirements.

Page 10 — Case Study and Product Comparison
Acme Retail Case Study
Acme Retail is an online retailer processing approximately 50,000 orders per day. The company initially hosted its application on five NovaVM instances. As traffic increased, Acme experienced unpredictable latency during promotional events.
The engineering team migrated the application to NovaCluster. The new architecture consists of NovaLoad, NovaCluster, NovaSQL, NovaCache, NovaObject, and NovaMetrics.
NovaLoad distributes incoming requests across Kubernetes workloads. NovaCluster automatically scales worker nodes based on workload demand. NovaSQL stores customer and order information. NovaCache stores frequently accessed product information and user sessions. NovaObject stores product images and order exports. NovaMetrics monitors CPU usage, memory utilization, request latency, and error rates.
After migration, Acme configured workloads across three availability zones. The company also enabled NovaSQL backups with a 21-day retention period.
Service Comparison
NovaSQL uses a relational data model and is intended for transactions. NovaDocument uses a document data model for flexible documents. NovaCache uses a key-value model primarily for caching. NovaObject uses an object model for files.
Acme chose NovaSQL for transactional order data because the application requires relational queries and transactional consistency. NovaCache was selected for frequently accessed product data because the data can be regenerated from NovaSQL if the cache is lost. NovaObject was selected for product images because images are large binary objects rather than relational records.
"""

questions_eval = [
    {
        "id": "Q1",
        "category": "Direct fact",
        "question": "When was NovaTech Systems founded?",
        "expected": "NovaTech Systems was founded in 2018."
    },
    {
        "id": "Q2",
        "category": "Definition",
        "question": "What is the difference between RPO and RTO?",
        "expected": "RPO is the maximum acceptable amount of data loss measured in time, while RTO is the maximum acceptable time required to restore service."
    },
    {
        "id": "Q3",
        "category": "Multi-hop",
        "question": "Which services did Acme Retail use to store product images and frequently accessed product data, and why?",
        "expected": "Acme used NovaObject for product images because images are large binary objects, and NovaCache for frequently accessed product data because cached data can be regenerated from NovaSQL if the cache is lost."
    },
    {
        "id": "Q4",
        "category": "Numerical reasoning",
        "question": "What would be the monthly storage cost for 500 GB of NovaObject Standard storage, excluding other charges?",
        "expected": "500 * $0.023 = $11.50 per month."
    },
    {
        "id": "Q5",
        "category": "Comparison",
        "question": "How does NovaSQL differ from NovaDocument?",
        "expected": "NovaSQL is a PostgreSQL-compatible relational database supporting SQL and relational queries. NovaDocument is a MongoDB-compatible document database designed for flexible JSON-like documents and does not provide relational joins."
    },
    {
        "id": "Q6",
        "category": "Cross-section retrieval",
        "question": "What happens to a NovaLoad backend after three consecutive failed health checks, and what is required for it to return to active traffic?",
        "expected": "NovaLoad removes it from active rotation after three consecutive failed health checks. It can return after passing two consecutive health checks."
    },
    {
        "id": "Q7",
        "category": "Negative / absence",
        "question": "Does NovaFunction support executions longer than 15 minutes?",
        "expected": "No. The maximum NovaFunction execution time is 15 minutes."
    },
    {
        "id": "Q8",
        "category": "Conditional reasoning",
        "question": "If an application needs data to remain available after a regional failure, which NovaCloud capabilities could help?",
        "expected": "Cross-region replication can help, such as NovaObject or NovaDocument replication. Workloads can also be distributed across availability zones. NovaSQL can use cross-region read replicas, but they are not automatically promoted during a regional outage."
    },
    {
        "id": "Q9",
        "category": "Timeline",
        "question": "When were Europe Central and Asia Pacific introduced?",
        "expected": "Europe Central was introduced in 2021, and Asia Pacific was introduced in 2023."
    },
    {
        "id": "Q10",
        "category": "Scenario",
        "question": "A developer needs temporary high-speed session storage that should not be the only persistent copy of critical data. Which service should they use?",
        "expected": "NovaCache, because it provides Redis-compatible in-memory storage suitable for session storage, but it should not be the only persistent storage for critical business data."
    },
    {
        "id": "Q11",
        "category": "Aggregation",
        "question": "How many default NovaCloud account resource limits are listed in the pricing section?",
        "expected": "6 default limits (NovaVM instances 100, NovaCluster 20, NovaVPC 50, NovaObject buckets 100, NovaAPI requests/sec 1,000, NovaQueue queues 200)."
    },
    {
        "id": "Q12",
        "category": "Exact numeric retrieval",
        "question": "What is the default NovaQueue visibility timeout?",
        "expected": "30 seconds."
    },
    {
        "id": "Q13",
        "category": "Numerical reasoning",
        "question": "If a customer stores 2 TB of data in NovaObject Standard storage, what is the approximate monthly storage cost?",
        "expected": "2,000 GB * $0.023 = $46 per month."
    },
    {
        "id": "Q14",
        "category": "Cross-page reasoning",
        "question": "Why would Acme Retail use NovaCache instead of NovaSQL for frequently accessed product information?",
        "expected": "NovaCache is an in-memory Redis-compatible cache designed for fast access. Cached data can be regenerated from NovaSQL if the cache is lost."
    },
    {
        "id": "Q15",
        "category": "Distractor test",
        "question": "Does NovaCache provide persistent storage for critical business data?",
        "expected": "No. It is in-memory and should not be the only persistent storage for critical business data."
    },
    {
        "id": "Q16",
        "category": "List retrieval",
        "question": "What are the five major NovaCloud product areas?",
        "expected": "Compute Services, Data Services, Application Services, Security Services, and Observability Services."
    },
    {
        "id": "Q17",
        "category": "Relationship",
        "question": "What happens when a NovaLoad backend fails health checks?",
        "expected": "Health checks run every 10 seconds. After three consecutive failures, the backend is removed from active traffic. After two consecutive successful checks, it can return."
    },
    {
        "id": "Q18",
        "category": "Contradiction / precision",
        "question": "Does NovaCloud automatically guarantee an RPO of 15 minutes for all applications?",
        "expected": "No. NovaCloud does not automatically guarantee a specific RPO or RTO for every service."
    },
    {
        "id": "Q19",
        "category": "Long-context retrieval",
        "question": "What observability tools are available, what does each collect, and how long is the data retained?",
        "expected": "NovaMetrics collects numerical measurements and retains them 15 months. NovaLogs collects logs and retains them 30 days by default, up to two years for Enterprise. NovaTrace collects distributed traces and retains them 30 days."
    },
    {
        "id": "Q20",
        "category": "Complex scenario",
        "question": "Acme needs load balancing, automatic scaling, transactional data, caching, file storage, and monitoring. Which services should it use?",
        "expected": "NovaLoad, NovaCluster, NovaSQL, NovaCache, NovaObject, and NovaMetrics respectively."
    }
]

def main():
    doc_id = "novacloud_eval_doc"
    filename = "NovaCloud_RAG_Evaluation_Document.txt"
    print("--- 1. Indexing NovaCloud document into Vector Store ---")
    spans = chunk_text_with_spans(novacloud_text)
    chunks = []
    for idx, item in enumerate(spans):
        chunks.append({
            "id": f"{doc_id}_chunk_{idx}",
            "doc_id": doc_id,
            "filename": filename,
            "chunk_index": idx,
            "content": item["content"],
            "start_char": item["start_char"],
            "end_char": item["end_char"],
            "full_text": novacloud_text
        })
    texts = [c["content"] for c in chunks]
    embeddings = hybrid_retriever_service.embedding_model.encode(texts).tolist()
    vector_store_service.add_chunks(
        doc_id=doc_id,
        filename=filename,
        chunks=chunks,
        embeddings=embeddings,
        file_size=len(novacloud_text.encode('utf-8')),
        upload_time=datetime.datetime.now().isoformat()
    )
    hybrid_retriever_service.build_bm25_index()
    print(f"Indexed {len(chunks)} chunks into Vector Store & BM25 index.")

    print("\n--- 2. Running 20 Evaluation Questions against AdaptiveRAGAgent ---")
    from app.agents.budgets import AgentBudgets
    agent = AdaptiveRAGAgent(budgets=AgentBudgets(max_wall_clock_seconds=45.0))
    eval_results = []

    for idx, q_item in enumerate(questions_eval, 1):
        q_id = q_item["id"]
        cat = q_item["category"]
        question = q_item["question"]
        expected = q_item["expected"]

        print(f"\n[{idx}/20] Evaluating {q_id} ({cat}): '{question}'")
        state = agent.run(question=question, document_id=doc_id, question_id=f"novacloud_{q_id}")
        
        generated_answer = state.final_answer or ""
        eval_metrics = evaluate_answer(generated_answer, expected, question_type=cat)

        res = {
            "id": q_id,
            "category": cat,
            "question": question,
            "expected": expected,
            "generated": generated_answer,
            "passed": eval_metrics["passed"],
            "score": eval_metrics["score"],
            "reason": eval_metrics["reason"],
            "steps": [s.action for s in state.trace],
            "evidence_count": len(state.retrieved_evidence)
        }
        eval_results.append(res)
        status = "PASSED" if res["passed"] else "FAILED"
        print(f"Result: {status} (Score: {res['score']})", flush=True)
        print(f"Generated Answer: {generated_answer[:150]}...", flush=True)

    print("\n================ EVALUATION SUMMARY ================", flush=True)
    passed_count = sum(1 for r in eval_results if r["passed"])
    failed_count = len(eval_results) - passed_count
    print(f"Total Questions: {len(eval_results)}", flush=True)
    print(f"Passed: {passed_count} ({passed_count/len(eval_results)*100:.1f}%)", flush=True)
    print(f"Failed: {failed_count} ({failed_count/len(eval_results)*100:.1f}%)", flush=True)

    # Save output to JSON file for detailed breakdown
    out_path = os.path.join(os.path.dirname(__file__), "novacloud_eval_results.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(eval_results, f, indent=2)
    print(f"\nDetailed evaluation results written to: {out_path}")

if __name__ == "__main__":
    main()
