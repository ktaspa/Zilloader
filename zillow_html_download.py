import time
from playwright.sync_api import sync_playwright

def download_zillow_page(page, url):
    for i in range(3):
        response = page.goto(url, wait_until = 'domcontentloaded')
        if response.status == 404:
            return False

        if not page.title().startswith('75082'):
            page.close()
            time.sleep(3)
            page = browser.new_page(java_script_enabled = True)
            continue

        target_element = page.query_selector('//div[@id="search-page-list-container"]')
        for i in range(6):
            target_element.evaluate("element => element.scrollBy(0, 1000)")
            time.sleep(0.1)

        # time.sleep(2)
        with open(f'./html-exports/zillow_{city}-{state}-{zipc}_{page_num}.html', 'w', encoding= 'utf-8') as f:
            f.write(target_element.inner_html())
        print(f'Page {page_num} downloaded.')
        return True


playwright = sync_playwright().start()
browser = playwright.chromium.launch(
    headless = False,
    args = ["--disable-blink-features=AutomationControlled"]
)

city = 'Richardson'.replace(' ', '-')
state = 'TX'
zipc = '75082'

for page_num in range(1,4):
    page = browser.new_page(java_script_enabled=True)
    url = f'https://www.zillow.com/{city}-{state}-{zipc}/{page_num}_p'

    if not download_zillow_page(page, url):
        raise Exception('Page not found')

    page.close()
    time.sleep(3)

browser.close()
playwright.stop()




