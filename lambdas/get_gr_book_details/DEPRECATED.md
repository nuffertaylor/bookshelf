# Deprecated

This lambda scraped goodreads.com for book details, which is fragile and against the direction of the app (Goodreads shut down its public API and RSS feeds). Contributing spines now goes through Hardcover catalog search (`lambdas/hardcover_search_books`, `POST /hardcover/search`).

The code is kept on disk for reference only. It is no longer built or deployed: `GetGRBookDetailsFunction` and the `/getgrbookdetails` route were removed from `infra/template.yaml`. Deploying that template change deletes the function and route, so deploy it only after the frontend no longer calls it. If the function was ever created outside the stack, delete it by hand.
