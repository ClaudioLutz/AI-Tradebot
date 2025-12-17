# Story 006: Main Orchestration Stories

This directory contains user stories for **Epic 006: Main Orchestration Script (Multi-Asset)**.

## Epic Overview
Create the `main.py` orchestrator script that ties together all modules into a cohesive trading bot workflow with support for multi-asset trading hours.

## Stories

### [Story 006-001: Command-Line Arguments and Initialization](./story-006-001-command-line-arguments-initialization.md)
Setup argument parsing, logging configuration, and main entry point structure.

### [Story 006-002: Configuration and Client Initialization](./story-006-002-configuration-client-initialization.md)
Implement configuration loading and Saxo client initialization at startup.

### [Story 006-003: Trading Hours Logic](./story-006-003-trading-hours-logic.md)
Implement trading hours validation logic supporting multiple modes (always, fixed, instrument).

### [Story 006-004: Single Trading Cycle Implementation](./story-006-004-single-trading-cycle.md)
Implement the core trading cycle logic that orchestrates data fetching, signal generation, and execution.

### [Story 006-005: Main Loop and Continuous Operation](./story-006-005-main-loop-continuous-operation.md)
Implement the main loop for continuous operation with configurable cycle intervals.

### [Story 006-006: Error Handling and Graceful Shutdown](./story-006-006-error-handling-graceful-shutdown.md)
Implement comprehensive error handling, recovery logic, and graceful shutdown procedures.

### [Story 006-007: Integration Testing](./story-006-007-integration-testing.md)
Create end-to-end integration tests validating the complete orchestration workflow.

### [Story 006-008: Developer Documentation](./story-006-008-developer-documentation.md)
Create comprehensive documentation for running and operating the trading bot.

## Dependencies
- Epic 001-2: Saxo Bank Migration
- Epic 002: Configuration Module
- Epic 003: Market Data Retrieval
- Epic 004: Trading Strategy System
- Epic 005: Trade Execution Module

## Related Documents
- [Epic 006: Main Orchestration](../../epics/epic-006-main-orchestration.md)
- [EPICS_OVERVIEW.md](../../epics/EPICS_OVERVIEW.md)
