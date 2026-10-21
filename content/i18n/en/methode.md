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
- **Changes**: the day’s average compared with the previous day’s, or with the average of the previous seven days when we have enough history.
- **Gainers and losers**: only games averaging at least a thousand players are included, to avoid spectacular percentages on nearly empty games.
- **Visits in 24 hours**: the difference between two readings 23 to 25 hours apart. Without a valid pair of readings, we don’t publish this figure.

A game is only ranked if it appears in at least half of the day’s readings. When readings are missing, the article says so.

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
2. An AI writes the article from that file. It writes no figure itself: it pulls them from the file.
3. An automatic checker blocks publication if a figure does not come from the data, or if a phrase suggests an official link with Roblox.
4. A reviewing agent checks the meaning of sentences. During the first weeks, every article is also read by the editor before publication.
5. Articles in English, Spanish and Portuguese are translated from the French original by an AI; the figures are the same, pulled from the same files.

In every article, underlined figures are links: they open the exact line of the data file they come from.

## Independence

{{nom}} is neither affiliated with nor endorsed by Roblox Corporation. Roblox is a trademark of Roblox Corporation. When an article discusses a game the editor has a connection with, the article says so.

## Errors

Spotted an error? Report it from the [Corrections](../corrections/) page. Every correction is published.
