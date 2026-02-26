from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import asyncio
import aiohttp

from get_common_watchlist import get_user_watchlist
from get_watchlist_data import get_multiple_movie_stats, results_to_df

app = FastAPI()

class UsernameRequest(BaseModel):
    usernames: list[str]

@app.post("/common-watchlist")
async def common_watchlist(request: UsernameRequest):
    usernames = request.usernames

    # Step 1: Get each user's watchlist
    all_watchlists = []
    for username in usernames:
        result = await get_user_watchlist(username)
        if "error" in result:
            return {"error": f"Could not fetch watchlist for {username}: {result['error']}"}
        all_watchlists.append(set(result["films"]))

    # Step 2: Find common films
    common_slugs = list(set.intersection(*all_watchlists))
    if not common_slugs:
        return {"error": "No common films found across these users."}

    # Step 3: Fetch stats for common films
    stats = await get_multiple_movie_stats(common_slugs)

    # Step 4: Build and return DataFrame as JSON
    df = results_to_df(stats)
    df["slug"] = common_slugs
    df = df.dropna(how="all")
    return {"films": df.to_dict(orient="records")}