# Alpaca Account Setup Guide

This guide will walk you through setting up an Alpaca paper trading account and obtaining your API credentials.

## What is Paper Trading?

Paper trading is simulated trading with virtual money. It allows you to test trading strategies without risking real capital. Alpaca provides paper trading accounts with $100,000 in virtual cash.

**Benefits:**
- ✅ No financial risk
- ✅ Real market data
- ✅ Same API as live trading
- ✅ Perfect for testing and learning

## Step-by-Step Setup

### Step 1: Create an Alpaca Account

1. Navigate to [https://alpaca.markets](https://alpaca.markets)
2. Click on **"Sign Up"** or **"Get Started"**
3. Fill in your information:
   - Email address
   - Password
   - Name
4. Agree to the terms of service
5. Click **"Create Account"**

### Step 2: Verify Your Email

1. Check your email inbox for a verification email from Alpaca
2. Click the verification link in the email
3. Your account will be activated

### Step 3: Access Paper Trading

1. Log in to your Alpaca account
2. You'll be taken to the dashboard
3. Make sure you're in **Paper Trading** mode
   - Look for "Paper Trading" indicator at the top
   - If you see "Live Trading", switch to Paper Trading

### Step 4: Generate API Keys

1. From the dashboard, navigate to **"Your API Keys"** section
   - Usually found under settings or API section
   - Or go directly to: [https://app.alpaca.markets/paper/dashboard/overview](https://app.alpaca.markets/paper/dashboard/overview)

2. Click **"Generate New Keys"** or **"Create New Key"**
   
3. You will see two keys generated:
   - **API Key ID** (also called Key ID)
   - **Secret Key** (also called Secret)

4. **IMPORTANT**: Copy both keys immediately and store them securely
   - The Secret Key will only be shown once
   - You cannot retrieve it later
   - If you lose it, you'll need to generate new keys

### Step 5: Store Your API Keys Securely

1. Open your project directory: `c:\Codes\AI Trader`

2. Copy the `.env.example` file to create `.env`:
   ```bash
   cp .env.example .env
   ```

3. Open the `.env` file in a text editor

4. Replace the placeholder values with your actual keys:
   ```env
   APCA_API_KEY_ID=PK1234567890ABCDEF
   APCA_API_SECRET_KEY=1234567890abcdefghijklmnopqrstuvwxyz1234
   APCA_API_BASE_URL=https://paper-api.alpaca.markets
   ```

5. Save the file

6. **NEVER** commit this file to version control
   - It's already in `.gitignore`
   - Never share these keys publicly
   - Never post them in forums or GitHub

### Step 6: Verify Your Setup

Run the verification scripts:

```bash
# Activate virtual environment
.\venv\Scripts\Activate.ps1

# Check environment variables
python verify_env.py

# Test API connection
python test_connection.py
```

You should see success messages if everything is configured correctly.

## Important Information

### Paper Trading API Endpoint

Always use the paper trading endpoint:
```
https://paper-api.alpaca.markets
```

**DO NOT** use the live trading endpoint unless you fully understand the risks and have tested your bot extensively.

### API Key Security

🔒 **Security Best Practices:**

1. **Never share your API keys**
   - Don't post them online
   - Don't commit them to Git
   - Don't send them in emails

2. **Store them securely**
   - Use environment variables (`.env` file)
   - Use a password manager for backup
   - Keep backups encrypted

3. **Regenerate if exposed**
   - If you accidentally expose your keys, regenerate them immediately
   - Old keys will be invalidated
   - Update your `.env` file with new keys

4. **Use separate keys for different projects**
   - Don't reuse the same keys across multiple projects
   - Easier to track and revoke if needed

### Rate Limits

Alpaca has rate limits for API calls:
- **200 requests per minute** per API key
- Applies to both paper and live trading
- Monitor your usage to avoid hitting limits

### Paper vs Live Trading

| Feature | Paper Trading | Live Trading |
|---------|--------------|--------------|
| Money | Virtual ($100k) | Real money |
| Risk | None | High |
| API Endpoint | paper-api.alpaca.markets | api.alpaca.markets |
| Data | Real market data | Real market data |
| Order Execution | Simulated | Real orders |

**ALWAYS test with paper trading first!**

## Troubleshooting

### Can't find API keys section
- Make sure you're logged in
- Check you're in Paper Trading mode
- Look under Settings → API Keys
- Try the direct link: [https://app.alpaca.markets/paper/dashboard/overview](https://app.alpaca.markets/paper/dashboard/overview)

### Keys not working
- Verify you copied the full key (no spaces or extra characters)
- Check you're using the paper trading endpoint
- Make sure `.env` file is in the project root
- Ensure no spaces around the `=` in `.env` file
- Try regenerating keys

### "Forbidden" error
- Keys might be for live trading instead of paper
- Keys might be expired or revoked
- Regenerate keys in the Alpaca dashboard

### Lost Secret Key
- You cannot retrieve it
- Generate new API keys
- Update your `.env` file with the new keys

## Next Steps

Once your account is set up and verified:

1. ✅ Account created and verified
2. ✅ API keys generated and stored in `.env`
3. ✅ Connection test passed
4. ➡️ Proceed with bot development

## Resources

- [Alpaca Documentation](https://alpaca.markets/docs/)
- [Alpaca API Reference](https://alpaca.markets/docs/api-references/)
- [Paper Trading Dashboard](https://app.alpaca.markets/paper/dashboard/overview)
- [Alpaca API Keys Management](https://app.alpaca.markets/paper/dashboard/overview)
- [Alpaca Support](https://alpaca.markets/support)

## Need Help?

If you encounter issues:
1. Check the [Alpaca Support Center](https://alpaca.markets/support)
2. Review our [README.md](../README.md) troubleshooting section
3. Check the Alpaca Community forums
4. Contact Alpaca support if account-related

---

**Remember:** Paper trading is safe and free. Use it to test and learn before considering live trading.
