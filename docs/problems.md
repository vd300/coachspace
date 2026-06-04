# Problems Faced During Development

This document tracks problems found during AI-assisted development so they are not repeated.

For every problem, document:

- what went wrong
- why it was a problem
- what decision was made
- what rule should be followed next time
- how Codex or any AI coding tool should behave in the future

Codex should read this file before making major code changes.

---

# Problem 1: Backend Code Generated Entirely Inside `main.py`

## What happened

During the initial backend implementation of the Coaching App, Codex placed most of the backend code inside a single `main.py` file.

This included:

- FastAPI app setup
- API routes
- request and response schemas
- database models
- business logic
- validation logic
- helper functions
- configuration logic

As a result, `main.py` became responsible for almost the entire backend.

---

## Why this was a problem

Keeping everything inside `main.py` may work for a small prototype, but it becomes difficult to maintain as the project grows.

Main issues:

- Hard to understand where code belongs
- Hard to add new features safely
- Hard to test business logic independently
- Easy to create duplicate models, schemas, or logic
- Higher chance that Codex adds code in the wrong place
- Poor separation between routes, database logic, and business rules

For example, route handlers should not contain all business and database logic.

Bad pattern:

```python
@app.post("/bookings")
def create_booking():
    # validate request
    # check coach availability
    # create booking
    # save to database
    # return response