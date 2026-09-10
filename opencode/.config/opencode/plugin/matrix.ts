import { mkdir, rename, rm, writeFile } from "node:fs/promises"
import { join } from "node:path"
import type { Plugin } from "@opencode-ai/plugin"

const sessionID = /^[A-Za-z0-9][A-Za-z0-9._-]*$/
const contextWindow = 400_000

function directory() {
  const runtime = process.env.XDG_RUNTIME_DIR
  return runtime ? join(runtime, "matrixd", "sessions") : undefined
}

async function writeSnapshot(id: string, payload: object) {
  const dir = directory()
  if (!dir || !sessionID.test(id) || id.includes("..")) return

  try {
    await mkdir(dir, { recursive: true })
    const target = join(dir, `${id}.json`)
    const temporary = join(dir, `.${id}.${crypto.randomUUID()}.tmp`)
    await writeFile(temporary, JSON.stringify(payload))
    await rename(temporary, target)
  } catch {
    // Matrix status is decorative; an unavailable runtime directory must not affect a session.
  }
}

async function writeState(id: string, state: "idle" | "working") {
  const dir = directory()
  if (!dir || !sessionID.test(id) || id.includes("..")) return

  try {
    await mkdir(dir, { recursive: true })
    await writeFile(join(dir, `${id}.state`), state)
  } catch {
    // Matrix status is decorative; an unavailable runtime directory must not affect a session.
  }
}

async function removeSession(id: string) {
  const dir = directory()
  if (!dir || !sessionID.test(id) || id.includes("..")) return

  try {
    await Promise.all([
      rm(join(dir, `${id}.json`), { force: true }),
      rm(join(dir, `${id}.state`), { force: true }),
    ])
  } catch {
    // Matrix status is decorative; an unavailable runtime directory must not affect a session.
  }
}

export default (async () => {
  return {
    event: async ({ event }) => {
      if (event.type === "session.created") {
        await writeSnapshot(event.properties.info.id, {
          context_window: { used_percentage: null },
        })
        await writeState(event.properties.info.id, "idle")
      }

      if (event.type === "session.status") {
        await writeState(
          event.properties.sessionID,
          event.properties.status.type === "busy" ? "working" : "idle",
        )
      }

      if (event.type === "session.idle") {
        await writeState(event.properties.sessionID, "idle")
      }

      if (event.type === "session.deleted") {
        await removeSession(event.properties.info.id)
      }

      if (event.type === "message.updated" && event.properties.info.role === "assistant") {
        const { info } = event.properties
        await writeSnapshot(info.sessionID, {
          context_window: {
            // OpenCode exposes the current request's input tokens, not exact context use.
            used_percentage: Math.min(100, (info.tokens.input / contextWindow) * 100),
          },
          model: { display_name: info.modelID },
        })
      }
    },
  }
}) satisfies Plugin
