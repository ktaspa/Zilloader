from pathlib import Path
from collections import namedtuple
from datetime import datetime
import re
import pandas as pd
import numpy as np
from bs4 import BeautifulSoup
from sklearn.neighbors import KNeighborsRegressor
import matplotlib.pyplot as plt
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

def build_search_url(city, state, zipcode, page_num):
    city_slug = slugify(city)
    if zipcode:
        return f'https://www.zillow.com/{city_slug}-{state}-{zipcode}/{page_num}_p/'
    return f'https://www.zillow.com/homes/{city_slug},-{state}_rb/{page_num}_p/'

def make_context(browser):
    return browser.new_context(
        java_script_enabled=True,
        user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        viewport={'width': 1440, 'height': 1800},
        locale='en-US'
    )

def download_pages(city, state, zipcode, max_pages=3):
    html_dir = Path('tmp_html')
    html_dir.mkdir(exist_ok=True)

    for file in html_dir.glob('*'):
        if file.is_file():
            file.unlink()

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=True,
            args=['--disable-blink-features=AutomationControlled', '--no-sandbox']
        )
        context = make_context(browser)

        for page_num in range(1, max_pages + 1):
            page = context.new_page()
            url = build_search_url(city, state, zipcode, page_num)
            print(f'Fetching URL: {url}')

            try:
                response = page.goto(url, wait_until='networkidle', timeout=90000)
            except Exception as e:
                print(f'Goto failed on page {page_num}: {e}')
                page.close()
                continue

            status = response.status if response else 'no response'
            title = page.title()
            print(f'Response status: {status}')
            print(f'Page title: {title}')

            page.wait_for_timeout(5000)

            for _ in range(10):
                page.mouse.wheel(0, 1800)
                page.wait_for_timeout(400)

            full_html = page.content()
            debug_file = html_dir / f'debug_{slugify(city)}_{state}_{zipcode}_{page_num}.html'
            debug_file.write_text(full_html, encoding='utf-8')

            target = (
                page.query_selector('div[id="search-page-list-container"]') or
                page.query_selector('div.List-c11n-8-84-3-photo-cards') or
                page.query_selector('div[class*="List-c11n"]') or
                page.query_selector('main')
            )

            print(f'Target found: {target is not None}')

            if target is not None:
                html = target.inner_html()
            else:
                html = full_html

            output = html_dir / f'zillow_{slugify(city)}_{state}_{zipcode}_{page_num}.html'
            output.write_text(html, encoding='utf-8')
            page.close()

        context.close()
        browser.close()

    return html_dir

def normalize_url(url):
    if not url:
        return ''
    if url.startswith('/'):
        return f'https://www.zillow.com{url}'
    return url

def parse_property_listing_info(article):
    price_element = article.find('span', {'data-test': 'property-card-price'})
    address_element = article.find('address', {'data-test': 'property-card-addr'})
    ul_element = article.find('ul')

    if address_element is None:
        address_element = article.find('address')

    if ul_element is None:
        ul_element = article.find('ul')

    if price_element is None:
        for span in article.find_all('span'):
            text = span.get_text(' ', strip=True)
            if '$' in text and re.search(r'\$\s*[\d,]+', text):
                price_element = span
                break

    if price_element is None or address_element is None or ul_element is None:
        return None

    price = clean_price(price_element.get_text(strip=True))
    address = address_element.get_text(' ', strip=True)

    link = article.find('a', href=True)
    url = normalize_url(link['href']) if link else ''

    features = [feature.get_text(' ', strip=True) for feature in ul_element.find_all('li')]
    features_text = ', '.join(features)

    parent_text = article.get_text(' ', strip=True)
    status = ''
    if '-' in parent_text:
        status = parent_text.split('-')[-1].strip()

    return PropertyDetail(price, address, features_text, status, url)

def parse_downloaded_html(html_dir):
    listings = []

    for html_file in sorted(html_dir.glob('zillow_*.html')):
        print(f'Parsing file: {html_file}')
        soup = BeautifulSoup(html_file.read_text(encoding='utf-8'), 'html.parser')

        articles = soup.find_all('article')
        print(f'Found articles: {len(articles)}')

        if not articles:
            cards = soup.select('[data-test="property-card"]')
            print(f'Found property cards: {len(cards)}')
            articles = cards

        for article in articles:
            property_info = parse_property_listing_info(article)
            if property_info is not None and property_info.price is not None:
                listings.append(property_info)

    df = pd.DataFrame(listings)

    if df.empty:
        return df

    df = df.drop_duplicates(subset=['address', 'price', 'url']).reset_index(drop=True)
    df['beds'] = df['features'].apply(extract_beds)
    df['baths'] = df['features'].apply(extract_baths)
    df['sqft'] = df['features'].apply(extract_sqft)
    df['price_per_sqft'] = df.apply(
        lambda row: row['price'] / row['sqft'] if pd.notna(row['sqft']) and row['sqft'] else np.nan,
        axis=1
    )

    return df

def build_model(df):
    model_df = df.dropna(subset=['price', 'sqft', 'beds', 'baths']).copy()

    if len(model_df) < 5:
        df['predicted_price'] = np.nan
        df['sigma_score'] = np.nan
        df['is_undervalued'] = False
        return df

    X = model_df[['sqft', 'beds', 'baths']]
    y = model_df['price']

    model = KNeighborsRegressor(n_neighbors=min(5, len(model_df)))
    model.fit(X, y)

    model_df['predicted_price'] = model.predict(X)
    residuals = model_df['price'] - model_df['predicted_price']
    sigma = residuals.std(ddof=0)

    if sigma == 0 or np.isnan(sigma):
        sigma = 1

    model_df['sigma_score'] = residuals / sigma
    model_df['is_undervalued'] = model_df['sigma_score'] <= -1.5

    df = df.merge(
        model_df[['address', 'predicted_price', 'sigma_score', 'is_undervalued']],
        on='address',
        how='left'
    )

    df['is_undervalued'] = df['is_undervalued'].fillna(False)
    return df

def save_excel(df, output_path):
    df.to_excel(output_path, index=False)

def save_chart(df, output_path, area_label):
    chart_df = df.dropna(subset=['price', 'sqft']).copy()

    plt.figure(figsize=(8, 5))
    plt.scatter(chart_df['sqft'], chart_df['price'])

    if not chart_df.empty and len(chart_df) >= 2:
        z = np.polyfit(chart_df['sqft'], chart_df['price'], 1)
        p = np.poly1d(z)
        x_line = np.linspace(chart_df['sqft'].min(), chart_df['sqft'].max(), 100)
        plt.plot(x_line, p(x_line))

    plt.xlabel('Square Feet')
    plt.ylabel('Price')
    plt.title(f'Zilloader Analysis: {area_label}')
    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()

def run_analysis(city, state, zipcode):
    html_dir = download_pages(city, state, zipcode)
    df = parse_downloaded_html(html_dir)

    if df.empty:
        return None

    df = build_model(df)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    out_dir = Path('outputs') / f'{zipcode}_{timestamp}'
    out_dir.mkdir(parents=True, exist_ok=True)

    csv_path = out_dir / 'zillow_properties.csv'
    excel_path = out_dir / 'zilloader_analysis.xlsx'
    chart_path = out_dir / 'chart.png'

    df.to_csv(csv_path, index=False)
    save_excel(df, excel_path)
    save_chart(df, chart_path, f'{city}, {state} {zipcode}')

    avg_price = float(df['price'].dropna().mean()) if not df['price'].dropna().empty else None
    avg_sqft = float(df['sqft'].dropna().mean()) if not df['sqft'].dropna().empty else None
    undervalued_count = int(df['is_undervalued'].sum()) if 'is_undervalued' in df.columns else 0

    top_undervalued = []
    if 'sigma_score' in df.columns:
        ranked = df.dropna(subset=['sigma_score']).sort_values('sigma_score')
        for _, row in ranked.head(5).iterrows():
            top_undervalued.append({
                'address': row['address'],
                'price': None if pd.isna(row['price']) else int(row['price']),
                'predicted_price': None if pd.isna(row.get('predicted_price')) else int(row['predicted_price']),
                'sigma_score': None if pd.isna(row.get('sigma_score')) else float(row['sigma_score']),
                'url': row['url']
            })

    return {
        'city': city,
        'state': state,
        'zipcode': zipcode,
        'listing_count': int(len(df)),
        'average_price': avg_price,
        'average_sqft': avg_sqft,
        'average_price_per_sqft': None if df['price_per_sqft'].dropna().empty else float(df['price_per_sqft'].dropna().mean()),
        'undervalued_count': undervalued_count,
        'top_undervalued': top_undervalued,
        'csv_file': str(csv_path).replace('\\', '/'),
        'excel_file': str(excel_path).replace('\\', '/'),
        'chart_file': str(chart_path).replace('\\', '/'),
        'generated_at': timestamp
    }