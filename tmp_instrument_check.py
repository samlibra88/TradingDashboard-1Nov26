from kiteconnect import KiteConnect
import config

kite = KiteConnect(api_key=config.API_KEY)
try:
    instruments = kite.instruments('NSE')
    matches = [instr for instr in instruments if 'NIFTY' in instr.get('tradingsymbol', '') or 'NIFTY' in instr.get('name', '')]
    print('COUNT', len(matches))
    for instr in matches[:20]:
        print(instr.get('exchange'), instr.get('tradingsymbol'), instr.get('name'))
except Exception as e:
    print('ERROR', e)
