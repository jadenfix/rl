import { compileFromFile } from "json-schema-to-typescript";
import { writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const repoRoot = resolve(__dirname, "../..", "..");

const schemas = [
  {
    name: "InteractionCreateEvent",
    file: resolve(repoRoot, "config/schemas/events/interaction_create.json"),
  },
  {
    name: "InteractionOutputEvent",
    file: resolve(repoRoot, "config/schemas/events/interaction_output.json"),
  },
  {
    name: "FeedbackSubmitEvent",
    file: resolve(repoRoot, "config/schemas/events/feedback_submit.json"),
  },
  {
    name: "TaskResultEvent",
    file: resolve(repoRoot, "config/schemas/events/task_result.json"),
  },
];

const header = `/* tslint:disable */\n/* eslint-disable */\n// This file is auto-generated via npm run generate:types. Do not edit manually.\n\n`;

let output = header;

for (const schema of schemas) {
  const ts = await compileFromFile(schema.file, {
    bannerComment: "",
    additionalProperties: false,
  });
  output += ts.replace("export interface", "export interface");
  output += "\n";
}

const target = resolve(__dirname, "../src/generated/events.ts");
await writeFile(target, output, "utf8");
console.log(`Wrote ${target}`);
