from kiteconnect import KiteConnect
import config

kite = KiteConnect(api_key=config.API_KEY)
kite.set_access_token(config.ACCESS_TOKEN)

instruments = kite.instruments('NFO')
count = 0
for instr in instruments:
    if 'NIFTY' in instr.get('tradingsymbol', '') or 'NIFTY' in instr.get('name', ''):
        print(instr.get('tradingsymbol'), '|', instr.get('name'))
        count += 1
        if count >= 50:
            break
print('Total NIFTY instruments:', sum(1 for instr in instruments if 'NIFTY' in instr.get('tradingsymbol', '') or 'NIFTY' in instr.get('name', '')))
