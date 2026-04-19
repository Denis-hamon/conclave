"""
conclave/benchmark_tasks.py

20 canonical tasks used to compare Haiku vs Sonnet vs Conclave routing.
"""
from __future__ import annotations

BENCHMARK_TASKS: list[dict] = [
    # --- Repetitive --------------------------------------------------------
    {"id": "write_ticket", "role": "TechLead", "category": "repetitive",
     "input": "Write a Jira ticket for adding rate limiting to the payments API."},
    {"id": "format_report", "role": "Analyst", "category": "repetitive",
     "input": "Format this JSON as a markdown table: "
              "{\"q1\": 120, \"q2\": 145, \"q3\": 160, \"q4\": 180}"},
    {"id": "weekly_summary", "role": "TechLead", "category": "repetitive",
     "input": "Write a weekly summary for the CPO from these bullets: "
              "- shipped feature flag service - onboarded new QA engineer - 2 P1 incidents resolved"},
    {"id": "stakeholder_email", "role": "CPO", "category": "repetitive",
     "input": "Draft a short email to the CTO explaining a 2-week delay on the checkout feature "
              "due to payment-service v3 not being in staging."},
    {"id": "test_plan_template", "role": "QA_Engineer", "category": "repetitive",
     "input": "Generate a test plan template for an OAuth2 login flow."},

    # --- Operational -------------------------------------------------------
    {"id": "ticket_triage", "role": "TechLead", "category": "operational",
     "input": "Triage these 5 bug reports and assign priority (P0-P3): "
              "(1) login fails on Safari, (2) typo in onboarding, (3) 500 on /checkout spikes at peak, "
              "(4) slow dashboard load, (5) wrong currency shown in EU."},
    {"id": "spec_review", "role": "TechLead", "category": "operational",
     "input": "Review this API spec and flag any missing error codes: "
              "POST /orders, returns 201 on success."},
    {"id": "dependency_check", "role": "TechLead", "category": "operational",
     "input": "List the dependencies and blockers for shipping an idempotent checkout endpoint "
              "that depends on payment-service and inventory-service."},
    {"id": "meeting_notes", "role": "CPO", "category": "operational",
     "input": "Summarize these meeting notes into decisions and action items: "
              "We agreed to postpone the mobile launch to Q3, to invest in shared components, "
              "and to hire a designer."},
    {"id": "risk_assessment", "role": "TechLead", "category": "operational",
     "input": "Identify the top 5 risks in a monorepo migration from polyrepo."},

    # --- Technical ---------------------------------------------------------
    {"id": "architecture_review", "role": "TechLead", "category": "technical",
     "input": "Review this microservices architecture and flag scalability issues: "
              "10 services sharing a single Postgres instance, no read replicas, "
              "synchronous service-to-service HTTP."},
    {"id": "security_audit", "role": "QA_Engineer", "category": "technical",
     "input": "Audit a JWT-based auth flow for OWASP Top 10 vulnerabilities."},
    {"id": "api_design", "role": "TechLead", "category": "technical",
     "input": "Design a REST API for a multi-tenant billing system. Specify endpoints, "
              "resource model, and tenancy isolation strategy."},
    {"id": "code_review", "role": "TechLead", "category": "technical",
     "input": "Review this Python function for correctness and performance: "
              "def dedupe(xs): return [x for i, x in enumerate(xs) if x not in xs[:i]]"},
    {"id": "database_schema", "role": "TechLead", "category": "technical",
     "input": "Design a database schema for an e-commerce order system with "
              "customers, orders, line_items, payments, and refunds."},

    # --- Strategic ---------------------------------------------------------
    {"id": "define_strategy", "role": "CPO", "category": "strategic",
     "input": "Define our Q3 product strategy given these signals: 2 competitors launched AI "
              "features, churn up 8% in enterprise tier, new mobile SDK launched by platform."},
    {"id": "prioritization", "role": "CPO", "category": "strategic",
     "input": "Prioritize these 8 features using RICE: mobile login, SSO, audit log, "
              "dashboard v2, api v3, localization, offline mode, dark mode."},
    {"id": "competitive_analysis", "role": "CPO", "category": "strategic",
     "input": "Analyze how we should respond to a competitor's new AI-assistant feature "
              "that overlaps 70% with our roadmap."},
    {"id": "okr_definition", "role": "CPO", "category": "strategic",
     "input": "Define quarterly OKRs for the product team, balancing growth, retention, "
              "and platform reliability."},
    {"id": "postmortem", "role": "TechLead", "category": "strategic",
     "input": "Write a postmortem for a 45-minute checkout outage caused by a database "
              "connection pool exhaustion during a Black Friday traffic spike."},
]

BENCHMARK_CATEGORIES = ["repetitive", "operational", "technical", "strategic"]
