# Method

{{nom}} publishes figures about Roblox that anyone can check again. This page explains where they come from, how they are calculated and what they don’t say.

## What we collect

Every hour, a program queries Roblox’s public web APIs, the same ones the roblox.com website uses:

- the Discover page charts (most-played games right now, trending, rising games);
- for every game that appeared in one of those charts over the past fourteen days: the number of players online, total visits, favorites and votes.

A game stays tracked for two weeks after its last appearance in a chart, so that we can measure declines too. Sponsored slots are excluded from the charts.

Every reading is archived as is, in CSV files anyone can read, in our [open data repository]({{donnees}}).

## How we calculate

All figures are calculated by a program, never by hand or by an AI. A day runs from midnight to midnight, Paris time.

- **Peak players**: the highest of the day’s hourly readings. Since we read once an hour, the real peak may be slightly higher.
- **Average players**: the average of the day’s hourly readings.
- **Changes**: the day’s average compared with the previous day’s, or with the average of the previous seven days when we have enough history. These comparisons only use complete measurements: the game must have been measured in at least three quarters of the readings of each day compared (18 hours out of 24).
- **Gainers and losers**: only games averaging at least a thousand players are included, to avoid spectacular percentages on nearly empty games.
- **Visits in 24 hours**: the difference between two readings 23 to 25 hours apart. Without a valid pair of readings, we don’t publish this figure.

- **One-off peak**: games are ranked by their daily peak. When that peak is more than three times the neighbouring readings, often a one-hour event, the article flags it as a one-off and also gives the game’s rank by daily average.
- **Entries into the top 50**: a game only counts as a new entry if it was fully measured the day before, outside the top 50. A game missing from our readings the day before (lost reading, game unavailable) that was in the top 50 during the previous seven days is a return, not an entry.

A game is only ranked if it appears in at least half of the day’s readings. When readings are missing, the article says so; below 18 readings in a day, it states that the day is incomplete. When Roblox’s API limits our requests, the program retries the games it could not measure before saving the reading; any that remain unmeasured are listed in the reading’s status file.

## Alerts

At each reading, a program compares every game with the previous reading. It publishes an alert when a game with at least 2,000 players gains 50% or more in one hour, or when a game enters the top 10 from outside the top 20. The same game cannot trigger the same alert twice within six hours.

## Game pages and open data

Every tracked game has its own page, with its hourly curve and key figures. A page is only offered to search engines after seven days of history. All data is freely available in JSON and CSV (see [Open data](../donnees/)).

## What these figures don’t say

- Roblox does not publish the total number of connected players in real time. The total we show only covers the games we track.
- The platform’s annual and quarterly figures (active users, revenue, hours played) come from Roblox Corporation’s official investor publications. We cite them with a link to the original document.
- We publish no revenue estimate for any game: no public data makes it possible to verify one.

## How articles are written

1. The program calculates the day’s facts and saves them to a file.
2. The daily report is written by a program from fixed templates; analyses are written by an AI. Neither writes any figure itself: figures are pulled from the file.
3. An automatic checker blocks publication if a figure does not come from the data, if a phrase suggests an official link with Roblox, or if a common phrase contradicts the facts (incomplete day not flagged, “stays on top” without being No. 1 the day before, unestablished entry into the top 50, one-off peak presented as lasting).
4. Analyses are reviewed by an agent that checks the meaning of sentences. The daily report, which follows fixed templates, is published as soon as it passes the checker.
5. Daily reports in English, Spanish and Portuguese follow translated templates; other articles are translated from the French original by an AI. The figures are the same, pulled from the same files.

In every article, underlined figures are links: they open the exact line of the data file they come from.

## Independence

{{nom}} is neither affiliated with nor endorsed by Roblox Corporation. Roblox is a trademark of Roblox Corporation. When an article discusses a game the editor has a connection with, the article says so.

## Errors

Spotted an error? Report it from the [Corrections](../corrections/) page. Every correction is published.
