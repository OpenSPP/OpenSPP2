import {execSync} from "child_process";
import * as path from "path";

const COMPOSE_CWD = path.resolve(__dirname, "..", "..");
const HEALTH_URL = `${process.env.ODOO_URL ?? "http://localhost:8069"}/web/health`;

export async function resetStack() {
  if (process.env.E2E_SKIP_STACK_RESET === "true") {
    // Running inside the e2e-runner container: docker-compose's
    // `depends_on: openspp: condition: service_healthy` already guarantees a
    // fresh, healthy stack before this container starts, and there's no
    // Docker CLI/socket in here to run `docker compose` against anyway.
    console.log("⏳ Waiting for Odoo to be healthy...");
    await waitForHealth();
    console.log("✅ Odoo is ready");
    return;
  }

  console.log("🔄 Tearing down stack and volumes...");
  execSync("docker compose --profile ui down -v", {stdio: "inherit", cwd: COMPOSE_CWD});

  console.log("🚀 Starting fresh stack...");
  execSync("docker compose --profile ui up -d --build", {
    stdio: "inherit",
    cwd: COMPOSE_CWD,
  });

  console.log("⏳ Waiting for Odoo to be healthy...");
  await waitForHealth();
  console.log("✅ Odoo is ready");
}

async function waitForHealth(retries = 30, intervalMs = 10_000) {
  for (let i = 1; i <= retries; i++) {
    try {
      const res = await fetch(HEALTH_URL);
      if (res.ok) return;
    } catch {}
    console.log(`  Health check ${i}/${retries} — retrying in ${intervalMs / 1000}s`);
    await new Promise((r) => setTimeout(r, intervalMs));
  }
  throw new Error("Odoo did not become healthy in time");
}
