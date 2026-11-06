# Optional Framework LED Matrix

Matrix hardware is opt-in: `./setup.sh all` and default audits exclude it.
On a machine with LED Matrix modules, run `./setup.sh matrix`; audit it explicitly
with `./check-setup.sh matrix`. `MATRIX_DIR` overrides the external checkout path.
Machines without the hardware need no checkout, service, or OpenCode integration.

`legacy-opencode/matrix.ts` preserves the old OpenCode V1 integration for reference.
It is deliberately outside the OpenCode Stow package: V2 cannot load V1 plugins.
Do not link it back into the active configuration without porting it to V2 first.
Re-running `./setup.sh opencode` also removes an old symlink to this repo's exact
former plugin path; unrelated custom plugins and real files are never deleted.
