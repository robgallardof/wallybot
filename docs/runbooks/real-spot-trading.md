# Real Kraken spot account

WallyBot now supports operator-approved real spot orders. You configure it from the UI; never
send keys in chat. It starts in OBSERVE until you explicitly activate LIVE.

1. Create a dedicated Kraken API key/secret for WallyBot. Enable query funds, query open/closed
   orders, create/modify orders and cancel/close orders. Do not grant funding, withdrawal, earn,
   transfer or withdrawal-address permissions. The app verifies the provider's permission report.
   Use a dedicated key; sharing one with other applications can break nonce ordering. API-specific
   OTP keys are not supported. This does not change MFA on your Kraken login or WallyBot session.
2. In **Conexiones**, choose **KRAKEN**, select real spot trading and enter the key and API secret.
   They are encrypted and not redisplayed. Successful linking places no order.
3. In **Configuración → Operaciones con dinero real**, select that connection. Enter your maximum
   USD per trade, total USD exposure, maximum daily USD loss and maximum price change in percent.
   Enter LIVE and confirm with MFA. Verification must succeed before activation.
4. In **Inteligencia → Propuestas**, inspect the reasoning and expiry. With LIVE active, the page
   says real money, shows your limits and requires a per-proposal confirmation before approval.
   The backend revalidates and may reduce the amount or reject it. An approval is single-use.
5. In **Portafolio**, inspect the separate **Cuenta real Kraken** balances and real orders. Initial
   holdings have unknown historical cost; their profit is not fabricated. Values retain their
   verification time. PAPER records are separately labeled as simulation.

Only USD, BTC (Kraken's XBT identifier) and ETH spot holdings are supported in this first real
adapter. There are no leveraged positions, transfers or withdrawals. IOC limit orders can be
partially filled or cancelled instead of filling. Stops and targets are review notices, not
automatic protective orders. No trading return is guaranteed.

## Connection and activation errors

Linking and activation show the specific, sanitized reason (translated in the UI); the raw
provider response and the key are never shown. Typical causes and fixes:

| Message (English key) | What to do |
|---|---|
| Kraken rejected the API key | Copy the API key again completely; check it was not deleted. |
| Kraken rejected the signature / API secret is not in Kraken's format | Paste the private key (API secret) exactly as Kraken showed it. |
| API key has excessive permissions | Create a new key without deposit, withdrawal, transfer, earn or address permissions. |
| API key lacks required ... permissions | Add query funds, query open/closed orders, create/modify and cancel/close orders. |
| API key history restrictions prevent complete reconciliation | Remove the key's query start/end date restriction. |
| API keys with their own 2FA password are not supported | Create a key without API 2FA (Kraken login 2FA is unaffected). |
| Kraken rejected the request sequence (nonce) | Use a key dedicated to WallyBot only. |
| Kraken is temporarily limiting / unavailable / could not be reached | Wait and retry; nothing is activated meanwhile. |
| The maximum per trade cannot exceed the maximum total exposure | Fix the limits; the form checks this before sending. |
| This deployment has real trading capability disabled | `WALLY_LIVE_CAPABLE` is false on the API. |

A failed activation leaves the account BLOCKED with that reason and the mode outside LIVE.

## Blocking and recovery

An outstanding/ambiguous order blocks another trade. The monitor reconciles it every 30 seconds,
including after restart and while new execution is disabled. It never resubmits the original
order. Check the observed order status before rearming. **Pausar** blocks new submissions; it does
not erase existing orders or guarantee cancellation of an already accepted order.

An external deposit, withdrawal, manual trade, unsupported holding or unexpected fee/account
movement can create a mismatch. The bot blocks execution instead of overwriting the ledger or
resetting losses. Review the discrepancy before any separately audited adjustment; repeatedly
clicking rearm cannot erase it. Do not change an initialized account to another account as a
shortcut. Daily/weekly/drawdown limits also persist across restart and rearm.

The deployment flag WALLY_LIVE_CAPABLE controls availability only, not activation. Compose
enables the capability on the API; all limits and confirmations are still required. Set the flag
false to prevent new real execution. No research/analyst process receives private trading keys.

API references: [Kraken API key permissions](https://docs.kraken.com/api/docs/rest-api/get-api-key-info),
[authentication](https://docs.kraken.com/exchange/guides/rest/authentication),
[IOC limit orders](https://docs.kraken.com/api-reference/trading/add-order).
