# B-SMART Store Access Register

**Application:** B-SMART  
**Last checked:** 8 November 2026

This is an access directory, not a password vault. It records URLs, owner email, account role and approval status. Never store passwords, password hashes, reset links, session tokens, API keys or one-time access keys here.

## Shared platform URLs

| Purpose | URL | Access |
|---|---|---|
| Public store directory | https://thesis-j0n8.onrender.com/#/stores | Public; only active approved merchant stores appear |
| Storefront URL pattern | https://thesis-j0n8.onrender.com/#/store/{store-slug} | Public after admin approval |
| Business Owner login/dashboard | https://thesis-j0n8.onrender.com/#/d1-owner | Verified owner account required |
| Platform Admin | https://thesis-j0n8.onrender.com/#/d1-platform-admin | Platform Admin secret required; keep secret in password manager |
| Main B-SMART business application | https://thesis-j0n8.onrender.com/ | Existing application account and business membership |

## Current verified production status

- Cloudflare D1 `bsmart-commerce` is schema version 13 (customer password-recovery migration applied).
- 11 store rows and 260 product rows are retained, all stores currently inactive and marked sample/demo.
- 3 existing orders, 3 order lines, 3 stock movements, 1 cashbook receipt and 1 legacy CI merchant account remain preserved.
- Public store directory returns zero stores and zero products because there are no approved real merchant stores.
- There are zero verified real owner accounts and zero customer accounts recorded in the last live D1 audit.
- Owner authentication uses PBKDF2 password hashes. Owner and customer password-recovery code is deployed; email delivery is **not configured** because Resend API key and verified sender are pending. Recovery endpoints fail closed until configured.
- Do not distribute the legacy CI account or use sample stores as real merchant accounts.

## Owner onboarding — not open for real production registration yet

1. Configure Cloudflare Worker secret `RESEND_API_KEY`.
2. Verify a sender identity/domain in Resend and set `AUTH_EMAIL_FROM`.
3. Set `PUBLIC_APP_URL=https://thesis-j0n8.onrender.com`.
4. Run staging tests for owner/customer registration, email verification, login, forgot password, token expiry/reuse and session revocation.
5. Re-run live owner auth health and confirm email verification/password reset are configured.
6. Only then allow a real business owner to register at `/#/d1-owner`.
7. Owner creates a private store draft and adds genuine store details/products.
8. Platform Admin verifies the business and approves store activation/publication.
9. Give the owner the public store URL and owner-panel login URL.
10. Add one access-register row after approval. Do not record the password.

## Per-store access register

Only add verified real stores. Use the store-specific public URL and shared owner login URL. Account role must reflect the actual enforced application role; currently D1 supports the `owner` role only. Staff roles are not yet implemented.

| Store name | Public store URL | Owner login URL | Owner email | Enforced role | Approval status | Credential reference (no secret) |
|---|---|---|---|---|---|---|
| No verified real merchant store yet | — | https://thesis-j0n8.onrender.com/#/d1-owner | — | — | Not onboarded | — |

## Secure access instructions

- Owners use a unique password and never share their login session.
- Use the password-reset email flow once Resend is configured; never send reset tokens in chat or store them in this file.
- Owner dashboard access is store-scoped; report any cross-store data visibility immediately.
- Platform Admin secret is stored only in an approved password manager/secret manager and Cloudflare Worker secret storage.
- Suspend compromised owner accounts through Platform Admin; suspension revokes active owner sessions.
- Rotate secrets after suspected exposure and review the audit log.
- Use MFA/SSO if added by a future identity provider; do not claim MFA is enabled until tested.

## Secret storage

Keep outside GitHub source, README, issue comments and public logs:
- Owner passwords and password-reset links.
- `PLATFORM_ADMIN_KEY`.
- `CLOUDFLARE_API_TOKEN`.
- `RESEND_API_KEY` and other email-provider credentials.
- AI provider keys, payment secrets and webhook signing secrets.
- Database export files and customer data.
