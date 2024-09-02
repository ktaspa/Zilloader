from datetime import datetime
from collections import namedtuple
from pathlib import Path
import pandas as pd
from bs4 import BeautifulSoup
PropertyDetail = namedtuple('PropertyDetail', ['price', 'address', 'features', 'is_active', 'url'])

def parse_property_listing_info(article):
    # Locate proeprty price and address
    price = article.find('span', {'data-test':'property-card-price'}).text.replace('$', '').replace(',', '')
    address = article.find('address', {'data-test': 'property-card-addr'}).text
    url = article.find('address', {'data-test': 'property-card-addr'}).parent['href']
    zestimate = article.find('')
    # Locate property features
    features = [feature.text for feature in article.find('ul').find_all('li')]
    features_text = ', '.join(features)

    # Locate property status
    parent_element = article.find('ul').parent
    text = parent_element.get_text(strip=True)
    status = text.split('-')[-1].strip()

    property_detail = PropertyDetail(price, address, features_text, status, url)
    return property_detail  


def main():
    html_dir = Path('./html-exports')
    html_files = html_dir.glob('*.html')

    property_listing = []

    html_file = next(html_files, None)

    while html_file is not None:
        print(f'Processing file {html_file}')
        with open(html_file, 'r', encoding='utf-8') as f:
            soup = BeautifulSoup(f, 'html.parser')

        property_article_elements = soup.find_all('article')

        for article_element in property_article_elements:
            property_info = parse_property_listing_info(article_element)
            property_listing.append(property_info)

        html_file = next(html_files, None)

    #timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    df = pd.DataFrame(property_listing)
    df.to_csv(f'zillow_properties.csv', index=False)

main()


