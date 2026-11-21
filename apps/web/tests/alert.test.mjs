import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { test } from "node:test";
import vm from "node:vm";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";

const require = createRequire(import.meta.url);
const compiledModule = { exports: {} };
const source = ts.transpileModule(
  readFileSync(new URL("../src/components/ui/alert.tsx", import.meta.url), "utf8"),
  { compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX } },
).outputText;
vm.runInNewContext(source, {
  module: compiledModule,
  exports: compiledModule.exports,
  require(name) {
    if (name === "@/components/ui/paper") return { Paper: "section" };
    if (name === "@/lib/ink/react")
      return {
        useInk: () => ({ hostProps: {}, node: null }),
        useMergedRef: () => null,
      };
    if (name === "@/lib/ink/recipes/alert-ink") return { alertRecipe: {} };
    if (name === "@/lib/utils") return { cn: (...values) => values.filter(Boolean).join(" ") };
    return require(name);
  },
});

test("plain alert text occupies the content column instead of the zero-width icon column", () => {
  const html = renderToStaticMarkup(
    React.createElement(
      compiledModule.exports.Alert,
      { variant: "warning" },
      "The source verifier is temporarily unavailable. Try again later.",
    ),
  );
  assert.match(
    html,
    /<div class="col-start-2 min-w-0">The source verifier is temporarily unavailable\. Try again later\.<\/div>/,
  );
});
