# TikTok Feishu Radar - Architecture Review Report

**Date:** 2026-03-21  
**Participants:** Monoko, Lain  
**Status:** Post-implementation review, pre-refactoring

---

## Executive Summary

This report documents key architectural insights from a review of the TikTok Feishu Radar pipeline. The goal is to capture lessons for future projects while establishing a plan to incrementally improve the current codebase.

---

## 1. Core Insights

### 1.1 Paradigm: OOP vs Functional

**Finding:** The "OOP vs functional" debate is a false dichotomy. What matters is **data flow and boundaries**.

**Linux Kernel Model (The Gold Standard):**
```c
// OOP without classes - structs with function pointers
struct file_operations {
    ssize_t (*read)  (struct file *, char *, size_t, loff_t *);
    ssize_t (*write) (struct file *, const char *, size_t, loff_t *);
    int (*open)      (struct inode *, struct file *);
};
```

**Key Principles:**
- **Explicit interfaces** over implicit behavior
- **Composition** over inheritance
- **State is visible** (structs), not hidden (private fields)
- **Operations are replaceable** (function pointers)

**Application to Our Project:**
- Current scraper class mixes concerns (fetch + filter + save)
- Better: Separate `fetch()`, `filter()`, `save()` as composable units
- The class is fine, but methods should be independently testable

### 1.2 Multi-Language Architecture

**Finding:** Using multiple languages is correct when each solves a specific problem well.

| Component | Language | Justification |
|-----------|----------|---------------|
| Scrapers | Node.js | Apify SDK is Node-first; async I/O fits |
| AI Analysis | Python | Ecosystem (anthropic, requests) |
| Workflow | Shell | Process orchestration, environment setup |

**The Real Issue:** Interface contracts, not language count.

Our `filtered-result.json` serves as the contract between Node and Python. This is acceptable, but should be documented (schema).

### 1.3 Shell Script Responsibility

**Finding:** Shell should do **workflow**, not logic.

**Current State (300+ lines):**
- Retry logic in bash
- Validation in bash
- Error handling in bash

**Target State (thin shell):**
```bash
#!/bin/bash
set -e

python3 stage1_update_prompt.py
node scraper.js  
python3 phase2_analyze.py  # retries happen here
python3 phase3_push.py
```

**Principle:** If it needs data transformation, it's Python. If it's "run this, then that", it's shell.

### 1.4 Scalability Through Layering

**Linux Model:**
```
User Space → System Calls → VFS → Filesystem Driver → Block Device
     ↑            ↑          ↑           ↑               ↑
   Programs    Table lookup  Structs    Function ptrs   Hardware
```

Each layer:
1. **Doesn't know** about layers above it
2. **Only uses** the interface of layers below it
3. **Can be replaced** without changing other layers

**Our Pipeline Should Mirror This:**
```
run_pipeline.sh → scraper.js → filtered-result.json → analyze.py → report.json → push.py
      ↑               ↑                ↑                    ↑              ↑
   Workflow       Fetch/Filter      Data contract       AI analysis    Output
```

---

## 2. Current Pain Points

### 2.1 Database Removal (Resolved)

**Issue:** SQLite added complexity with no value.  
**Action:** Removed `better-sqlite3` from both scrapers.  
**Lesson:** Don't add storage until you measure you need it.

### 2.2 Virtual Environment Corruption (Resolved)

**Issue:** `pydantic-core` native module failed (ARM64 vs Intel mismatch).  
**Action:** Recreated `.venv` with correct platform wheels.  
**Lesson:** Native dependencies are fragile; avoid when possible.

### 2.3 Shell Script Complexity (Pending)

**Issue:** `run_pipeline.sh` does too much logic.  
**Impact:** Hard to test, hard to modify, retry logic scattered.  
**Status:** Accepted for now, flagged for future refactoring.

### 2.4 Testing (Not Addressed)

**Issue:** No unit tests for scrapers or AI logic.  
**Blocker:** Requires API keys to run.  
**Future Solution:** Interface-based mocking (see Linux model).

---

## 3. Architectural Recommendations

### 3.1 For This Project (Incremental)

**Priority 1: Keep Working**
- Pipeline is functional and shipping
- Do not refactor for purity

**Priority 2: Isolate Changes**
- When modifying scraper, extract `fetch()`/`filter()`/`save()`
- Keep JSON interface contracts stable
- Add schema documentation for `filtered-result.json`

**Priority 3: Shell Diet**
- Move retry logic into Python (where API calls happen)
- Move validation into Python (where data lives)
- Shell becomes: setup → run → check exit code

### 3.2 For Future Projects

**Design Checklist:**

1. **Can I test this without API keys?**
   - If no → you need interface boundaries (like Linux's VFS)

2. **Can I swap the implementation?**
   - If no → you have hidden coupling

3. **Does the shell script fit on one screen?**
   - If no → logic has leaked into orchestration

4. **Is there exactly one way to run this?**
   - If no → environment setup is too complex

**Pattern: Data Flow Architecture**
```
Input → Transform A → Transform B → Output
  ↑          ↑            ↑           ↓
Config   Pure function   Pure function  Side effect
```

Each transform:
- Takes explicit input
- Returns explicit output
- Has no hidden dependencies
- Can be unit tested with mock data

---

## 4. Concrete Next Steps

### Immediate (No Code Changes)
1. ✅ Document JSON schema for `filtered-result.json`
2. ✅ Add `.env.example` to repo (already done)
3. ✅ Remove SQLite (completed 2026-03-21)

### Short-term (Next 2-4 Weeks)
1. Move Phase 2 retry logic from shell to Python
2. Extract `filter()` function in scraper (testable independently)
3. Add validation schema for AI API responses

### Medium-term (Next 2-3 Months)
1. Create `test_data/` with sample JSON fixtures
2. Add unit tests for `filter()` and `transform()` functions
3. Document the API contract between phases

### Long-term (If Project Grows)
1. Consider a single orchestration language (Python)
2. Add proper observability (structured logging)
3. Separate "fetch" from "transform" services if scale demands

---

## 5. Key Principles Summary

| Principle | Current | Target |
|-----------|---------|--------|
| **Explicit over implicit** | Database hidden in class | JSON files visible |
| **Shell does workflow** | 300+ lines of logic | <50 lines of sequence |
| **Python does logic** | Logic scattered | Retries, validation in Python |
| **Interfaces over implementations** | Class with mixed concerns | Separate fetch/filter/save |
| **Working over perfect** | It ships | Keep shipping, improve incrementally |

---

## 6. References

- [The Linux Programming Interface](https://man7.org/tlpi/) - Michael Kerrisk
- [Linus on "good taste"](https://lwn.net/Articles/193794/) - Removing code is better than adding
- [The Unix Philosophy](https://en.wikipedia.org/wiki/Unix_philosophy) - Do one thing well

---

**Next Action:** Review this report, then begin Phase 2 retry logic migration from shell to Python.

**Report Status:** Draft for discussion  
**Last Updated:** 2026-03-21 11:10 Asia/Hong_Kong
