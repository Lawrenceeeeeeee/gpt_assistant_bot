from okx import OkxRestClient
api = OkxRestClient()

instId = 'BTC-USDT-SWAP'
now = int(time.time()*1000)
start = now - 365*24*60*60*1000


def get_candlesticks(instId, end, bar='1H', amount=10000):
    result = []
    for i in range(amount//100):
        res = api.public.get_history_candlesticks(instId, after=end, bar=bar)
        candlesticks = res['data']
        result.extend(candlesticks)
        if candlesticks:
            end = candlesticks[-1][0]
        else:
            break
    return result