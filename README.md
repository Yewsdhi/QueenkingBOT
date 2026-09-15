# ArchonBot

A Telegram Music Player Bot, written in Python with Pyrogram and Py-Tgcalls.

## 🚀 Deploy on Heroku

> **Important:** The Heroku Deploy button works after this project is pushed to a **public GitHub repository**. Replace `YOUR_GITHUB_USERNAME/YOUR_REPOSITORY` below with your actual GitHub repository path.

[![Deploy](https://www.herokucdn.com/deploy/button.svg)](https://heroku.com/deploy?template=https://github.com/Yewsdhi/QueenkingBOT)

### Required Heroku configuration

The `app.json`, `Procfile`, `heroku.yml`, and `Dockerfile` are already included for Heroku/container deployment.

You will need to provide these environment variables during deployment:

- `API_ID`
- `API_HASH`
- `BOT_TOKEN`
- `MONGO_URL`
- `LOGGER_ID`
- `OWNER_ID`
- `SESSION`

### Heroku deployment

1. Push this project to a public GitHub repository.
2. Open `README.md` and replace `YOUR_GITHUB_USERNAME/YOUR_REPOSITORY` in the Deploy button URL.
3. Open the Deploy button.
4. Enter the required environment variables.
5. Deploy the app as a worker.

