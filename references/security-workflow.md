# Security Workflow — /autoresearch-security

Autonomous security auditing that uses the autoresearch loop to iteratively discover, validate, and report vulnerabilities. Combines STRIDE threat modeling, OWASP Top 10 sweeps, and red-team adversarial analysis into a single autonomous loop.

**Output:** A severity-ranked security report with threat model, findings, mitigations, and iteration log.

## Trigger

- User invokes `/autoresearch-security`
- User says "security audit", "run a security sweep", "threat model this codebase", "find vulnerabilities"
- User says "red-team this app", "OWASP audit", "STRIDE analysis"

## Loop Support

Works with both unbounded and bounded modes:

```
# Unlimited -- keep finding vulnerabilities until interrupted
/autoresearch-security

# Bounded -- run exactly N security sweep iterations
/loop 10 /autoresearch-security

# With target scope
/autoresearch-security
Scope: src/api/**/*.ts, src/middleware/**/*.ts
Focus: authentication and authorization flows
```

## Architecture

```
SETUP PHASE (once):
  1. Scan codebase -> identify tech stack, frameworks, APIs
  2. Map assets -> data stores, auth, external services
  3. Identify trust boundaries -> client/server, API/DB
  4. Generate STRIDE threat model
  5. Build attack surface map
  6. Create security-audit-results.tsv log
  7. Establish baseline (count known issues)

AUTONOMOUS LOOP:
  Each iteration: pick ONE attack vector from the threat
  model, attempt to find/validate the vulnerability,
  log the result, move to next vector.

  LOOP (FOREVER or N times):
    1. Review: threat model + past findings + results log
    2. Select: pick next untested attack vector
    3. Analyze: deep-dive into target code for the vector
    4. Validate: construct proof (code path, input, output)
    5. Classify: severity + OWASP category + STRIDE category
    6. Log: append to results log
    7. Repeat
```

## Persona Composition

Adopt the `persona-security-expert` skill's mindset for all analysis in this audit. Reference that skill for the full OWASP Top 10 checklist and STRIDE threat modeling methodology. Do not duplicate those checklists — compose with the existing persona.

## Setup Phase — Threat Model Generation

### Step 1: Codebase Reconnaissance

Scan the project to build context:

```
READ:
  - package.json / requirements.txt / go.mod (dependencies)
  - .env.example / config files (secrets handling)
  - Dockerfile / docker-compose.yml (infrastructure)
  - API route files (attack surface)
  - Auth/middleware files (trust boundaries)
  - Database schemas/models (data assets)
  - CI/CD configs (supply chain)
```

### Step 2: Asset Identification

Catalog every asset that has security relevance:

| Asset Type | Examples | Priority |
|------------|----------|----------|
| **Data stores** | Database, Redis, file storage, cookies, localStorage | Critical |
| **Authentication** | Login, OAuth, JWT, sessions, API keys | Critical |
| **API endpoints** | REST routes, GraphQL resolvers, webhooks | High |
| **External services** | Payment APIs, email providers, CDN, analytics | High |
| **User input surfaces** | Forms, URL params, headers, file uploads | High |
| **Configuration** | Environment variables, feature flags, CORS settings | Medium |
| **Static assets** | Public files, uploaded content, generated files | Low |

### Step 3: Trust Boundary Mapping

Identify where trust levels change:

```
Trust Boundaries:
  - Browser <-> Server (client-side vs server-side)
  - Server <-> Database (application vs data layer)
  - Server <-> External APIs (internal vs third-party)
  - Public routes <-> Authenticated routes
  - User role <-> Admin role (privilege levels)
  - CI/CD <-> Production (deployment boundary)
  - Container <-> Host (infrastructure boundary)
```

### Step 4: STRIDE Threat Model

For each asset + trust boundary combination, analyze threats using STRIDE:

| Threat | Question | Example Findings |
|--------|----------|------------------|
| **S**poofing | Can an attacker impersonate a user/service? | Weak auth, missing CSRF, forged JWTs |
| **T**ampering | Can data be modified in transit or at rest? | Missing input validation, SQL injection, prototype pollution |
| **R**epudiation | Can actions be denied without evidence? | Missing audit logs, unsigned transactions |
| **I**nformation Disclosure | Can sensitive data leak? | Error messages expose internals, PII in logs, debug endpoints |
| **D**enial of Service | Can the service be disrupted? | Missing rate limiting, regex DoS, resource exhaustion |
| **E**levation of Privilege | Can a user gain unauthorized access? | IDOR, broken access control, path traversal |

Output the threat model as a structured table in the security report.

### Step 5: Attack Surface Map

Generate an attack surface map showing:

```
Attack Surface:
  Entry Points
    GET /api/users/:id          -> IDOR risk (user enumeration)
    POST /api/auth/login        -> Brute force, credential stuffing
    POST /api/upload            -> File upload, path traversal
    WebSocket /ws               -> Auth bypass, injection
    Webhook /api/webhooks/*     -> Signature verification
  Data Flows
    User input -> DB query       -> Injection risk
    JWT -> route handler          -> Token validation
    File upload -> storage        -> Malicious file execution
  Abuse Paths
    Rate limit bypass -> account takeover
    IDOR chain -> data exfiltration
    SSRF -> internal service access
```

### Step 6: Baseline

Count existing security issues before the loop starts:
- Run any existing security linting (`npm audit`, `eslint-plugin-security`, `bandit`, etc.)
- Count issues as baseline metric
- Record in results log as iteration #0

## The Security Loop

### Iteration Protocol

Each iteration follows the autoresearch pattern but adapted for security:

#### Phase 1: Review (Select Attack Vector)

Priority order for selecting the next vector to test:

1. **Critical STRIDE threats** not yet tested
2. **OWASP Top 10 categories** not yet covered
3. **High-severity attack paths** from the surface map
4. **Dependency vulnerabilities** (supply chain)
5. **Configuration weaknesses** (headers, CORS, CSP)
6. **Business logic flaws** (race conditions, state manipulation)
7. **Information disclosure** (error handling, debug modes)

Track coverage in the results log. The goal is comprehensive coverage.

#### Phase 2: Analyze (Deep Dive)

For the selected vector:
1. Read all relevant code files
2. Trace data flow from entry point to data store
3. Identify missing validation, sanitization, or access checks
4. Look for known vulnerability patterns

#### Phase 3: Validate (Proof Construction)

For each potential finding, construct proof:

```
Finding Proof Structure:
  - Vulnerable code location (file:line)
  - Attack scenario (step-by-step)
  - Input that triggers the vulnerability
  - Expected vs actual behavior
  - Impact assessment
  - Confidence level (Confirmed / Likely / Possible)
```

**Validation Rules:**
- **Confirmed** -- Code path clearly allows the attack, no guards present
- **Likely** -- Guards exist but are bypassable or incomplete
- **Possible** -- Theoretical risk, depends on configuration or runtime conditions

Do NOT report findings without supporting code evidence.

#### Phase 4: Classify

Assign severity and categories:

**Severity (CVSS-inspired):**

| Severity | Criteria |
|----------|----------|
| **Critical** | RCE, auth bypass, SQL injection, data breach, admin takeover |
| **High** | XSS (stored), SSRF, privilege escalation, mass data exposure |
| **Medium** | CSRF, open redirect, info disclosure, missing rate limits |
| **Low** | Missing headers, verbose errors, weak session config |
| **Info** | Best practice suggestions, hardening recommendations |

**OWASP Top 10 (2021) mapping:**

| ID | Category |
|----|----------|
| A01 | Broken Access Control |
| A02 | Cryptographic Failures |
| A03 | Injection |
| A04 | Insecure Design |
| A05 | Security Misconfiguration |
| A06 | Vulnerable Components |
| A07 | Auth & Identification Failures |
| A08 | Software & Data Integrity Failures |
| A09 | Security Logging & Monitoring Failures |
| A10 | Server-Side Request Forgery |

**STRIDE mapping:** Tag each finding with the applicable STRIDE category.

#### Phase 5: Log

Append to security-audit-results.tsv:

```tsv
iteration	vector	severity	owasp	stride	confidence	location	description
0	-	-	-	-	-	-	baseline -- 3 npm audit warnings
1	IDOR	High	A01	EoP	Confirmed	src/api/users.ts:42	GET /api/users/:id missing ownership check
2	XSS	Medium	A03	Tampering	Likely	src/components/comment.tsx:18	User input rendered without sanitization
3	rate-limit	Medium	A05	DoS	Confirmed	src/api/auth.ts:15	POST /login has no rate limiting
```

#### Phase 6: Repeat

- **Unbounded:** Keep finding vulnerabilities. Never stop. Never ask.
- **Bounded (/loop N):** After N iterations, generate final report and stop.
- **Coverage tracking:** Every 5 iterations, print coverage summary.

### Coverage Summary Format

```
=== Security Audit Progress (iteration 10) ===
STRIDE Coverage: S[x] T[x] R[ ] I[x] D[x] E[x] -- 5/6
OWASP Coverage: A01[x] A02[ ] A03[x] A04[ ] A05[x] A06[x] A07[x] A08[ ] A09[ ] A10[ ] -- 5/10
Findings: 4 Critical, 2 High, 3 Medium, 1 Low
Confirmed: 7 | Likely: 2 | Possible: 1
```

## Final Report Structure

Generated at loop completion (bounded) or on interrupt (unbounded):

Create a `security/{YYMMDD}-{HHMM}-{audit-slug}/` folder with these files:

### overview.md
Executive summary with total findings, STRIDE/OWASP coverage, top 3 critical findings, and links to all report files.

### threat-model.md
Full STRIDE analysis: asset inventory, trust boundary diagram, STRIDE threat matrix, risk ratings.

### attack-surface-map.md
Entry points, data flows, and abuse paths.

### findings.md
All findings from the loop in descending severity. Each finding includes OWASP category, STRIDE category, location, confidence, description, attack scenario, code evidence, and mitigation.

### owasp-coverage.md
Coverage matrix showing which OWASP categories were tested and results.

### dependency-audit.md
Output of dependency security tools (npm audit, pip audit, etc.).

### recommendations.md
Prioritized action items with code fix snippets, grouped by priority level.

### Folder Naming Convention

```
security/{YYMMDD}-{HHMM}-{audit-type-slug}/
```

- If no scope/focus specified -> `stride-owasp-full-audit`
- If scope is auth-related -> `auth-authorization-audit`
- If scope is API-related -> `api-security-audit`
- If user provides a focus string -> kebab-case it

## Metric for the Loop

The security audit uses a **coverage + finding count** composite metric:

```
metric = (owasp_categories_tested / 10) * 50 + (stride_categories_tested / 6) * 30 + min(finding_count, 20)
```

- **Direction:** higher is better (more coverage + more findings = more thorough)
- **Maximum theoretical:** 50 + 30 + 20 = 100
- **Baseline:** 0 (nothing tested yet)

This incentivizes the loop to cover ALL categories before going deep on any one.

## Flags & Modes

### `--diff` — Delta Mode

Only audit files changed since the last audit.

1. Find the latest `security/*/overview.md` by timestamp in folder name
2. Parse `findings.md` from that folder to get previously tested files
3. Run `git diff --name-only {last_audit_commit}..HEAD` to find changed files
4. Scope the current audit to ONLY those changed files
5. Mark findings as: **New**, **Fixed**, or **Recurring**

If no previous audit folder exists, `--diff` falls back to full audit with a warning.

### `--fail-on` — Severity Threshold Gate

Exit with non-zero code if findings meet or exceed a severity threshold. Designed for CI/CD blocking.

| Flag Value | Blocks on |
|------------|-----------|
| `critical` | Any Critical finding |
| `high` | Any Critical or High finding |
| `medium` | Any Critical, High, or Medium finding |

### `--fix` — Auto-Remediation Mode

After completing the audit, switches to standard autoresearch loop to fix confirmed findings.

1. Run the full security audit (setup + loop + report)
2. Filter findings: only **Confirmed** severity **Critical** and **High**
3. Switch to standard autoresearch loop:
   - **Goal:** Fix all confirmed Critical and High findings
   - **Scope:** Files referenced in findings (file:line locations)
   - **Metric:** Count of remaining confirmed findings (lower is better)
   - **Verify:** Re-run the security checks that found each vulnerability
4. For each fix iteration:
   - Pick the highest-severity unfixed finding
   - Apply the mitigation from recommendations.md
   - Commit the fix
   - Re-verify: does the vulnerability still exist?
   - If fixed -> keep commit, mark finding as "Fixed" in report
   - If still vulnerable -> revert, try different approach
   - If new findings introduced -> revert immediately

**Safety rules:**
- NEVER fix Low or Info findings automatically (too subjective)
- NEVER modify test files (fixes must not break existing tests)
- Run existing tests after each fix -- revert if any test fails
- Maximum 3 fix attempts per finding, then skip

### Combining Flags

Flags can be combined:

```
# Delta audit + auto-fix critical/high + block on remaining criticals
/loop 15 /autoresearch-security --diff --fix --fail-on critical

# Quick delta check in CI
/loop 5 /autoresearch-security --diff --fail-on high
```

**Execution order when combined:**
1. `--diff` narrows scope
2. Security audit runs (with narrowed scope if `--diff`)
3. `--fix` runs remediation loop on confirmed Critical/High
4. `--fail-on` checks remaining (unfixed) findings against threshold

## OWASP Checks Reference

Detailed checks to perform for each OWASP category:

### A01 — Broken Access Control
- IDOR on all parameterized routes
- Missing authorization middleware on protected routes
- Horizontal privilege escalation (user A accessing user B's data)
- Vertical privilege escalation (user accessing admin functions)
- Directory traversal on file operations
- CORS misconfiguration allowing unauthorized origins
- Missing function-level access control

### A02 — Cryptographic Failures
- Sensitive data in plaintext (passwords, tokens, PII)
- Weak hashing algorithms (MD5, SHA1 for passwords)
- Hardcoded secrets/API keys in source
- Missing encryption at rest / in transit
- Weak random number generation for security tokens
- Exposed .env files or config with secrets

### A03 — Injection
- SQL/NoSQL injection in database queries
- Command injection in shell executions (exec, spawn)
- XSS (stored, reflected, DOM-based)
- Template injection (SSTI)
- Path injection in file operations
- Header injection (CRLF)

### A04 — Insecure Design
- Missing rate limiting on sensitive endpoints
- No account lockout after failed login attempts
- Predictable resource identifiers
- Race conditions in critical operations
- Missing CSRF protection on state-changing operations

### A05 — Security Misconfiguration
- Debug mode enabled in production
- Default credentials / admin pages exposed
- Verbose error messages exposing internals
- Missing security headers (CSP, HSTS, X-Content-Type-Options)
- Unnecessary HTTP methods enabled
- Stack traces in error responses

### A06 — Vulnerable and Outdated Components
- Known CVEs in dependencies (npm audit, pip audit)
- Outdated frameworks with security patches available
- Unmaintained dependencies

### A07 — Identification and Authentication Failures
- Weak password policies
- Missing multi-factor authentication for admin
- Session fixation vulnerabilities
- JWT vulnerabilities (none algorithm, weak secret, no expiry)
- Insecure password reset flows
- Missing session invalidation on logout/password change

### A08 — Software and Data Integrity Failures
- Missing integrity checks on CI/CD pipelines
- Unsigned or unverified updates/dependencies
- Insecure deserialization
- Missing CSP or SRI for external scripts

### A09 — Security Logging and Monitoring Failures
- Missing audit logs for security events
- No logging of failed authentication attempts
- Sensitive data in logs (passwords, tokens)
- Missing alerting on suspicious activity
- Log injection vulnerabilities

### A10 — Server-Side Request Forgery (SSRF)
- Unvalidated URLs in server-side requests
- DNS rebinding vulnerabilities
- Missing allowlist for external service calls
- Proxy/redirect endpoints without validation

## Red-Team Adversarial Lenses

### Security Adversary (Primary)
**Mindset:** "I'm a hacker trying to breach this system"
- Focus: auth bypass, injection, data exposure, privilege escalation
- Method: trace every input to its sink, find missing guards
- Priority: exploitable findings over theoretical risks

### Supply Chain Attacker
**Mindset:** "I'm compromising dependencies or build pipeline"
- Focus: dependency vulnerabilities, CI/CD weaknesses, unsigned artifacts
- Method: audit dependency tree, check for typosquatting, verify integrity

### Insider Threat
**Mindset:** "I'm a malicious employee or compromised account"
- Focus: privilege escalation, data exfiltration, access control gaps
- Method: check what a low-privilege user can access, find horizontal movement

### Infrastructure Attacker
**Mindset:** "I'm attacking the deployment, not the code"
- Focus: container escape, exposed services, network segmentation
- Method: check Docker configs, K8s manifests, exposed ports, env vars

## Gitignore

Add to `.gitignore` (if not already present):
```
security-audit-results.tsv
```

The `.tsv` iteration log is a working file. The `.md` reports are meant to be committed and shared.

## Anti-Patterns

- **Do NOT report theoretical risks without code evidence** -- every finding needs a file:line reference
- **Do NOT skip categories** -- the loop should aim for 100% OWASP + STRIDE coverage
- **Do NOT auto-fix vulnerabilities** unless `--fix` flag is set -- report only by default
- **Do NOT test against live production** -- analyze code statically, suggest dynamic tests
- **Do NOT report the same finding twice** -- check results log for duplicates before logging
- **Do NOT prioritize quantity over quality** -- 5 confirmed critical > 50 theoretical lows
