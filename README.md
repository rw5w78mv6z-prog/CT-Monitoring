# CT Monitoring Online

Flask + PostgreSQL version for deployment to Render or another Python host.

Environment variable required:
- `DATABASE_URL` = PostgreSQL connection string

Start command:
`gunicorn app:app`
