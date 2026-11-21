import { expect, test } from "@playwright/test";

const DEFAULT_BASE_URL = "https://paisaproof.vercel.app";
const DEFAULT_API_BASE_URL = "https://aadha-ps.onrender.com";

function getBaseUrl(): string {
  return (process.env.BASE_URL?.trim() || DEFAULT_BASE_URL).replace(/\/+$/, "");
}

function getApiHealthUrl(): string {
  const raw =
    process.env.API_BASE_URL?.trim() || process.env.API_URL?.trim() || DEFAULT_API_BASE_URL;
  const origin = raw.replace(/\/+$/, "").replace(/\/api\/v1$/, "");
  return `${origin}/api/v1/health`;
}

function isFaviconConsoleError(text: string, locationUrl: string | undefined): boolean {
  return /favicon/i.test(text) || /favicon/i.test(locationUrl ?? "");
}

test.describe("Production read-only smoke suite", () => {
  test("landing sign-in screen renders email + Google button without unexpected console errors", async ({
    page,
  }) => {
    const consoleErrors: string[] = [];
    const pageErrors: string[] = [];

    page.on("console", (msg) => {
      if (msg.type() !== "error") return;
      const text = msg.text();
      const locUrl = msg.location()?.url;
      if (isFaviconConsoleError(text, locUrl)) return;
      consoleErrors.push(locUrl ? `${text} (${locUrl})` : text);
    });

    page.on("pageerror", (err) => {
      pageErrors.push(err.message);
    });

    const response = await page.goto(getBaseUrl(), { waitUntil: "domcontentloaded" });
    expect(response, "Landing page should return an HTTP response").not.toBeNull();
    expect(response!.status()).toBeLessThan(400);

    const emailInput = page.locator('input[type="email"]').first();
    const googleButton = page.getByRole("button", { name: /sign in with google/i });

    await expect(emailInput).toBeVisible({ timeout: 20_000 });
    await expect(googleButton).toBeVisible({ timeout: 20_000 });

    await page.waitForTimeout(500);

    expect(pageErrors, `Unexpected uncaught page errors: ${pageErrors.join("; ")}`).toEqual([]);
    expect(consoleErrors, `Unexpected console errors: ${consoleErrors.join("; ")}`).toEqual([]);
  });

  for (const viewport of [
    { width: 390, height: 844 },
    { width: 1440, height: 900 },
  ]) {
    test(`no horizontal overflow at ${viewport.width}px viewport`, async ({ page }) => {
      await page.setViewportSize(viewport);
      const response = await page.goto(getBaseUrl(), { waitUntil: "domcontentloaded" });
      expect(response, "Landing page should return an HTTP response").not.toBeNull();
      expect(response!.status()).toBeLessThan(400);

      await expect(
        page.getByRole("button", { name: /sign in with google/i }),
      ).toBeVisible({ timeout: 20_000 });

      const metrics = await page.evaluate(() => ({
        scrollWidth: document.documentElement.scrollWidth,
        clientWidth: document.documentElement.clientWidth,
      }));

      expect(
        metrics.scrollWidth,
        `Horizontal overflow detected at ${viewport.width}px: scrollWidth=${metrics.scrollWidth} > clientWidth=${metrics.clientWidth}`,
      ).toBeLessThanOrEqual(metrics.clientWidth);
    });
  }

  test("GET {API}/api/v1/health returns ok", async ({ request }) => {
    const healthUrl = getApiHealthUrl();
    const retryableStatuses = new Set([502, 503, 504]);
    let lastStatus = 0;
    let lastError = "";

    for (let attempt = 1; attempt <= 3; attempt += 1) {
      try {
        const res = await request.get(healthUrl, { timeout: 45_000 });
        lastStatus = res.status();
        if (lastStatus === 200) {
          const body = (await res.json()) as { status?: string; db?: string };
          expect(body.status).toBe("ok");
          expect(body.db).toBe("ok");
          return;
        }
        lastError = `HTTP ${lastStatus}: ${await res.text()}`;
        if (!retryableStatuses.has(lastStatus) || attempt === 3) {
          break;
        }
      } catch (err) {
        lastError = err instanceof Error ? err.message : String(err);
        if (attempt === 3) break;
      }
      await new Promise((resolve) => setTimeout(resolve, 5_000));
    }

    throw new Error(`Health check failed for ${healthUrl} (status=${lastStatus}): ${lastError}`);
  });
});
