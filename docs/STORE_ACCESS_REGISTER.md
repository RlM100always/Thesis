# Store Access Register

**Application:** B-SMART  
**Last checked:** 8 November 2026

This register intentionally documents access routes and account status, not passwords.

## Shared platform URLs

| Purpose | URL | Access |
|---|---|---|
| Public store directory | https://thesis-j0n8.onrender.com/#/stores | Public |
| Storefront pattern | https://thesis-j0n8.onrender.com/#/store/{store-slug} | Public |
| D1 Business Owner Center | https://thesis-j0n8.onrender.com/#/d1-owner | Owner account required |
| D1 Platform Admin | https://thesis-j0n8.onrender.com/#/d1-platform-admin | Platform Admin secret required |
| Main business application | https://thesis-j0n8.onrender.com/ | User account and business membership required |

## Verified account/store state

The last repository-side live audit recorded:
- 10 seeded sample stores and 259 sample products in Cloudflare D1.
- One retained CI/POS test fixture, excluded from public discovery.
- No verified real merchant-owned operational store.
- One legacy CI merchant account; it is not a real business owner and must not be distributed as an operational login.
- Customer accounts were zero at the time of that audit.

The sample catalogue entries are not real merchant accounts. Do not assign real owner credentials to them or describe their sample orders as revenue.

## Owner access onboarding

1. A real business owner registers at the D1 Business Owner Center.
2. The owner uses their own business email and a unique password (current registration policy: 12–128 characters).
3. The owner signs in and creates a store profile. New stores are private drafts.
4. Platform Admin reviews the business and approves publication/operational COD status.
5. The owner receives their public store URL and owner-panel URL.
6. Record the store name, public slug, owner email, role and approval status below. Do not record the password.

**Release gate:** owner email verification and self-service password recovery are implemented in the upgrade branch, but are not live until migration 0009 is safely applied and the Resend sender is configured. Do not treat a typed email address as proof of business ownership. Open public merchant onboarding remains disabled until the email delivery flow is tested end to end.

## Per-store register

Add one row only after a real owner account and store have been created and reviewed.

| Store name | Public store URL | Owner login URL | Owner email | Role | Status | Credential reference (no secret) |
|---|---|---|---|---|---|---|
| No verified operational merchant store recorded | — | https://thesis-j0n8.onrender.com/#/d1-owner | — | — | Not onboarded | — |

## Secret storage

Keep the following outside GitHub source, README, issue comments and public deployment logs:
- Owner passwords and password-reset links.
- `PLATFORM_ADMIN_KEY`.
- `CLOUDFLARE_API_TOKEN` and Cloudflare account identifiers where treated as sensitive by the organisation.
- AI provider keys, email-provider keys, payment gateway secrets and webhook signing secrets.
- Database export files and customer data.

Use Render Environment, Cloudflare Worker secrets, GitHub Actions repository secrets or an approved password manager as appropriate. Never paste secret values into a public README.


## Account security rule

This register is an access directory, not a credential vault. It records owner email, role, store, panel URL, verification and active/suspended status. It must never contain passwords, password hashes, API keys, reset links, session tokens or one-time access keys. Use the platform-admin owner directory to suspend/reactivate access; password resets are sent to the verified owner email.
