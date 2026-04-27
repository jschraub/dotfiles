# Ubiquitous Language

Terminology used in `~/dotfiles/claude/CLAUDE.md` and the conversations that produce updates to it. When discussing the global preferences system or any project that derives from it, prefer these terms.

## Preference system

| Term                  | Definition                                                                                                            | Aliases to avoid                                       |
| --------------------- | --------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------ |
| **Global file**       | The user's `CLAUDE.md` at `~/.claude/CLAUDE.md` containing always-on preferences (sourced from `~/dotfiles/claude/`)   | base file, root file, global CLAUDE                    |
| **Project file**      | A per-project `CLAUDE.md` that overrides or extends the global file for one project                                   | project-level CLAUDE, local CLAUDE                     |
| **Conditional rule**  | A rule prefixed by an explicit trigger; applies only when the trigger is satisfied                                    | scoped rule                                            |
| **Trigger**           | The condition (file pattern, framework presence, file extension) that activates a conditional rule                    | scope condition, activator                             |
| **Authority order**   | The precedence list determining which source wins on conflict (user > project file > project conventions > global)    | priority chain                                         |
| **Drift**             | Divergence between an existing project's conventions and the global file                                              | inconsistency                                          |
| **Drift flag**        | A one-time, per-session notice raised when drift is detected                                                          | drift warning                                          |
| **Carve-out**         | An explicitly documented exception to a global rule                                                                   | exception, opt-out                                     |

## Codebase structure

| Term                         | Definition                                                                                                | Aliases to avoid                          |
| ---------------------------- | --------------------------------------------------------------------------------------------------------- | ----------------------------------------- |
| **Monorepo**                 | A single repo containing `apps/` + `packages/`, managed by pnpm + Turborepo                               | workspace, multi-repo                     |
| **App**                      | A deployable application within the monorepo (`apps/web`, `apps/mobile`)                                  | application, frontend, client             |
| **Shared package**           | A workspace package under `packages/` consumed by apps                                                    | shared module, lib                        |
| **`packages/core`**          | The shared package: types, Zod schemas, orval-generated API client, pure logic, TanStack Query hooks      | core lib, common                          |
| **`packages/design-tokens`** | The shared package: raw design values + the shared `tailwind.config`                                      | tokens                                    |
| **Web app**                  | The Next.js App Router app at `apps/web`                                                                  | frontend (ambiguous — also covers mobile) |
| **Mobile app**               | The Expo app at `apps/mobile`                                                                             | native app                                |

## Functional programming

| Term                       | Definition                                                                                          | Aliases to avoid                       |
| -------------------------- | --------------------------------------------------------------------------------------------------- | -------------------------------------- |
| **Pragmatic FP**           | The user's chosen FP style: immutability + pure functions + ADTs, without heavy FP libraries        | light FP, FP-flavored, soft FP         |
| **Discriminated union**    | A type whose variants are distinguished by a tag field                                              | tagged union, ADT, sum type, variant   |
| **`Result`**               | A type representing either success (`ok`) or failure (`err`); used instead of throwing              | Either, outcome, result-or-error       |
| **Pure function**          | A function whose output depends only on its inputs, with no side effects                            | (canonical — no synonyms)              |

## Authentication (Keycloak)

| Term                  | Definition                                                                                                  | Aliases to avoid                |
| --------------------- | ----------------------------------------------------------------------------------------------------------- | ------------------------------- |
| **Shared Keycloak**   | The single Keycloak instance running on Cloudflare Containers, used by every project                        | central Keycloak, the IdP, SSO  |
| **Realm**             | A Keycloak-internal container for users and clients; the user runs one named `personal`                     | (Keycloak-specific term; keep)  |
| **OIDC client**       | A registration in Keycloak representing one app's authentication relationship                               | client, app registration        |
| **JWKS endpoint**     | The JSON Web Key Set URL Keycloak exposes; .NET backends use it via `AddJwtBearer` for JWT validation       | keyset URL                      |
| **Login theme**       | A Keycloak theme overriding the login UI; one per app via Keycloakify                                       | sign-in theme, branded login    |
| **Keycloakify**       | The tool that compiles React components into Keycloak theme JARs                                            | (proper noun)                   |

## Infrastructure (Cloudflare-first)

| Term                       | Definition                                                                                                                  | Aliases to avoid                              |
| -------------------------- | --------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------- |
| **Cloudflare-first**       | The default infra strategy: prefer Cloudflare for every layer that has a Cloudflare option                                  | Cloudflare-only, CF-default                   |
| **Cloudflare Container**   | The specific Cloudflare product: a Docker container managed by a Worker, sleeps when idle (proper noun)                     | container (ambiguous without qualifier)       |
| **Worker**                 | A Cloudflare Workers function — TypeScript only, runs on V8 isolates at the edge                                            | edge function, lambda                         |
| **Edge logic**             | Code running in Workers (auth, routing, preprocessing) — distinct from container backends                                   | edge code                                     |
| **Hyperdrive**             | Cloudflare's Postgres connection pooler, used in front of Neon                                                              | (proper noun)                                 |
| **Cold start**             | The latency cost when an idle Cloudflare Container wakes to serve a request (~1–3s default for .NET)                        | startup latency, warm-up                      |
| **Ready-to-Run** (R2R)     | A .NET build flag (`<PublishReadyToRun>true</PublishReadyToRun>`) that pre-compiles methods, halving cold start             | "R2" (collides with R2 storage — see flagged) |
| **Cloudflare R2**          | Cloudflare's S3-compatible object storage with zero egress fees                                                             | "R2" (without qualifier)                      |

## Git workflow

| Term                            | Definition                                                                                              | Aliases to avoid                |
| ------------------------------- | ------------------------------------------------------------------------------------------------------- | ------------------------------- |
| **Sacred history**              | Any commit pushed to a shared branch is permanent; never rewritten                                      | immutable history               |
| **Merge commit**                | The only permitted merge style; preserves every branch commit verbatim                                  | (canonical — squash/rebase forbidden) |
| **History rewrite**             | Any operation changing a commit's hash (squash, rebase, amend after push, force-push)                   | history modification            |
| **Conventional Commits**        | The commit-message format: `type(scope): subject`                                                       | (proper noun)                   |
| **Trunk-based**                 | A branching model with short-lived branches merging into `main`; no `develop` or `release` branches     | trunk development               |
| **Security-only rewrite**       | The single permitted reason to rewrite shared history: scrubbing leaked secrets via `git filter-repo`   | (canonical)                     |

## Testing

| Term                       | Definition                                                                                                | Aliases to avoid                |
| -------------------------- | --------------------------------------------------------------------------------------------------------- | ------------------------------- |
| **Strict TDD**             | Red-green-refactor cycle: failing test → confirm red → implement to green → refactor                      | TDD-by-default                  |
| **Spike**                  | Throwaway exploratory code, exempt from strict TDD; must be explicitly marked as a spike                  | exploration code, prototype     |
| **Integration test**       | A test that exercises a real database via Testcontainers, not a mock                                      | end-to-end (use Playwright e2e for UI) |
| **Testcontainers**         | The pattern/library of running real services (Postgres) in throwaway Docker containers for tests          | (proper noun)                   |

## Backend defaults

| Term                       | Definition                                                                                                   | Aliases to avoid                   |
| -------------------------- | ------------------------------------------------------------------------------------------------------------ | ---------------------------------- |
| **Greenfield service**     | A new backend service starting from scratch — defaults to F# + Giraffe                                       | new service, fresh service         |
| **SDK-heavy work**         | Backend work requiring complex SDK / framework integration — defaults to C# + Minimal APIs                   | framework-heavy, integration-heavy |

## Relationships

- A **Project file** overrides the **Global file** for the project it lives in.
- A **Conditional rule** has exactly one **Trigger** and zero-or-more **Carve-outs**.
- An **App** consumes one or more **Shared packages**.
- A **Monorepo** contains many **Apps** and many **Shared packages**.
- One **Shared Keycloak** has one **Realm** which has many **OIDC clients**.
- Each **App** ↔ exactly one **OIDC client** ↔ exactly one **Login theme**.
- A **Cloudflare Container** runs zero-or-one **Backend service**.
- A **Worker** can route requests to a **Cloudflare Container** (the two-piece pattern).
- An **Integration test** uses **Testcontainers** to provision a real Postgres.
- A **History rewrite** is permitted only via the **Security-only rewrite**.

## Example dialogue

> **Dev:** "I'm scaffolding a new product. Do I need a **Project file**?"

> **Domain expert:** "Only if you have project-specific overrides. The **Global file** already specifies the **Monorepo** layout, **Cloudflare-first** infra, **Shared Keycloak** for auth, and **Strict TDD**. A **Project file** is for **carve-outs**."

> **Dev:** "If I'm starting a backend, F# or C#?"

> **Domain expert:** "**Greenfield service** — F# + Giraffe. **SDK-heavy work** — C# + Minimal APIs. That rule lives under a **Conditional rule** triggered by the project type."

> **Dev:** "Auth?"

> **Domain expert:** "Register a new **OIDC client** in the `personal` **Realm** on the **Shared Keycloak**. Build a **Login theme** with **Keycloakify** consuming `packages/design-tokens`. Don't deploy a per-project Keycloak."

> **Dev:** "What if I open an existing project that uses Redux instead of TanStack Query?"

> **Domain expert:** "That's **drift**. Match the project's conventions, raise a **Drift flag** once, then proceed. Don't migrate unless asked."

> **Dev:** "And if a webhook handler has bad **cold start** symptoms?"

> **Domain expert:** "Try `min-instances ≥ 1` first, then **Ready-to-Run**, then NativeAOT only after measuring. Don't reach for AOT preemptively."

## Flagged ambiguities

- **"R2"** is overloaded between **Cloudflare R2** (object storage) and **Ready-to-Run** (.NET build flag). Always qualify in writing — use "**Cloudflare R2**" for storage and "**Ready-to-Run**" or "**`PublishReadyToRun`**" for the build flag.

- **"Container"** is overloaded between a generic **Docker container** and the specific **Cloudflare Container** product. Qualify with "Cloudflare" when discussing the product; use "Docker container" or "container image" for the generic concept.

- **"Project file"** specifically means a per-project **`CLAUDE.md`** in this glossary. It does **not** mean `.csproj`, `.fsproj`, or `package.json` — refer to those by their extension (e.g., "the `.csproj`").

- **"Hobby tier" / "Growth tier"** were used during planning but were **rejected** for the final file. The global file contains hobby-tier defaults only; growth-tier decisions are per-project. Treat these phrases as historical planning artifacts, not as live terminology.

- **"Stack"** was used loosely to mean both an entire **tech stack** and a sub-language **library set** (e.g., "C# stack"). Prefer "**stack**" for the whole architecture and "**library set**" or "**framework picks**" when discussing one language's choices.

- **"Sharing"** is overloaded:
  - A **Shared package** is a workspace package consumed by apps.
  - A **Shared Keycloak** is a single deployed instance reused across apps.
  - In **option D** of the UI strategy, components, navigation, and styling are explicitly **not** shared between web and mobile, while types, schemas, hooks, and design tokens **are** shared.
  - Always specify *what* is shared and *how* (code package vs. deployed instance vs. design surface).

- **"Hooks"** is overloaded:
  - **React hooks** (e.g., TanStack Query hooks in `packages/core`)
  - **Husky pre-commit hooks** (git hooks)
  - **Claude Code hooks** (settings.json automations)
  - Qualify when ambiguous: "React hooks", "git hooks", "Claude Code hooks".
