# Post Deployment Researcher Trial Plan

## 1. Trial Goal

After server deployment, use 2025 data to verify that researchers can complete:

```text
API data access -> local research -> weights package -> upload backtest -> Dashboard -> result zip -> conclusion
```

The trial validates platform usability, not a single strategy's investment
quality.

## 2. Trial Participants

- 1 Python-capable researcher
- 1 junior researcher or intern
- 1 AI agent operator, optional

## 3. Trial Tasks

Task 1: Run demo weights package.

Task 2: Run the VIX Q5 pilot package as an acceptance sample.

Task 3: Build one simple 20-day momentum Top 20 equal-weight strategy:

- fetch or prepare 2025 data
- compute 20-day momentum
- select top 20 names
- create long-only equal weights
- build Strategy Package
- upload to platform
- inspect Dashboard
- download result zip

## 4. Submission Requirements

Each participant submits:

- `strategy_package.zip`
- result zip
- short research note
- list of issues encountered

Do not submit API tokens, raw platform data, or unauthorized downloaded data.

## 5. Feedback Form

Questions:

- Is the API easy to use?
- Is the documentation understandable?
- Is the template structure clear?
- Can package errors be diagnosed?
- Can Dashboard metrics be explained?
- Is result zip sufficient?
- Which step was most confusing?
- Did the data policy feel clear?

## 6. Success Criteria

- At least 1 person independently completes the full workflow.
- At least 1 custom strategy uploads and backtests successfully.
- All failures can be traced to a clear cause.
- Data usage policy is read and acknowledged.
- No data is shared outside authorized channels.
