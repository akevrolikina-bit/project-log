# Jira Time Log Checker — Product Strategy

## Vision

A web application that transforms the monthly time-logging review from 4–8 hours of manual work into a manageable process taking 30–60 minutes. Initially runs locally; cloud deployment planned for the future.

## Problem

Every month, a team lead manually:
- Exports data from Jira
- Cross-checks worklogs against the production calendar
- Verifies that time is logged to permitted tasks
- Reads comments and evaluates their adequacy
- Prepares feedback for team members
- Calculates project distribution for management

All of this is done manually in Excel, for 10–20 people across 3 countries. Takes half a day to a full day.

## Target Users

- **Primary:** accounting team lead
- **Future:** other team leads, each reviewing their own team
- All users authenticate (login/password)

## Development Phases

### Phase 1 — MVP

- Fetch worklogs from Jira API (for an arbitrary period)
- Fetch tasks by filter (region + project)
- Load rules from Google Docs (task list, reconciliation rules)
- Automated checks: permitted tasks + production calendar (RU/KZ/BY)
- Generate Excel (separate sheet per employee)
- Summary report by projects and regions (for management)
- User authentication

### Phase 2 — Smart Review

- AI-powered comment review (traffic light: green/yellow/red)
- Manual review interface for questionable comments
- Manual allocation of % for "shared" tasks across projects

### Phase 3 — Maturity

- Tracking time spent on the review process itself
- Review history (month-to-month trends)
- Notifications and reminders

## Data Sources

| Source | What we fetch | Access |
|--------|--------------|--------|
| Jira Server API | Employee worklogs for a period | Personal Access Token (read-only) |
| Jira Server API | Tasks by filter (region + project) | Personal Access Token (read-only) |
| Google Docs API | Permitted/prohibited task list + rules | OAuth (read-only) |

## Key Parameters

| Parameter | Value |
|-----------|-------|
| Deployment | Local (Phase 1), cloud (later) |
| Review period | Arbitrary (any date range) |
| Calendars | 3 countries: Russia, Kazakhstan, Belarus |
| Scale | 10–20+ employees per team lead |
| Output document | Excel (one sheet per employee) |
| Summary report | Time distribution by projects and regions |

## Product Principles

- **Iterative** — MVP first, then add features as needed
- **Read-only from Jira** — the app never modifies anything, only reads
- **Rules in Google Docs** — updated by multiple leads, the app fetches automatically
- **Output is Excel** — one file that can be forwarded to the team
- **Local at launch** — runs on a computer, can be moved to the cloud later
- **Team separation** — each lead sees and reviews only their own team

## Workflow (MVP)

```
INPUT DATA
├── Jira API: employee worklogs
├── Jira API: tasks by filter (region + project)
├── Google Docs: permitted tasks + rules
└── Settings: employees + calendars + period
        │
        ▼
AUTOMATED CHECKS
├── Is the task on the permitted list?
└── Hours = working days per country calendar?
        │
        ▼
OUTPUT
├── Excel — errors (one sheet per employee)
└── Summary — time by projects and regions
```
