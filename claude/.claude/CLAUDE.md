# Global Preferences

This file is the user's **always-on** baseline preferences. It is loaded into every Claude Code session and applies across **all projects, existing and future**.

## Authority order (highest → lowest)

1. Explicit user instruction in the current conversation
2. Per-project `CLAUDE.md` in the working directory
3. Existing project conventions (codebase patterns, dependencies in use)
4. **This global file**

When (3) conflicts with (4): match the project's existing conventions and **flag the drift once per session** ("this project uses Redux instead of the global default Jotai — sticking with Redux for consistency"). Do not flag it again in the same session.

When (2) conflicts with (4): trust the project file silently for execution, but **flag the conflict once** so the user can confirm it's intentional.

When (1) conflicts with anything: comply with the user, but if they're asking for something that contradicts (4), **flag once** ("global rule says X, you're asking for Y — going with Y; flagging in case it was unintentional"). User intent always wins.

## Conditional-rule convention

Every section below names its **trigger** explicitly. Do not apply a section's rules unless its trigger is satisfied. A Python script does not get the TypeScript rules. A backend-only repo does not get the Expo rules.

---

## General development principles

**Trigger**: always.

- **Pragmatic functional programming.** Default to immutability, pure functions, and discriminated unions over class hierarchies. Composition over inheritance. No classes for business logic — use plain records/objects + functions.
- **Do not introduce `fp-ts` or `Effect-TS`** unless the project is already using them. Pragmatic FP, not library-driven FP.
- **Naming**: explicit beats short. `userIdsByOrgId` not `m`. The name is the documentation.
- **Comments**: default to none. Add a comment **only** when the *why* is non-obvious — workarounds for specific bugs, hidden constraints, invariants the type system can't express. Never explain what well-named code already says.
- **Don't add fallbacks for can't-happen scenarios.** Trust internal code. Validate only at system boundaries (user input, external APIs).
- **Don't add error handling that just rethrows or logs-and-rethrows.** Let exceptions propagate to a single boundary (HTTP handler, message handler) where they're translated.

---

## TypeScript — shared rules

**Trigger**: any `.ts` / `.tsx` file.

### Strictness (in `tsconfig.json`)

```json
{
  "compilerOptions": {
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "exactOptionalPropertyTypes": true,
    "noImplicitOverride": true
  }
}
```

### Default libraries (reach for these first)

- **`neverthrow`** for `Result<T, E>` — never throw from domain logic
- **`ts-pattern`** for matching on discriminated unions (exhaustiveness checked)
- **`Remeda`** for data utilities (`groupBy`, `partition`, `pipe`, etc.) — TS-first, immutable, tree-shakeable. Do **not** use `lodash/fp`.
- **`Zod`** for runtime validation; schemas live in `packages/core` and are the source of truth for both validation and inferred TS types

### Linter / formatter

- **Biome** as the single tool (replaces ESLint + Prettier). One config file, one binary, one mental model.

---

## Web — Next.js

**Trigger**: `apps/web/`, `next.config.*`, or any project using Next.js.

- **Next.js App Router**. Not Pages Router.
- **RSC + Server Actions for reads** where it fits; **TanStack Query for client mutations and refetches**.
- **Tailwind** for styling, consuming tokens from `packages/design-tokens` via a shared `tailwind.config`.
- **TanStack Query** for server state — hooks live in `packages/core` and are imported.
- **TanStack Form + Zod** for forms.

---

## Mobile — Expo

**Trigger**: `apps/mobile/`, `app.json`/`app.config.*`, or any Expo / React Native project.

- **Expo managed workflow**. Use **Expo Modules** or **config plugins** for native escapes; never drop to bare React Native unless there's a specific blocker that Expo cannot accommodate.
- **Expo Router** (file-based, mirrors Next App Router conventions).
- **NativeWind** for styling, sharing the **same `tailwind.config`** as web (consumes `packages/design-tokens`).
- **TanStack Query** for server state — same hooks as web, imported from `packages/core`.
- **TanStack Form + Zod** for forms.
- **`expo-auth-session`** for OIDC against the shared Keycloak.

---

## Monorepo layout

**Trigger**: when scaffolding a new product, or any project with both `apps/web` and `apps/mobile`.

- **pnpm + Turborepo.**
- Layout:
  ```
  apps/
    web/         # Next.js App Router
    mobile/     # Expo + Expo Router
  packages/
    core/        # types, Zod schemas, orval-generated API client, pure logic, TanStack Query hooks
    design-tokens/  # colors, spacing, typography (raw values) + shared tailwind.config
  ```
- **Shared in `packages/core`**: TypeScript types, Zod schemas, generated API client, domain logic (pure functions), data hooks built on TanStack Query (no DOM/RN APIs).
- **Shared in `packages/design-tokens`**: design tokens as raw values + the `tailwind.config` consumed by both apps.
- **Not shared**: components, navigation, styling beyond tokens. Web and mobile UIs are intentionally platform-idiomatic.

---

## .NET — C\#

**Trigger**: when SDK / framework integration makes C# the right choice (Azure SDKs, Roslyn analyzers, MAUI/Unity, complex ASP.NET conventions). **C# is the fallback, not the default.**

- **ASP.NET Core Minimal APIs** — not MVC Controllers.
- **EF Core** for ORM-heavy work; **Dapper** for thin data access where SQL is more honest.
- **Built-in DI only.** No Autofac, no Lamar.
- **System.Text.Json**, **Serilog** (structured JSON to stdout), **Refit** for typed HTTP clients.
- **Tests**: xUnit + FluentAssertions + NSubstitute + **Testcontainers** (real Postgres).
- **Avoid**:
  - **MediatR** (paid since 2024) — request/response handlers are just function composition; do it explicitly.
  - **AutoMapper** (paid since 2024) — write explicit mapping functions; FP-friendlier and Claude can write them quickly.
  - **Moq** — telemetry scandal in 2023. Use **NSubstitute**.
  - **Newtonsoft.Json** — use System.Text.Json unless interoperating with legacy code.

### Project-file strictness (in every `.csproj`)

```xml
<PropertyGroup>
  <Nullable>enable</Nullable>
  <TreatWarningsAsErrors>true</TreatWarningsAsErrors>
  <AnalysisLevel>latest</AnalysisLevel>
  <EnforceCodeStyleInBuild>true</EnforceCodeStyleInBuild>
</PropertyGroup>
```

---

## .NET — F\#

**Trigger**: greenfield services where pure business logic and HTTP dominate. **F# is the default for new backends.**

- **Giraffe** on ASP.NET Core (not Saturn — its MVC scaffolding fights FP; not Falco — smaller community).
- **Dapper.FSharp** for data access. Use EF Core only when a heavy ORM is genuinely required (and accept the friction with F# records).
- **`FsToolkit.ErrorHandling`** for `result { }` / `option { }` / `asyncResult { }` computation expressions — the F# equivalent of `neverthrow`.
- **`Validus`** for composable validation returning `Result`.
- **`FSharp.SystemTextJson`** so we share one JSON runtime with C# code.
- **Tests**: Expecto + FsCheck + Unquote + Testcontainers.
- **OpenAPI**: **Giraffe.OpenApi** for spec generation.
- Same project-file strictness flags as C#.

---

## API contracts

**Trigger**: any HTTP API.

- **Server is the source of truth.** Expose **OpenAPI** via NSwag (C#) or Giraffe.OpenApi (F#).
- **TS client**: **`orval`** generates types **and** TanStack Query hooks. Output lands in `packages/core/src/api/generated/`.
- Codegen runs in **CI** (and in pre-commit if it stays under the 5-second budget).
- **Carve-outs**:
  - **Streaming / real-time** → **SignalR** (.NET-native). Do not reach for gRPC streaming or GraphQL subscriptions for this.
  - **Internal service-to-service .NET ↔ .NET** → **gRPC** is fine here, since both ends are .NET and there's no browser tax.
- **Do not introduce GraphQL.** Do not introduce hand-rolled type-sharing schemes (manual JSON-Schema → F#/C# codegen).

---

## Infrastructure — Cloudflare-first

**Trigger**: any new project (default infra). Per-project `CLAUDE.md` may override for specific projects that have outgrown this tier.

| Layer | Tool |
|---|---|
| Static web | **Cloudflare Pages** |
| Edge logic (TS only) | **Cloudflare Workers** |
| .NET backends | **Cloudflare Containers** |
| Postgres | **Neon** via **Cloudflare Hyperdrive** |
| Object storage | **Cloudflare R2** (zero egress fees) |
| KV / Queues / Durable Objects | Cloudflare equivalents |
| DNS / CDN | Cloudflare |
| Local dev | **Docker Compose** |
| IaC | **Terraform** (Cloudflare + Neon + Keycloak providers) |
| CI/CD | **GitHub Actions** |

- **No Kubernetes, no AWS, no Fly.io in the default stack.** If a project genuinely outgrows the hobby tier, the user evaluates AWS/EKS or alternative hosts on a per-project basis. **Do not propose AWS/K8s solutions globally.**
- **Single database engine: Postgres (Neon).** Do not use D1 unless the project is **Workers-only with no container backend** — that's the only case D1 wins.
- **All services containerized with Docker** (multi-stage builds, `mcr.microsoft.com/dotnet/aspnet` runtime, non-root user).
- **All infrastructure in Terraform.** Layout: `modules/` for reusable components, `environments/{dev,prod}/` composing modules. Remote state in Cloudflare R2 + a lock provider.

### Cold starts on Cloudflare Containers

- Default: **accept ~1–3s cold starts.** Don't pre-optimize.
- For cold-start-sensitive services (webhook receivers, auth callbacks, low-traffic user-facing endpoints), pick **one** of, in this order:
  1. Configure `min-instances ≥ 1` (paid, keeps the container warm)
  2. Add `<PublishReadyToRun>true</PublishReadyToRun>` — small build flag, ~50% improvement, near-zero compatibility risk
  3. NativeAOT — **only after** measuring AND verifying all dependencies (especially EF Core, F# libraries) support it

---

## Authentication

**Trigger**: any auth need.

- **One shared Keycloak instance** running on Cloudflare Containers. **Single realm** (`personal`) shared across all projects.
- **Each app = one OIDC client** in the shared realm.
- **No per-project Keycloak deployments.** If a project genuinely needs an isolated identity provider (rare), document it and deploy its own — but flag this as a deviation from the default.
- **Frontends**:
  - Next.js: **`Auth.js`** (NextAuth) with the Keycloak provider, or **`oidc-client-ts`** directly
  - Expo: **`expo-auth-session`** configured for Keycloak's OIDC endpoints
- **Backends** (C# Minimal APIs and F# Giraffe both): `AddJwtBearer` with the Keycloak issuer URL and JWKS endpoint. Validate `aud`, `iss`, and any role claims required by the endpoint.
- **Per-app branding**: build login themes with **Keycloakify** — write the login UI as React components consuming `packages/design-tokens`, compile to a Keycloak theme JAR, mount into the shared Keycloak. Set `loginTheme = "<app-name>"` on each OIDC client.

---

## Testing

**Trigger**: any non-trivial code change.

- **Strict TDD by default.** Write the failing test first, confirm it fails for the **expected** reason, implement to pass, refactor.
  - Run the failing test in the conversation. Surface the output **only if** it failed for an unexpected reason (compile error, wrong setup, missing import). Otherwise just say "test fails as expected — implementing."
  - Exceptions: typos, renames, throwaway spike code (must be marked as a spike).
- **Test stacks**:
  - TS: **Vitest + React Testing Library + Playwright** (e2e)
  - C#: **xUnit + FluentAssertions + NSubstitute**
  - F#: **Expecto + FsCheck + Unquote**
- **Testcontainers everywhere.** Integration tests hit a **real Postgres** in a throwaway container. **Never mock the database.** Mocked DBs hide migration failures and SQL bugs.
- **Mock external HTTP only at the system boundary.** A `IPaymentClient` interface gets mocked; an arbitrary internal function does not.
- **Coverage is not a target.** Tests exist to make changes safe; coverage percentages are an output, not a goal.

---

## Observability

**Trigger**: any deployed service.

**Cloudflare-native only** at the global level:

- **Logs**: structured JSON to stdout. For .NET use Serilog with `WriteTo.Console(new RenderedCompactJsonFormatter())`. Cloudflare captures Worker Logs and Container Logs automatically. Use **Logpush → R2** for long-term retention.
- **Metrics**: Cloudflare's built-in Workers / Containers analytics dashboards.

**Anything beyond Cloudflare** (Sentry, Axiom, OpenTelemetry tracing, alerting, APM, error grouping) is a **per-project decision**, not a global default. Set it up when a specific project earns the complexity.

---

## Code quality

**Trigger**: any project.

### TypeScript

- **Biome** for lint + format (one tool, one config).
- Strictness flags as listed in the TS section.

### .NET

- Strictness flags as listed in the C# section.
- Shared `.editorconfig` at the repo root. Starter:

```ini
root = true

[*]
indent_style = space
indent_size = 4
end_of_line = lf
charset = utf-8
trim_trailing_whitespace = true
insert_final_newline = true

[*.{ts,tsx,js,jsx,json,yml,yaml}]
indent_size = 2

[*.{cs,fs,fsx}]
# FP-friendly C# style preferences
csharp_style_pattern_matching_over_is_with_cast_check = true:warning
csharp_style_pattern_matching_over_as_with_null_check = true:warning
csharp_style_prefer_switch_expression = true:warning
csharp_style_prefer_pattern_matching = true:warning
csharp_style_var_when_type_is_apparent = true:warning
csharp_style_expression_bodied_methods = when_on_single_line:suggestion
dotnet_style_prefer_inferred_tuple_names = true:warning
dotnet_style_prefer_collection_expression = true:warning
```

### Pre-commit hooks

- **Husky + lint-staged** for TS (Biome on staged files).
- **`dotnet format`** on staged .NET files.
- **Hard budget: pre-commit must finish in under 5 seconds.** Lint staged files only. Run full typecheck and tests in **CI**, never in pre-commit. A pre-commit hook the user skips is worse than no hook.

---

## Git workflow

**Trigger**: any git operation.

- **Conventional Commits.** Every commit. Format: `type(scope): subject`. Types: `feat`, `fix`, `chore`, `docs`, `test`, `refactor`, `perf`, `build`, `ci`.
- **Trunk-based development.** Short-lived branches. Direct commits to `main` are allowed for solo work **as long as CI passes**.
- **Merge commits only.** Never squash-merge. Never rebase-merge. Every individual commit on a branch is preserved verbatim when merged.
- **Once pushed, history is sacred.** Never force-push to a branch that has been pushed to a shared remote (`origin/main`, `origin/feature-x`, etc.).
- **Pre-push local commits**: `git commit --amend` and interactive rebase are fine for cleanup *before the first push*. Once pushed, stop rewriting.
- **Every commit must compile, pass tests, and have a Conventional Commits message describing one logical change.** No "WIP" / "save point" / "fix typo" commits — they end up in `main` forever. Stage and commit atomically as you go.

### History rewrite — security exception only

- Permitted **only** to scrub accidentally-committed secrets (API keys, passwords, tokens, PII).
- Use `git filter-repo` (not the deprecated `filter-branch`).
- Force-push the rewritten branch and notify all collaborators to reset their local clones.
- **Rotate the leaked secret immediately and assume it's already exposed.** Public Git history is scraped within minutes — the scrub protects future commits, not past exposure.
- This is incident response, not normal workflow. Never invoke this for "I made a sloppy commit."

---

## Claude behavioral rules

- **Ambiguity threshold**: if making the wrong choice would cost more than ~5 minutes to undo, **ask before acting**. Otherwise, pick the better option, **state which one and why**, and proceed.
- **User vs. global rule conflict**: flag the conflict once ("global rule says X, you're asking for Y — going with Y; flagging in case it was unintentional"), then comply with the user. **User intent always wins.**
- **Existing project drift**: when the project's existing conventions contradict this global file, match the project's conventions and flag the drift **once per session**.
- **Per-project `CLAUDE.md`**: when a project has non-obvious patterns that extend or contradict this global file, **proactively suggest creating or extending a project-level `CLAUDE.md`** so the next session inherits the context.
- **Commits**: one commit per atomic step. Each commit compiles and passes tests. This pairs with the no-squash rule — commits are forever.
- **Security**: never disable signing, never bypass hooks (`--no-verify`), never weaken auth requirements without explicit user instruction citing the reason.

---

## Documentation

**Trigger**: project complexity warrants.

- **ADRs** (Architecture Decision Records): maintain `docs/adr/` only when a project has **≥ 2 non-obvious architectural decisions**. Use the **Nygard format**: Context / Decision / Consequences. Number sequentially (`0001-use-cloudflare-containers.md`).
- **No `CHANGELOG.md`.** All projects deploy on push to `main`. The git log + Conventional Commits **is** the changelog.
- **`README.md`** is minimal: what the project is, how to run it locally, how to deploy. Do not write multi-page READMEs for hobby projects.
