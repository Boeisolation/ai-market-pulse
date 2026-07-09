# Push Notifications

AI Market Pulse can push your daily report to Telegram or Feishu (plus Slack, Discord, WeCom, generic webhooks, and email — see the reference section at the bottom). This guide covers the fast path: getting a Telegram bot token / chat ID or a Feishu webhook URL, then wiring it up with one command.

## Telegram

1. Open Telegram and message [@BotFather](https://t.me/BotFather).
2. Send `/newbot`, pick a name and a username for your bot. BotFather replies with a token that looks like `123456789:AAExampleTokenDoNotShare`. That's your **bot token**.
3. Send at least one message to your new bot (or add it to a group and send a message there) so Telegram has something to report back.
4. Get your **chat ID**: open `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates` in a browser (replace `<YOUR_TOKEN>` with the token from step 2), and look for `"chat":{"id":...}` in the JSON response. That number (it can be negative for groups) is your chat ID.

## Feishu (飞书)

1. In the Feishu group you want notifications in, open group settings → **Bots** → **Add Bot** → **Custom Bot**.
2. Give it a name, confirm, and Feishu shows you a **webhook URL** that looks like `https://open.feishu.cn/open-apis/bot/v2/hook/xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`. Copy it.

## Wire it up — CLI

```bash
market-pulse init --symbols "AAPL,MSFT,NVDA,600519" \
  --telegram-token "123456789:AAExampleTokenDoNotShare" \
  --telegram-chat-id "-1001234567890" \
  --path watchlist.yaml
```

This does **not** write your token/chat ID into `watchlist.yaml` as plain text — it writes an environment-variable reference (`token_env: TELEGRAM_BOT_TOKEN`, `chat_id_env: TELEGRAM_CHAT_ID`) instead, so the config file stays safe to share or commit. Right after writing the file, the command prints the export lines you need:

```bash
export TELEGRAM_BOT_TOKEN=123456789:AAExampleTokenDoNotShare
export TELEGRAM_CHAT_ID=-1001234567890
```

Copy-paste those into your shell, then verify the whole thing actually works:

```bash
market-pulse test-notify --config watchlist.yaml
```

You should get a confirmation message in Telegram/Feishu within a few seconds, and the command prints each target's send result (success or a specific failure reason) in the terminal. `market-pulse doctor --config watchlist.yaml` also does a quick local check (missing env var, non-`https://` webhook URL, etc.) without sending anything — run it first if `test-notify` fails and you're not sure why.

For Feishu, the equivalent flag is `--feishu-webhook`:

```bash
market-pulse init --symbols "AAPL,MSFT,NVDA,600519" --feishu-webhook "https://open.feishu.cn/open-apis/bot/v2/hook/xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
```

You can combine `--telegram-token`/`--telegram-chat-id` and `--feishu-webhook` in the same command to push to both.

## Wire it up — local console

Run `market-pulse serve`, open `http://127.0.0.1:8766`, and expand **Push Notifications (optional)** below the other options. Paste your Telegram bot token + chat ID and/or your Feishu webhook URL directly into the form — these are only used for that one run (nothing is written to disk), and the result panel shows whether each push actually succeeded after the report finishes generating.

## Reference: all supported channels

The `--telegram-token`/`--telegram-chat-id`/`--feishu-webhook` flags and the console form cover the two fastest-to-set-up channels. `notifications:` in `watchlist.yaml` also supports Slack, Discord, WeCom, a generic webhook, and email — hand-edit the config for these using the same `_env`-suffixed indirection pattern:

```yaml
notifications:
  - type: "telegram"
    token_env: "TELEGRAM_BOT_TOKEN"
    chat_id_env: "TELEGRAM_CHAT_ID"
  - type: "feishu"
    url_env: "FEISHU_WEBHOOK_URL"
  - type: "slack"
    url_env: "SLACK_WEBHOOK_URL"
  - type: "discord"
    url_env: "DISCORD_WEBHOOK_URL"
  - type: "wecom"
    url_env: "WECOM_WEBHOOK_URL"
  - type: "webhook"
    url_env: "GENERIC_WEBHOOK_URL"
  - type: "email"
    smtp_host_env: "SMTP_HOST"
    smtp_port_env: "SMTP_PORT"
    username_env: "SMTP_USERNAME"
    password_env: "SMTP_PASSWORD"
    sender_env: "SMTP_SENDER"
    to_env: "SMTP_TO"
```

`market-pulse doctor` validates all of the above locally (no network calls); `market-pulse test-notify` sends a real test message to every configured target regardless of type.

Webhook URLs must use `https://` and must not resolve to a private/internal address — this is enforced at send time as a safety check, not just a suggestion.
