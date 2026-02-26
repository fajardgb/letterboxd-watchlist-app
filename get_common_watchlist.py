import asyncio
import aiohttp
from bs4 import BeautifulSoup
import pandas as pd
import time

import warnings
warnings.filterwarnings("ignore")


async def fetch_page(session, url):
    """
    Asynchronously fetch a page.

    Args:
        session: aiohttp ClientSession
        url (str): URL to fetch

    Returns:
        str: HTML content of the page

    Raises:
        ValueError: If the page cannot be fetched
    """
    async with session.get(url) as response:
        if response.status != 200:
            raise ValueError(
                f"ERROR: Unable to fetch page: {url}. HTTP status code: {response.status}"
            )
        return await response.text()


async def get_watchlist_count(session, username):
    """
    Get number of films in a user's watchlist (async version).

    Args:
        session: aiohttp ClientSession
        username (str): Letterboxd username

    Raises:
        ValueError: If the page cannot be fetched or parsed
        ValueError: If the watchlist count element is not found
        ValueError: If the watchlist count cannot be parsed

    Returns:
        watchlist_count (int): Number of films in the user's watchlist
        num_pages (int): Number of pages in the user's watchlist
    """
    page_url = f"https://letterboxd.com/{username}/watchlist/"
    html = await fetch_page(session, page_url)

    # get soup object
    soup = BeautifulSoup(html, "html.parser")

    # find the watchlist count element
    watchlist_count_element = soup.find("span", class_="js-watchlist-count")
    if not watchlist_count_element:
        raise ValueError(f"ERROR: Could not find watchlist count for user {username}.")

    # get number of total films in watchlist
    try:
        watchlist_count = int(watchlist_count_element.text.strip().split()[0])
    except (ValueError, IndexError) as e:
        raise ValueError(
            f"ERROR: Unable to parse watchlist count for user {username}."
        ) from e

    # cheap way to find number of pages:
    # there are up to 28 films per page
    # so we can calculate the number of pages from the count
    # needs to be more flexible in the future if Letterboxd changes this number
    num_pages = (watchlist_count + 27) // 28  # integer division rounding up

    return watchlist_count, num_pages


async def get_film_slugs_from_html(html):
    """
    Get film titles (slugs) from HTML content.

    Args:
        html (str): HTML content of the watchlist page

    Returns:
        list: A list of film slugs (str) found on the page
    """
    soup = BeautifulSoup(html, "html.parser")
    elements = soup.find_all(attrs={"data-item-slug": True})
    slugs = [element.get("data-item-slug") for element in elements]
    return slugs


async def fetch_page_slugs(session, page_url, semaphore):
    """
    Fetch film slugs from a single page with rate limiting.

    Args:
        session: aiohttp ClientSession
        page_url (str): URL of the watchlist page
        semaphore: asyncio.Semaphore for rate limiting

    Returns:
        list: Film slugs from the page
    """
    async with semaphore:
        try:
            html = await fetch_page(session, page_url)
            slugs = await get_film_slugs_from_html(html)
            # Small delay to be polite to the server
            await asyncio.sleep(2)
            return slugs
        except ValueError as e:
            print(e)
            return []


async def get_full_watchlist(session, username, num_pages, max_concurrent=5):
    """
    Get the full watchlist for a user asynchronously.

    Args:
        session: aiohttp ClientSession
        username (str): Letterboxd username
        num_pages (int): Number of pages in the user's watchlist
        max_concurrent (int): Maximum number of concurrent requests (default: 5)

    Returns:
        list: A list of film slugs (str) in the user's watchlist
    """
    # Create a semaphore to limit concurrent requests
    semaphore = asyncio.Semaphore(max_concurrent)

    # Generate all page URLs
    page_urls = [f"https://letterboxd.com/{username}/watchlist/"] # first page - has no page number in URL
    page_urls.extend(
        [
            f"https://letterboxd.com/{username}/watchlist/page/{page}/"
            for page in range(2, num_pages + 1)
        ]
    )

    # Fetch all pages concurrently
    tasks = [fetch_page_slugs(session, url, semaphore) for url in page_urls]
    results = await asyncio.gather(*tasks)

    # Flatten the list of lists
    watchlist = [slug for page_slugs in results for slug in page_slugs]
    return watchlist

def list_to_df(film_list):
    """
    Convert a list of film slugs to a pandas DataFrame.

    Args:
        film_list (list): List of film slugs

    Returns:
        pd.DataFrame: DataFrame with a single column 'film-slug' containing the film slugs
    """
    return pd.DataFrame(film_list, columns=["film-slug"])


async def get_user_watchlist(username, max_concurrent=5):
    """
    Main function to get a user's complete watchlist.

    Args:
        username (str): Letterboxd username
        max_concurrent (int): Maximum number of concurrent requests

    Returns:
        dict: Dictionary containing watchlist info and films
    """
    async with aiohttp.ClientSession() as session:
        try:
            # Fetch metadata
            watchlist_count, num_pages = await get_watchlist_count(session, username)

            # Fetch all films
            full_watchlist = await get_full_watchlist(
                session, username, num_pages, max_concurrent
            )

            return {
                "username": username,
                "total_count": watchlist_count,
                "num_pages": num_pages,
                "films": full_watchlist,
                "films_fetched": len(full_watchlist),
            }
        except ValueError as e:
            print(e)
            return {"username": username, "error": str(e)}


# Main execution
if __name__ == "__main__":
    usernames = ["gfajardo555", "romekk", "Tylerh1"]  # List of usernames to fetch watchlists for
    all_watchlists = []  # List to store common films across all users
    for username in usernames:

        start_time = time.time()
        result = asyncio.run(get_user_watchlist(username, max_concurrent=5))
        end_time = time.time()
        elapsed = end_time - start_time

        if "error" not in result:
            print(f"\nWatchlist for user: {username}")
            print(f"User: {result['username']}")
            print(f"Total films in watchlist: {result['total_count']}")
            print(f"Number of pages: {result['num_pages']}")
            print(f"Films fetched: {result['films_fetched']}")
            print(f"First and last 5 films: {result['films'][:5]} ... {result['films'][-5:]}")
            print(f"Time elapsed: {elapsed:.2f} seconds")

            all_watchlists.append(set(result['films']))
        else:
            print(f"Error: {result['error']}")

    # Find common films across all users
    common_films = list(set.intersection(*all_watchlists))
    print(f"\nCommon films across all users: {len(common_films)}")
    print(f"Common films: {common_films[:5]} ... {common_films[-5:]}")

    # save the DataFrame to a CSV file
    df = list_to_df(common_films)
    df.to_csv(f"{'_'.join(usernames)}_common_watchlist.csv", index=False)
