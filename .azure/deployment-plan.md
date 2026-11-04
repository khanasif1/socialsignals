# Background extraction and iPhone verification

Status: Validated

Local implementation and simulator verification are complete. The user has
approved Azure resource creation in Australia East in the selected subscription.
Cloud quota, policy, permissions, Entra-only AI configuration, and deployment
validation passed. The application is deployed and live storage/AI/reader
verification passed. The deployed stack keeps Storage and Key Vault public
endpoints disabled and uses private service connectivity. Preserve that network
boundary; do not broaden access to work around an RBAC or client-routing issue.

## Scope

- Add a scheduled, user-authorized LinkedIn extraction worker.
- Store extracted original posts in private Blob storage for the existing backend.
- Preserve the existing AI processing, deduplication, bookmarks, and iOS reader.
- Test the interface at iPhone 13 Pro Max dimensions and distinguish browser
  emulation from testing on a physical iPhone.

## Requirements and safety boundaries

- Never put LinkedIn credentials, cookies, or session data in GitHub or the app.
- Do not bypass MFA, CAPTCHA, access restrictions, or account-security challenges.
- Do not claim exhaustive coverage of a personalized or infinite-scrolling feed.
- Live extraction, Azure deployment, and physical-device verification require
  the corresponding authorized account, Azure context, and device access.

## Architecture

The user directed autonomous implementation after the initial planning pause.
The worker and opt-in deployment artifacts are implemented. The user approved
the selected subscription, Australia East, and provisioning an
Azure OpenAI resource with Entra ID authentication only; API keys are blocked.
No budget cap was specified. Use conservative single-instance hosting and a
bounded AI deployment rather than interpreting this as unlimited capacity.
Production credentials belong in Key Vault, never this plan or Git.

The existing application uses Azure CLI and Bicep, a Linux Python 3.12 App
Service B1 with Always On, private Blob JSON storage, Key Vault references,
and managed identity. Preserve that deployment recipe and the existing API.

A scheduled App Service WebJob in an Ubuntu Playwright container is the
implemented option. It runs daily at 06:00 UTC, with Always On, explicit
post/scroll/time/processing limits and separate renewable crawler/writer leases.
The API and worker share the opt-in container and managed identity; this does
not isolate worker credentials or browser resource usage from the API.
The existing ZIP deployment remains the default. `deploy-crawler.sh` requires
an explicit existing app, subscription, image, and Key Vault secret references.
It disables collection during the upgrade and requires worker-image-aware
storage health before enabling the schedule.

The implemented worker flow is:

1. Acquire a separate renewable crawl lease, not the global reader writer lock.
2. Read credentials securely at runtime and use normal browser login only.
   Stop and expose a sanitized action-required status on MFA, CAPTCHA, consent,
   or account-security challenges; never bypass them or log login-page content.
3. Collect a bounded, best-effort batch of available feed posts and HTTPS image
   links. Preserve original text and provenance; do not invent publication dates
   or promise exhaustive coverage of the personalized feed.
4. Pass normalized records through `Reader.import_posts`, which writes raw JSON
   and ingestion metadata under the existing writer lock. Dropping arbitrary
   JSON into Blob alone is insufficient.
5. Explicitly schedule pending AI processing through the canonical reader flow.
   The current preference defaults to manual processing, so importing records
   alone will not populate processed posts in the app.
6. Expose sanitized collection/processing status, last success, remaining work,
   and retryable versus action-required failures. Keep credentials and session
   state out of the client, AI requests, logs, screenshots, and Git.

The distinct `linkedin_crawler` source is wired through backend models,
frontend types, integration status, and user-facing copy. The app refreshes
when foregrounded, every active minute, and while collection/processing runs.
Challenge and restricted-login states pause scheduled attempts until explicit
`--resume`. Browser contexts are ephemeral; no cookies or credentials enter
post storage. Official personal-feed API entitlement remains false.

Implemented artifacts include the browser collector, worker CLI, container,
persisted WebJob entry point/schedule, existing-app upgrade script, optional
Bicep/wrapper configuration, secure environment example, and repeatable
backend/browser/container test suites. `test-crawler-container.ps1` generates
ephemeral local emulator credentials and removes its own test containers.

LinkedIn's User Agreement, section 8.2, prohibits unauthorized automated access
and scraping. This is not a supported personal-feed API and can restrict the
account. Confirm the permitted source/access arrangement before live use.

References consulted:

- https://www.linkedin.com/legal/user-agreement
- https://learn.microsoft.com/en-us/azure/app-service/webjobs-create
- https://learn.microsoft.com/en-us/azure/azure-functions/functions-how-to-custom-container

## Azure context

Subscription: User-approved target (identifier retained only in protected local state).
Region: Australia East (`australiaeast`, user approved).
Resource group: Dedicated `rg-signal-aue`, provisioned in the approved subscription.
Budget: No cap specified; preserve conservative resource sizes.
AI: New Azure OpenAI resource; Entra ID only, local/key authentication disabled.

### Approved rollout

The user's resource-creation request and explicit subscription/region selection
approve the previously presented dedicated-resource-group architecture, including
the requested new AI resource. Do not modify unrelated existing resources.

- New resource group `rg-signal-aue`, in the approved subscription only.
- One Linux B1 App Service plan and one containerized SIGNAL application.
- One Standard LRS storage account with private Blob container and shared keys
  disabled; one RBAC Key Vault with purge protection.
- One Basic container registry with admin and anonymous access disabled.
- One OpenAI S0 account with local authentication disabled, and one regional
  Standard `gpt-4.1-mini` deployment, version `2025-04-14`, capacity 30 (30K TPM).
  Unlike GlobalStandard, this deployment does not select global processing.
- Scope the application's managed-identity roles to its Blob container,
  Key Vault, registry (AcrPull), and OpenAI account (OpenAI User).
- Required network adaptation within the same dedicated group: one VNet with
  separate delegated App Service and private-endpoint subnets, two private
  endpoints (Blob and Key Vault), and their private DNS zones/links. Preserve
  disabled public access and all existing identity restrictions. Basic B1 supports
  outbound VNet integration; no hosting-tier upgrade or public inbound app
  restriction is required. The user authorized resource creation and end-to-end
  deployment with no stated budget cap. An additional networking question could
  not be answered because the user was unavailable; use only the minimum
  connectivity required by the observed subscription restriction.
- Use subscription-scope validation/what-if so the dedicated resource group
  need not be created before validation. Build and push with the verified Linux
  Docker engine and Entra-authenticated ACR login; the context is allowlisted.
  ACR Tasks upload failed on Windows while traversing long frontend paths.
- Keep collection disabled until Key Vault credentials resolve. Generate
  independent reader/session secrets into protected local deployment state,
  never print secrets, and reuse them on redeployment.
- Test live managed-identity Blob access and Entra-authenticated model processing
  before attempting an authorized account crawl. Account challenges still pause.

Read-only preflight confirmed ARM access, wildcard management permissions,
Australia East Linux B1 availability, the OpenAI User role definition, and
5,000 units of unallocated regional Standard gpt-4.1-mini quota. The CLI quota
workflow returned App Service limit 14 with usage 0. No capacity increase is
needed. Model retirement is currently listed as April 14, 2027; migration
must be planned before that date.

The explicit subscription and region approval supersedes the earlier blocked
subscription selection. Infrastructure was provisioned after successful validation.
The installed Docker Desktop was started and its Linux engine verified.
The actual Linux amd64 image was built and run, including Chromium as UID
10001, API health/startup, and the published WebJob entry point.
Container PyPI TLS failed in this environment; a complete Linux wheel set was
downloaded through the host's verified HTTPS connection and mounted during
the dependency build step. TLS verification was not disabled. Wheel files
are ignored and are not copied into image layers.

## Verification

Completed locally without real LinkedIn credentials or Azure resource changes:

- Fixed Topics card accessibility so the labeled control handles activation.
- Increased featured and regular bookmark controls to at least 48 x 48.
- Added `frontend/playwright.config.ts`, `frontend/e2e/iphone.spec.ts`, and
  `npm run test:iphone`. All 12 WebKit checks passed with the iPhone 13 Pro Max
  device profile, 3x pixel ratio, and full-screen CSS viewports of 428 x 926
  and 926 x 428. Touch activation, navigation, search/empty states, bookmarks
  and reload persistence, topic activation, reader/explanations, dark/large
  text, image gallery sizing, image failures/retry, icon font loading, and
  overflow were covered. Final tests ran against the exported web app.
- Tests use isolated fictional demo state and locally fulfilled image fixtures;
  no live LinkedIn account or AI provider was used.
- TypeScript checking, 9 frontend unit tests, and final Expo web/iOS bundle
  exports passed. An exported iOS bundle is not a signed IPA.
- The actual Release app passed both Maestro flows on an iPhone 13 Pro Max
  simulator running iOS 26.2:
  https://github.com/khanasif1/socialsignals/actions/runs/41590115395.
  Real Chromium fixture extraction, Azure Blob SDK requests against Azurite,
  HTTPS FastAPI, native login, image loading, original text, save/read,
  automatic second-batch refresh without tapping sync, and Keychain session
  restoration after app restart passed. Final persisted state contained two
  processed posts with the first saved and read. Xcode generated simulator
  signing and entitlements; no Apple account or device profile was used.
  Fixture posts, images, and AI output are synthetic. This does not verify
  live LinkedIn access, production Azure identity, or a physical iPhone.
- All 72 backend tests passed inside the actual Linux worker image. This
  includes real Chromium extraction against intercepted synthetic pages,
  actual Azure Blob SDK calls against isolated Azurite containers, real
  HTTP FastAPI access, and the exported iPhone-sized WebKit reader. A second
  background batch appeared automatically without tapping sync.
- The same image's actual startup, storage health, non-root gunicorn processes,
  and published WebJob shell entry point passed. Disabled collection does not
  attempt login. Shell syntax, deployment guard behavior and Bicep compilation
  passed. Windows CRLF scripts are normalized before container execution.
- The Blob emulator test uses shared-key HTTP only on local test endpoints;
  it does not validate production HTTPS, managed identity, RBAC, or Key Vault.
- Screenshots and browser report are in ignored frontend test-output directories.
  The earlier manual iframe and demo-storage changes were removed/restored.

Pending: successful authorized live LinkedIn collection, a private-network route
for direct workstation Blob browsing, and physical iPhone installation/testing.
The November 4 runtime follow-up below supersedes the earlier disabled-crawler
checkpoint: credentials resolve and the schedule is enabled, but the first real
attempt stopped with `access_restricted`. Collection is paused pending account/
access resolution and explicit resume. Native simulator verification does not
prove physical-device behavior. Account challenges are never bypassed.

## Validation proof

Recipe: Azure CLI with subscription-scope `infrastructure/bootstrap.bicep`,
which creates the isolated resource group and calls the existing
`infrastructure/main.bicep`. `deployment/deploy-cloud.ps1` provides Prepare,
Validate, and guarded Deploy actions; protected parameters are ignored by Git.

- [x] All validation checks pass
  - [x] 1. Core Validation (CLI, auth, build, validate, what-if) - bootstrap/main compiled; subscription validation and what-if passed against the approved target.
  - [x] 2. Docker Build (if containerized) - actual Linux amd64 image built and runtime tested.
  - [x] 3. Azure Policy Validation - assigned policy sets reviewed through Azure CLI; ARM validation passed with no policy denial. Entra-only AI and storage authentication are enforced independently.

The azure-validate recipe's `validate-deployment.ps1` completed all five checks
using scope `sub`, location `australiaeast`, the approved subscription,
`infrastructure/bootstrap.bicep`, and the protected parameter file.
The initial what-if reported Create: 17, Modify: 0, Delete: 0. No pre-existing
resource changes were proposed. Validation timestamp: November 3, 2026.

After provisioning, Key Vault and Storage reported publicNetworkAccess Disabled
when the property was omitted, preventing the approved authenticated-public-
endpoint architecture from working. Both now explicitly request Enabled while
retaining RBAC, Entra-only storage, TLS, and private Blob contents. The corrected
template passed all five core checks again; the resource-ID-only preview targets
only this dedicated group. The helper's detailed create/modify/delete counts
include property deltas and are not counts of resource deletions. The deployment
is incremental, not complete. No policy deny was bypassed or exception granted.

The public-access correction did not persist: both services again reported
Disabled. It is not a working fix and has been replaced by private connectivity
in `infrastructure/private-network.bicep`. Bootstrap enables it; legacy main
template consumers retain an opt-in switch. The new template compiles and
Microsoft.Network is registered. Repeat target-scope validation before deploying.

Private-network revision validation on November 3, 2026: all five core checks
passed, including subscription ARM validation and what-if. The model/container
runtime is unchanged and the published Linux amd64 image digest is
`sha256:d8cc8313dab047abea6eb4f97fd518b32414462561daf6b5b4c83ea1970a3e41`.
The four data-plane roles remain unchanged; private-endpoint connections do not
grant the app any new identity permissions. No subscription policy denial was
reported for the private network resources.

The private endpoints were provisioned with Approved connections; both Key Vault
references resolved and the actual container passed managed-identity Blob health.
The first live AI run exposed a provenance bug: structured output could set
`Explanation.generated=false`. The API now controls this metadata for newly
generated and previously cached explanations. Thirty targeted backend/API/
deployment tests passed. Release `20261103-entra-1` built as Linux amd64 image
`sha256:5ee0795dc456aa45c9215e22315fecdd362f62d6f4f28a2ee264fb7d1b787aab`.
The complete five-check target-scope validation passed again for this release.

Real cloud API verification passed: original-text-preserving import, Entra-
authenticated structured model processing, private Blob persistence, search,
bookmarks/read state, and generated explanations. The single retained sample is
explicitly synthetic, has no source URL, and is not a LinkedIn crawl.
Both portrait/landscape live-cloud WebKit reader checks passed, including reload
restoration of saved/read state. Metro required a cleared export cache to replace
the previous fixture API endpoint.

The actual Kudu WebJobs API initially rejected execution because its Linux agent
was not enabled. Microsoft's WebJobs tutorial requires
`WEBSITE_SKIP_RUNNING_KUDUAGENT=false`; this is now present in Bicep and the
existing-app upgrade script. All five core checks passed for the correction and
34 targeted backend/deployment tests passed. Runtime worker image and scoped
identity roles are unchanged.

## Live deployment result

Deployment completed in the dedicated Australia East group `rg-signal-aue`.

- API: https://signal-aue-957858fe.azurewebsites.net
- Health: https://signal-aue-957858fe.azurewebsites.net/api/health
- Storage: `sig957858feaue`, private `signal-data` Blob container, shared keys
  and public network access disabled.
- Key Vault: `sig-l5smxkxbdrtja`, RBAC enabled, public network access disabled.
- Private Blob/vault endpoints: Succeeded, both connections Approved; app
  VNet integration and both Key Vault references verified.
- Registry: `sigl5smxkxbdrtja`, admin disabled. Published release
  `signal-worker:20261103-entra-1`, digest
  `sha256:1e05842322b855c6aa5a95ef36b0dd9e6faffb8bff9bd2c58a815416fd4f38ec`.
- AI account: `signal-aue-957858fe-ai`, local authentication disabled, both
  application AI-key settings empty. Regional model deployment Succeeded.
- Live RBAC verification confirmed the app identity's four resource-scoped
  data-plane roles: Blob Data Contributor, Key Vault Secrets User, AcrPull,
  and Cognitive Services OpenAI User.
- Live API report: storage connected, worker image true, LLM processing,
  preserved original text, search, saved/read persistence, and generated
  explanations all passed. One explicitly labeled synthetic sample is retained.
- Actual Kudu-triggered WebJob run `202611030819040026`: Success, with collection
  disabled. This proves Azure job execution, not authenticated LinkedIn extraction.
- Live-cloud iPhone 13 Pro Max WebKit: portrait and landscape passed. These are
  browser checks, distinct from the earlier actual native simulator runs.
- Final settings: production CORS restored to `[]`, crawler disabled, daily
  schedule disabled, Linux Kudu agent enabled. Temporary preview/export/log
  helpers were stopped and removed. Protected deployment state remains local.

User action still required: rotate the password disclosed in chat and run the
interactive `deployment/configure-crawler.py` helper to put its replacement in
Key Vault. It verifies references and health before enabling collection. No real
LinkedIn login was attempted, no disclosed credential was used, and no account
challenge will be bypassed. Apple signing and physical-device access remain
separate prerequisites.

## Runtime follow-up: November 4, 2026

The user confirmed configuring the replacement credentials. Both credential
settings are Key Vault references with live status `Resolved`. The app has
`SIGNAL_LINKEDIN_CRAWLER_ENABLED=true` and `WEBJOBS_DISABLE_SCHEDULE=0`.
No LinkedIn credential values were retrieved or printed during this follow-up.

An actual immediate job was triggered once: `202611040147010832`, finishing at
01:47:55 UTC with Kudu status `Failed`. The persisted Blob-backed API reports
`action_required`, code `access_restricted`, 0 extracted, and no last success.
The collector refused a guarded 401/403/429 response before feed extraction;
the sanitized code does not distinguish the exact HTTP status. No challenge
was bypassed and no automatic resume or repeated login was attempted.
The retained-post API confirmed exactly one explicitly synthetic deployment
sample and zero `linkedin_crawler` posts.

The signed-in operator already had inherited Owner, but no Blob data role.
Storage Blob Data Reader was assigned and verified at only `sig957858feaue`'s
account scope; no new operator write/delete role was granted. The app's
existing scoped service roles are unchanged.

Public Blob listing from this workstation was tested and remains network-blocked.
Storage still has public networking and shared-key access disabled. A data role
does not supply private-endpoint routing or DNS to a browser. The user was
unavailable to choose an approved private client route or policy-permitted
network change, so the private boundary was preserved. The runbook documents
private-client CLI/Portal access and existing authenticated app/API status.
The initial deployment checkpoint above is historical, not the current crawler
state. Direct workstation Blob browsing and live LinkedIn collection remain
external blockers, not completed verification.

The operator subsequently requested consolidation and removal of non-main
GitHub branches. The sole non-main branch was identical to main at `6fb70f6`;
containment was checked before an expected-head-guarded remote deletion.
Local worktree files were preserved.

The explicitly requested corporate sign-in was resolved through the resource
directory's aliases to the same operator identity already holding Blob Data
Reader and inherited Owner. No additional/broader role was necessary. The
provided Portal error confirms a public-network restriction. Approval for a
single-client network exception was requested but unavailable; storage remains
private-only. README now includes a numbered operator verification checklist.

`docker build --quiet --tag signal-crawler:cloud-validated --file deployment/Dockerfile .`
passed against the Linux engine, producing image
`sha256:9f917fadaad85285dd84b6d331c20a41457e54e48962cde8cb4bb181853c63d1`.
The nine backend integration tests, including the Entra-without-keys constructor
test, passed. Previous complete container and native proof remains recorded above.

## Role Assignment Verification

Status: Verified (service roles live on November 3; operator assignment live on
November 4, 2026).
The sole service identity is the web application's system-assigned identity.
Its Storage Blob Data Contributor role is scoped to the private container
(JSON reads/writes, listing, properties, and leases); Key Vault Secrets User is
scoped to the dedicated vault; AcrPull to the new registry; Cognitive Services
OpenAI User to the new Entra-only account. No application role is subscription-
or resource-group-scoped. The authenticated API smoke test exercised the
application's identity and private connectivity. The separate operator now has
account-scoped Storage Blob Data Reader as recorded above; its assignment was
verified, but workstation data-plane requests remain blocked by networking.
