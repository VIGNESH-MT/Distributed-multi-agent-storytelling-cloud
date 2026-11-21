# Distributed Multi-Agent Storytelling Cloud

Consistency-aware distributed multi-agent storytelling system deployed on a private K3s cloud.

Research implementation for CO4219/CO7219.

## Research question

How do agent coordination and shared-state consistency mechanisms affect narrative coherence, throughput, latency and fault tolerance in a distributed multi-agent storytelling system?

## Research principles

- Reproducible dependency management
- Independently deployed agent services
- Explicit orchestration state transitions
- Transactional shared-state updates
- Observable and auditable execution
- Repeatable experimental workloads
- Evidence-based evaluation

## Infrastructure

- Ubuntu 24.04
- Multipass
- K3s
- Buildah
- PostgreSQL

## Application

- Python
- FastAPI
- LangGraph

## Current implementation status

The two-node K3s infrastructure foundation has been established. PostgreSQL has been deployed with persistent storage, and persistence across a PostgreSQL pod replacement has been verified.

The FastAPI application currently provides an initial health-check endpoint. Multi-agent orchestration, distributed agent deployment, consistency experiments and performance evaluation remain under development.

## Repository structure

- `app/` — application source code
- `requirements.in` — direct Python dependencies
- `requirements.lock` — resolved dependency lock file
- `VERSION` — project version

## Research and evaluation

The project will evaluate coordination and shared-state consistency mechanisms using repeatable workloads and measurements of narrative coherence, throughput, latency, conflict handling and fault tolerance.
