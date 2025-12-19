# nus_cma_project

This is the code of NUS CMA project for Container Maritime Alliance (CMA) optimization research.

## System Overview

**11-Rank Vessel System** ✅ (Migration completed November 14, 2025)

The CMA optimization system supports comprehensive liner shipping network design with:

- **Vessel Fleet:** 11 vessel ranks (300-15,199 TEU capacity range)
  - Rank 1-9: Original fleet classes
  - **Rank 10:** 10,000-12,499 TEU (new)
  - **Rank 11:** 12,500-15,199 TEU (new)
  
- **Speed Optimization:** 18 speed levels (10.0-18.5 knots, 0.5 knot increments)
  - Enhanced precision for cost/speed trade-offs
  - Comprehensive fuel consumption data across all speeds
  
- **Port Network:** 182 global ports with hybrid operational data
  - 56 CNC Enhanced Ports: Complete operational details (productivity, costs, waiting times, maneuvering)
  - 126 Legacy Ports: Global coverage fallback
  
- **Service Lines:** Real-world validation baselines
  - 34 CNC proforma service lines
  - ~50-100 legacy current lines
  
- **Demand Modeling:** Day-of-week demand patterns (7 matrices + total)

## Core Functionality

The system provides comprehensive optimization capabilities:

- **Cost Minimization:** `fulfill_demands()` - Multi-commodity network flow optimization
- **Week Prediction:** `fulfill_demands_2()` - Rolling horizon planning
- **MCTS Search:** `MonteCarloTree` - Service line network construction
- **Visualization:** Route plotting, network diagrams, performance charts

## Validation Status

**Comprehensive Testing:** 129 tests passing (100%)

- 11 Integration tests (data loading, fulfill_demands)
- 18 Notebook validation tests
- 20 Proforma validation tests
- 18 Waiting times tests
- 27 Fuel consumption tests
- 26 Port call costs tests
- 9 Data loading tests

**System Verification:** All existing features working correctly with enhanced data sources.

## Documentation

Examples:

- [A Smaller Network - Southeastern Asia](./src/example_southeasternAsia.ipynb)
- [Compared to Benchmark Model (LINERLIB)](./src/test_benchmarks.ipynb)
- [Data Loading and Validation](./src/test_data.ipynb) - Updated for 11-rank system
- [MCTS Demonstration](./src/test_mcts.ipynb)
- [Visualization Examples](./src/test_visulization.ipynb)

Reports:

- [Main report](./docs/_Report.md)
- [Data Ingestion Documentation](./docs/Data_Ingestion_Documentation.md) - Comprehensive data source guide
  - **Section 12:** Complete migration summary and validation results
- [MILP Formulations](./docs/MILP_Formulations.md) - Mathematical formulation documentation
- [Literature review](./docs/_Literature_Review.md)

## Data Sources

**Primary (Enhanced CNC Operational Data):**
- `src/cma/res/input/` - Enhanced operational data (vessel classes, port operations, proforma lines)

**Secondary (Legacy Global Coverage):**
- `src/cma/res/data_2024-12-23/` - Full distance matrix, day-of-week demand patterns

**Benchmark Data:**
- `src/LINERLIB/` - Industry benchmark instances for validation

For complete data source documentation, see [Data Ingestion Documentation](./docs/Data_Ingestion_Documentation.md).

## Project Status

**Current Status:** ✅ 11-Rank System Migration COMPLETE (18/18 tasks)

See [Milestones](./docs/_todo-list.md) for development history and completed tasks.

## To Do

- [Milestones](./docs/_todo-list.md)

