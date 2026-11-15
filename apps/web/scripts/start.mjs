import { access, cp } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const project = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const server = resolve(project, ".next/standalone/apps/web");
try {
  await access(resolve(server, "server.js"));
} catch {
  throw new Error("Production output is missing. Run npm run build first.");
}
await cp(resolve(project, ".next/static"), resolve(server, ".next/static"), {
  recursive: true,
});
try {
  await access(resolve(project, "public"));
  await cp(resolve(project, "public"), resolve(server, "public"), {
    recursive: true,
  });
} catch (error) {
  if (error.code !== "ENOENT") throw error;
}
process.env.HOSTNAME = process.env.PEHCHAAN_WEB_HOST || "0.0.0.0";
process.env.PORT ||= "3000";
await import(pathToFileURL(resolve(server, "server.js")).href);
