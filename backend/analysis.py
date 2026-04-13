from pathlib import Path
from collections import namedtuple
from io import BytesIO
from datetime import datetime
import re
import pandas as pd
import numpy as np
from bs4 import BeautifulSoup
from sklearn.neighbors import KNeighborsRegressor
import matplotlib.pyplot as plt
import openpyxl
from playwright.sync_api import sync_playwright

PropertyDetail = namedtuple('PropertyDetail', ['price', 'address', 'features', 'status', 'url'])


def slugify(value):
    return value.strip().replace(' ', '-')


def clean_price(value):
    if value is None:
        return None
    digits = re.sub(r'[^\d]', '', value)
    return int(digits) if digits else None


def extract_beds(features):
    match = re.search(r'(\d+(?:\.\d+)?)\s*bd', features.lower())
    return float(match.group(1)) if match else None


def extract_baths(features):
    match = re.search(r'(\d+(?:\.\d+)?)\s*ba', features.lower())
    return float(match.group(1)) if match else None


def extract_sqft(features):
    match = re.search(r'([\d,]+)\s*sqft', features.lower())
    return int(match.group(1).replace(',', '')) if match else None


def download_pages(city, state, zipcode, max_pages=3):
    html_dir = Path('tmp_html')
    html_dir.mkdir(exist_ok=True)
    for file in html_dir.glob('*.html'):
        file.unlink()

    city_slug = slugify(city)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, args=['--disable-blink-features=AutomationControlled'])

        for page_num in range(1, max_pages + 1):
            page = browser.new_page(java_script_enabled=True)
            url = f'https://www.zillow.com/{city_slug}-{state}-{zipcode}/{page_num}_p/'
            response = page.goto(url, wait_until='domcontentloaded', timeout=60000)

            if response is None or response.status == 404:
                page.close()
                break

            page.wait_for_timeout(3000)
            target = page.query_selector('div[id="search-page-list-container"]')
            if target is None:
                page.close()
                continue

            for _ in range(8):
                target.evaluate('element => element.scrollBy(0, 1200)')
                page.wait_for_timeout(250)

            html = target.inner_html()
            output = html_dir / f'zillow_{city_slug}_{state}_{zipcode}_{page_num}.html'
            output.write_text(html, encoding='utf-8')
            page.close()
    return summary