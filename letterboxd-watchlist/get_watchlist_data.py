import asyncio
import aiohttp
from bs4 import BeautifulSoup
import pandas as pd
import time

import warnings
warnings.filterwarnings("ignore")



async def get_movie_stats(session: aiohttp.ClientSession, data_film_slug: str):
    movie_url = f"https://letterboxd.com/film/{data_film_slug}/"

    async with session.get(movie_url) as response:
        if response.status != 200:
            print(f"ERROR: Failed to retrieve movie stats for {data_film_slug}.")
            return None

        html = await response.text()
        soup = BeautifulSoup(html, 'html.parser')

        director_tag = soup.find('meta', {'name': 'twitter:data1'})
        rating_tag = soup.find('meta', {'name': 'twitter:data2'})
        og_title_tag = soup.find('meta', {'property': 'og:title'})
        duration_tag = soup.find('p', class_='text-link text-footer')
        genre_header = soup.find(lambda tag: tag.name == 'h3' and (tag.text == 'Genre' or tag.text == 'Genres'))

        title = og_title_tag.get('content').split('(')[0] if og_title_tag else None
        director = director_tag.get('content') if director_tag else None
        rating = float(rating_tag.get('content').split(' ')[0]) if rating_tag else None
        year = og_title_tag.get('content').split('(')[-1].strip(')') if og_title_tag else None
        duration = duration_tag.text.strip().split()[0] if duration_tag else None

        if not genre_header:
            genres = None
        else:
            genre_div = genre_header.find_next('div', class_='text-sluglist')
            genres = ', '.join(a.text for a in genre_div.find_all('a', class_='text-slug'))

        return title, director, rating, genres, year, duration


# --- Fetching multiple films concurrently ---
async def get_multiple_movie_stats(slugs: list[str]):
    async with aiohttp.ClientSession() as session:
        tasks = [get_movie_stats(session, slug) for slug in slugs]
        return await asyncio.gather(*tasks)
    
def results_to_df(results: list[tuple]):
    df = pd.DataFrame(results, columns=['Title', 'Director', 'Rating','Genres', 'Year', 'Duration'])
    return df

if __name__ == "__main__":
    username = "gfajardo555"
    df = pd.read_csv(f"{username}_watchlist.csv")
    film_slugs = df["film-slug"].tolist()
    film_slugs = film_slugs[:5]  # Limit to first 5 films for testing
    print(f"Fetching stats for {len(film_slugs)} films...")
    print(f"Film slugs: {film_slugs}")
    print("\n\n")

    start_time = time.time()
    results = asyncio.run(get_multiple_movie_stats(film_slugs))
    end_time = time.time()

    for slug, stats in zip(film_slugs, results):
        print(f"Stats for {slug}: {stats}")

    print(f"\nResults: {results}")

    # save df
    df = results_to_df(results)
    df.to_csv(f"{username}_watchlist_film_stats.csv", index=False)
    print(f"\nSaved film stats to {username}_watchlist_film_stats.csv")
    

    print(f"Time taken to fetch stats for {len(film_slugs)} films: {end_time - start_time:.2f} seconds")