import argparse
import asyncio
import time
from dataclasses import dataclass
from pathlib import Path

import aiofiles
from logmagix import Loader, Logger, LogLevel
from patchright.async_api import BrowserContext, Page, async_playwright

from config import Config


@dataclass
class TurnstileResult:
    turnstile_value: str | None
    elapsed_time_seconds: float
    status: str
    reason: str | None = None


class AsyncTurnstileSolver:
    HTML_TEMPLATE = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <title>Turnstile Solver</title>
        <script
        src="https://challenges.cloudflare.com/turnstile/v0/api.js?onload=onloadTurnstileCallback"
        async=""
        defer=""
        ></script>
    </head>
    <body>
        <!-- cf turnstile -->
    </body>
    </html>
    """

    def __init__(self, debug: bool = False):
        self.debug = debug
        self.log = Logger(prefix="Enshteyn40", level=LogLevel.DEBUG if debug else LogLevel.INFO)
        self.loader = Loader(prefix="Enshteyn40", desc="Captcha yechayabman...", timeout=0.05)
        self.browser_args = [
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-background-networking",
            "--disable-background-timer-throttling",
            "--disable-backgrounding-occluded-windows",
            "--disable-renderer-backgrounding",
            "--window-position=2000,2000",
        ]

    async def _setup_page(self, context: BrowserContext, url: str, sitekey: str) -> Page:
        page = await context.new_page()
        url_with_slash = url + "/" if not url.endswith("/") else url

        if self.debug:
            self.log.debug(f"Navigating to URL: {url_with_slash}")

        turnstile_div = f'<div class="cf-turnstile" data-sitekey="{sitekey}"></div>'
        page_data = self.HTML_TEMPLATE.replace("<!-- cf turnstile -->", turnstile_div)

        await page.route(url_with_slash, lambda route: route.fulfill(body=page_data, status=200))
        await page.goto(url_with_slash)

        if self.debug:
            self.log.debug("Getting window dimensions.")
        page.window_width = await page.evaluate("window.innerWidth")
        page.window_height = await page.evaluate("window.innerHeight")

        return page

    async def _get_turnstile_response(self, page: Page, max_attempts: int = 10) -> str | None:
        attempts = 0

        if self.debug:
            self.log.debug("Starting Turnstile response retrieval loop.")

        while attempts < max_attempts:
            turnstile_check = await page.eval_on_selector("[name=cf-turnstile-response]", "el => el.value")

            if turnstile_check == "":
                if self.debug:
                    self.log.debug(f"Attempt {attempts + 1}: No Turnstile response yet.")

                await page.evaluate("document.querySelector('.cf-turnstile').style.width = '70px'")
                await page.click(".cf-turnstile")
                await asyncio.sleep(0.5)
                attempts += 1
            else:
                turnstile_element = await page.query_selector("[name=cf-turnstile-response]")
                if turnstile_element:
                    value = await turnstile_element.get_attribute("value")
                    if self.debug:
                        self.log.debug(f"Turnstile javob olindi: {value}")
                    return value
                break

        return None

    async def solve(self, url: str, sitekey: str, headless: bool = False) -> TurnstileResult:
        self.loader.start()
        start_time = time.time()

        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=headless, args=self.browser_args)
            context = await browser.new_context()

            try:
                page = await self._setup_page(context, url, sitekey)
                turnstile_value = await self._get_turnstile_response(page)

                elapsed_time = round(time.time() - start_time, 3)

                if not turnstile_value:
                    result = TurnstileResult(
                        turnstile_value=None,
                        elapsed_time_seconds=elapsed_time,
                        status="Muaffaqiyatsizlik",
                        reason="Token olinmasdan maksimal urinishlar soniga erishildi",
                    )
                    self.log.failure("Turnstile qiymati olinmadi")
                else:
                    result = TurnstileResult(
                        turnstile_value=turnstile_value,
                        elapsed_time_seconds=elapsed_time,
                        status="Muaffaqiyat",
                    )
                    self.log.message(
                        "Cloudflare",
                        f"Muvaffaqiyatli captcha yechildi: {turnstile_value[:45]}...",
                        start=start_time,
                        end=time.time(),
                    )

            finally:
                await context.close()
                await browser.close()
                self.loader.stop()

                if self.debug:
                    self.log.debug(f"Captcha yechish uchun ketgan vaqt: {result.elapsed_time_seconds}")
                    self.log.debug("Browser yopildi. Token qiymati qaytarildi.")

        return result


async def save_value(file: Path, value: str):
    mode = "a" if file.exists() else "w"
    async with aiofiles.open(file, mode=mode, encoding="utf-8") as f:
        await f.write(f"{value}\n")


async def get_turnstile_token(
    headless: bool = False,
    url: str = None,
    sitekey: str = None,
    out_file: Path = "tokens.txt",
) -> dict:
    solver = AsyncTurnstileSolver(debug=bool(Config.DEBUG_MODE))
    result = await solver.solve(url=url, sitekey=sitekey, headless=headless)
    if result.turnstile_value:
        await save_value(out_file, result.turnstile_value)

    return result.__dict__


async def main():
    import random
    await asyncio.sleep(random.uniform(0, 3))
    start_time = time.perf_counter()
    parser = argparse.ArgumentParser(description="Turnstile Token Generator")
    parser.add_argument("--headless", default=False, help="Run in headless mode")
    parser.add_argument("--url", type=str, default="https://randomgodbot.com", help="URL to solve Turnstile")
    parser.add_argument(
        "--sitekey",
        type=str,
        default="0x4AAAAAAA2AVdjVXiMwY1g-",
        help="Cloudflare sitekey",
    )
    parser.add_argument("-c", "--count", type=int, default=1, help="Number of tasks to run")
    parser.add_argument("-p", "--part", type=int, default=1, help="Part async tasks")
    parser.add_argument("-o", "--out", type=str, default="tokens.txt", help="Output file")

    args = parser.parse_args()
    out_file = Path(args.out)

    tasks = [
        get_turnstile_token(
            headless=args.headless,
            url=args.url,
            sitekey=args.sitekey,
            out_file=out_file,
        )
        for _ in range(args.count)
    ]

    chunk_size = args.part
    results = []

    for part in range(0, len(tasks), chunk_size):
        chunk = tasks[part : part + chunk_size]

        chunk_results = await asyncio.gather(*chunk)
        results.extend(chunk_results)

    elapsed_time = round(time.perf_counter() - start_time, 3)
    print(f"{len(results)} tokenlar  {args.out} ga saqlandi  {elapsed_time} - soniya ichida")


if __name__ == "__main__":
    asyncio.run(main())
