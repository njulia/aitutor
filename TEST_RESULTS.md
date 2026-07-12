# Validation results

Validated on 11 July 2026.

```text
DEV_MODE=true pytest -q
21 passed

python -m compileall -q web_app.py src scripts
passed

node --check static/js/app.js
passed

node --check static/js/chart-lite.js
passed

DEV_MODE=true python -c "import web_app"
95 routes loaded
```

A fresh-database integration check also covered registration, parent account creation, default learner creation, memory enable/read, logout, complete account erasure and failed login after erasure.
