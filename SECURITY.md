# PEIMS v0.4 Security model — prototype, not production approval

## Trust boundaries

1. **Public Streamlit demonstrator:** intended for fictional project data. No authentication, user isolation beyond Streamlit session state, safe file storage, permanent audit log or managed database. Never send actual site records, mine plans, HSE information, invoices or identities.
2. **Enterprise API source:** deliberately separate. All `/v1/` routes require a valid signed RSA JWT with matching issuer and API audience; project membership must be pre-provisioned via trusted console. The project id is checked in every database query. API never trusts a role sent by the caller.
3. **PostgreSQL:** application-side role checks and SQLAlchemy constraints. DB credentials require secret management; migrations and privileged role provisioning must use operationally isolated accounts. The initial prototype has **no PostgreSQL row-level security (RLS)**.
4. **Identity provider:** OIDC provider must issue an **access token intended for this API**, not a Streamlit identity cookie or an unrelated ID token. Validate issuer, signature, intended audience, expiry and issuance time. Explicit RS256 and HTTPS JWKS only. Rotate keys at provider and test revocation processes.

## Implemented controls

- No embedded or default passwords; API cannot serve project data without issuer, JWKS, audience and DB configuration.
- Scope membership as `(project_id, subject)`, roles as `viewer`, `engineer`, `manager`; viewer reads operational records, engineer edits activities/RFIs, manager additionally controls cost data and audit records.
- Optimistic row version check, 409 conflicts, row locks and single-transaction audit metadata for changes.
- Validation of progress percentage, money amount, text lengths and accepted enum values; DB CHECK and unique constraints.
- Error responses do not expose JWT details or reveal inaccessible project existence; secrets are not committed.
- Audit records include only actor, project, record, action, names of fields changed and timestamp, not full invoice or correspondence content.

## NOT included / required before company use

- Production SSO integration, live Postgres, database backups/recovery testing, user provisioning policies, idp session revocation and access review.
- Enforced TLS termination, a restricted origin list, network perimeter controls, WAF/rate limiting, secrets rotation, vulnerability scanning, monitoring or disaster recovery.
- Database-level RLS, immutable append-only logging, tamper-evident event signing, tenant isolation penetration testing and security sign-off.
- Any approval by Newmont or permission to ingest actual employee, procurement, engineering, operational or sensitive mine data.
- Regulatory-grade electronic signatures, formal transmittal or safety-critical control.

**Never expose the API as a public, production service before completing these controls and authorization.**
