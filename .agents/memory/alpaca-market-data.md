---
name: Alpaca market-data feed
description: Subscription-specific feed constraint for historical stock data requests
---

The configured Alpaca account rejects recent SIP market-data queries, while the IEX feed is permitted for historical stock bars.

**Why:** A default stock-bars request failed with a subscription error even though the trading-account API worked.

**How to apply:** Set the stock-bars request feed explicitly to the account-compatible feed when querying recent data.