# API Key Setup (Cloud Assist tier)

Poise is BYOK (bring your own key) for Cloud Assist — you connect your own account with a provider, and Poise calls it directly from your machine. Your key is stored in your OS keychain, never in a plaintext config file.

## OpenAI

1. Go to [platform.openai.com/api-keys](https://platform.openai.com/api-keys) and sign in.
2. Click **Create new secret key**, give it a name like "Poise", and copy it (you won't see it again).
3. In Poise's setup wizard or **Settings → API Keys**, choose **OpenAI**, paste the key, and click **Test connection**.

## Anthropic

1. Go to [console.anthropic.com/settings/keys](https://console.anthropic.com/settings/keys) and sign in.
2. Click **Create Key**, name it, and copy it.
3. In Poise, choose **Anthropic**, paste the key, and click **Test connection**.

## Google (Gemini)

1. Go to [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey) and sign in.
2. Click **Create API key**.
3. In Poise, choose **Google (Gemini)**, paste the key, and click **Test connection**.

## Troubleshooting

| Message | Meaning | Fix |
|---|---|---|
| "Your API key was rejected — check Settings" (`CLOUD_AUTH_FAILED`) | Key is invalid, revoked, or wrong provider selected | Regenerate the key on the provider's site and re-enter it |
| "API rate limit reached — wait and try again" (`CLOUD_RATE_LIMIT`) | You've hit your provider's request/token limit | Wait a bit, or check your usage tier with the provider |
| Cost warning at ~50K tokens / ~$2 estimate | Poise's default per-session soft cap | You can raise the cap for that session from the warning dialog |

## Removing or rotating a key

**Settings → API Keys → Remove**. This deletes it from the OS keychain immediately; Poise never keeps a copy elsewhere.
