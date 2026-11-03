# Background extraction and iPhone verification

Status: Ready for Validation

Local implementation and verification are complete. Azure target confirmation,
cloud validation, live credentials, and physical-device verification remain
blocked; this status is not a claim that Azure validation passed.

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
The worker and opt-in deployment artifacts are implemented. That direction did
not identify an approved Azure subscription or supply account credentials.

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

Subscription: Not confirmed.
Region: Not confirmed.
Resource group and budget: Not confirmed.

The signed-in Azure CLI account is not approval to deploy personal account
credentials or data to that subscription. The subscription question was not
answered because the user was unavailable. No resources were created.
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

Pending: approved Azure context/capacity/permissions, registry publication and
deployment, actual Kudu schedule execution, managed-identity Blob integration,
Key Vault resolution, live AI processing, approved account login and unattended
collection, and installation/testing on a physical iPhone. Native simulator
verification does not prove physical-device behavior. Account challenges are never
bypassed; live LinkedIn DOM compatibility and account acceptance are unverified.

## Validation proof

Recipe: Azure CLI wrappers with the existing Bicep template at
`infrastructure/main.bicep`; preserve this repository layout.

- [ ] All validation checks pass
  - [ ] 1. Core Validation (CLI, auth, build, validate, what-if) - run the azure-validate `validate-deployment` script with the approved subscription, target resource group, and this template.
  - [x] 2. Docker Build (if containerized) - actual Linux amd64 image built and runtime tested.
  - [ ] 3. Azure Policy Validation

Local build and functional proof is recorded above. Azure validation has not
passed and no cloud deployment has been executed. The azure-validate workflow
loaded the plan and recorded the recipe checklist, but its core target-scope
validation, what-if, policy, and role checks remain blocked. The subscription
question was asked again after local completion; the user was unavailable.
Do not substitute the active work subscription or mark this plan Validated.
