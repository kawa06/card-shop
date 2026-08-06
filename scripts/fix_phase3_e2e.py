from pathlib import Path

p = Path(__file__).resolve().parents[1] / "frontend" / "e2e" / "phase3-live.spec.ts"
t = p.read_text(encoding="utf-8")
t = t.replace(
    "await expect(page.locator('h1')).toContainText('\\u914d\\u4fe1')",
    "await expect(page.getByRole('heading', { name: '\\u30e9\\u30a4\\u30u6配信\\u7ba1\\u7406' })).toBeVisible({ timeout: 90_000 })",
)
t = t.replace("\\u30e9\\u30a4\\u30u6", "\\u30e9\\u30a4\\u30d6")
p.write_text(t, encoding="utf-8", newline="\n")
print("ok")
