from threading import Thread, Event
from datetime import datetime, timedelta
import time
from binance.client import Client
from binance.enums import *
from zoneinfo import ZoneInfo

def check_balance(client, currency):
    balance = client.get_asset_balance(asset=currency)
    return float(balance['free'])

def get_lot_size(client, symbol):
    info = client.get_symbol_info(symbol)
    for filt in info['filters']:
        if filt['filterType'] == 'LOT_SIZE':
            return float(filt['minQty']), float(filt['stepSize']), len(str(filt['stepSize']).split('.')[-1])
        
def buy_coin(client, money, symbol):
    coin_price = float(client.get_symbol_ticker(symbol=symbol)['price'])
    coin_amount = money / coin_price

    min_qty, step_size, precision = get_lot_size(client, symbol)
    
    coin_amount = round(coin_amount, 8)
    
    coin_amount = max(min_qty, round(coin_amount // step_size * step_size, precision))
    
    coin_amount_str = f"{coin_amount:.{precision}f}"
    
    order = client.order_market_buy(symbol=symbol, quantity=coin_amount_str)
    return order, coin_price

def sell_coin(client, coin_amount, symbol):
    min_qty, step_size, precision = get_lot_size(client, symbol)

    coin_amount = max(min_qty, round(coin_amount // step_size * step_size, precision))
    coin_amount_str = f"{coin_amount:.{precision}f}"
    order = client.order_market_sell(symbol=symbol, quantity=coin_amount_str)
    return order

def fetch_portfolio(api_key, api_secret):
    client = Client(api_key, api_secret)
    try:
        account_info = client.get_account()
        balances = account_info['balances']

        price_usdt_in_brl = float(client.get_symbol_ticker(symbol='USDTBRL')['price'])

        portfolio = {}
        for balance in balances:
            asset = balance['asset']
            amount = float(balance['free']) + float(balance['locked'])
            
            if amount > 0:
                if asset == 'BRL':
                    value_in_usdt = amount / price_usdt_in_brl
                    portfolio[asset] = {'AMOUNT': amount, 'USDT': value_in_usdt}
                elif asset != 'USDT':
                    symbol = asset + 'BRL'
                    price_in_brl = float(client.get_symbol_ticker(symbol=symbol)['price'])
                    value_in_usdt = (amount * price_in_brl) / price_usdt_in_brl
                    portfolio[asset] = {'AMOUNT': amount, 'USDT': value_in_usdt}                  

        return portfolio
    except Exception as e:
        print(f"An error occurred: {e}")
        return {}

def formatPercent(percent, type):
    if type == 'SELL':
        return 1 + percent / 100
    elif type == 'BUY':
        return 1 - percent / 100

def strategy_PRT(self): 
    with self.app.app_context():
        symbol = self.coin_currency + self.fiat_currency
        amount_money_in_fiat = check_balance(self.client, self.fiat_currency)
        coin_current_price = float(self.client.get_symbol_ticker(symbol=symbol)['price'])  
        money = int(self.value)
        buy_percent = formatPercent(float(self.buy_percent), 'BUY')
        sell_percent = formatPercent(float(self.sell_percent), 'SELL')
        if(self.percentage):
            percentaged = money / 100
            money = amount_money_in_fiat * percentaged
            
        print("----" * 10)
        print("TradingBot running")
        print("Seus Dados:")
        print(f"Saldo em {self.fiat_currency}: {amount_money_in_fiat}")
        print(f"Saldo em {self.coin_currency}: {check_balance(self.client, self.coin_currency)}")
        print(f"Preço atual do {self.coin_currency}: {coin_current_price}")
        print(f"Valor a ser investido: {money}")
        print(f"Porcentagem de compra: {buy_percent}")
        print(f"Porcentagem de venda: {sell_percent}")
        print(f"Skid: {self.skid}")
        print(f"Estratégia: {self.strategy}")
        print(f"Comprado: {self.purchased}")
        print(f"Preço de Base: {self.price}")
                    
        if(self.purchased is False):
            if self.price is None:
                print(f"Preço de Compra: {coin_current_price}")
            else:
                print(f"Esperando para Comprar: \nPreço Atual: {coin_current_price}\nPreço Esperado: { self.price * buy_percent}")
            
        else:
            print(f"Esperando para Vender: \nPreço Atual: {coin_current_price}\nPreço Esperado: { self.price * sell_percent}")    
        
        
        if not self.purchased:
            if self.price is None or coin_current_price <= self.price * buy_percent:
                if(money > amount_money_in_fiat):
                    print('Saldo insuficiente')
                    return
                
                result, price_coin = buy_coin(self.client, money , symbol)
                print(f"Compra de R$ {money} ao preco do {self.coin_currency} de R$ {price_coin} {price_coin} Realizada com sucesso!")
                print(f"Resultado: {result}") 
                self.price = price_coin
                self.purchased = True
                balance_coin_now = check_balance(self.client, self.coin_currency)
                balance_fiat_now = check_balance(self.client, self.fiat_currency)
                bot_historic = self.bot_historic(price=self.price, date=datetime.now(), bot_id=self.id, side='BUY', quantity_coin=float(result['origQty']), coin_currency=self.coin_currency, fiat_currency=self.fiat_currency, quantity_fiat=money, balance_coin=balance_coin_now, balance_fiat=balance_fiat_now)
                self.db.session.add(bot_historic)
                self.db.session.commit()
        else:
            if coin_current_price >= self.price * sell_percent:
                coin_price = float(self.client.get_symbol_ticker(symbol=symbol)['price'])
                coin_amount = money / coin_price
                result = sell_coin(self.client, coin_amount, symbol)
                print(f"Venda de R$ {money} ao preco do {self.coin_currency} de R$ {coin_price} Realizada com sucesso!")
                print(f"Resultado: {result}")
                balance_coin_now = check_balance(self.client, self.coin_currency)
                balance_fiat_now = check_balance(self.client, self.fiat_currency)
                self.purchased = False
                self.price = coin_current_price
                bot_historic = self.bot_historic(price=self.price, date=datetime.now(), bot_id=self.id, side='SELL', quantity_coin=float(result['origQty']), coin_currency=self.coin_currency, fiat_currency=self.fiat_currency, quantity_fiat=money, balance_coin=balance_coin_now, balance_fiat=balance_fiat_now)
                self.db.session.add(bot_historic)
                self.db.session.commit()

        print('Estratégia PRT')
    

def strategy_LANC(self):
    target_time = self.entry_datetime
    current_time = datetime.now(ZoneInfo("UTC"))
    if current_time < target_time:
        return
    symbol = self.coin_currency + self.fiat_currency

    self.price = float(self.client.get_symbol_ticker(symbol=symbol)['price'])
    max_price = self.price * (1 + self.skid / 100)

    purchase_prices = []
    
    while True:
        current_price = float(self.client.get_symbol_ticker(symbol=symbol)['price'])
        print(f"Preço atual: {current_price}"
              f"\nPreço máximo: {max_price}")
        print("soma de tudo", sum([p['value'] for p in purchase_prices]))
        if current_price >= max_price:
            break 
        if sum([p['value'] for p in purchase_prices]) > self.value * 0.985:
            break
        try:
            result, purchase_price = buy_coin(self.client, self.value, symbol)
            print(f"Compra realizada ao preço na quantida de {float(result['origQty'])}  {purchase_price}.")
            
            purchase_prices.append({'price': purchase_price, 'amount': float(result['origQty']), 'value': self.value})
        except Exception as e:
            print(f"Erro ao comprar: {e}")
            if(e.code == -2010):
                print("Saldo insuficiente")
                break
            continue
        
        
    self.purchased = True 
    
    sell_target_price = purchase_prices[0]['price'] * (1+(self.lanc_sell_1 / 100))
    while True:
        current_price = float(self.client.get_symbol_ticker(symbol=symbol)['price'])
        if current_price >= sell_target_price:
            break  
        time.sleep(1)  

    coin_amount = sum([p['amount'] for p in purchase_prices]) * 0.99
    coin_amount = coin_amount * (self.lanc_amount_1 / 100)

    result = sell_coin(self.client, coin_amount, symbol)
    print(f"Venda realizada ao preço de {current_price}.")
    balance_coin_now = check_balance(self.client, self.coin_currency)
    balance_fiat_now = check_balance(self.client, self.fiat_currency)
    bot_historic = self.bot_historic(price=self.price, date=datetime.now(), bot_id=self.id, side='SELL', quantity_coin=float(result['origQty']), coin_currency=self.coin_currency, fiat_currency=self.fiat_currency, quantity_fiat=0, balance_coin=balance_coin_now, balance_fiat=balance_fiat_now)
    self.db.session.add(bot_historic)
    self.db.session.commit()
    
    if(self.lanc_sell_2):
        sell_target_price = purchase_price * (1+(self.lanc_sell_2 / 100))
        while True:
            current_price = float(self.client.get_symbol_ticker(symbol=symbol)['price'])
            if current_price >= sell_target_price:
                break  
            time.sleep(1)  
        
        coin_amount = sum([p['amount'] for p in purchase_prices]) * 0.99
        coin_amount = coin_amount * (self.lanc_amount_2 / 100)
        print("coin_amount 2", coin_amount)
        sell_coin(self.client, coin_amount, symbol)
        print(f"Venda realizada ao preço de {current_price}.")
        balance_coin_now = check_balance(self.client, self.coin_currency)
        balance_fiat_now = check_balance(self.client, self.fiat_currency)
        bot_historic = self.bot_historic(price=self.price, date=datetime.now(), bot_id=self.id, side='SELL', quantity_coin=float(result['origQty']), coin_currency=self.coin_currency, fiat_currency=self.fiat_currency, quantity_fiat=0, balance_coin=balance_coin_now, balance_fiat=balance_fiat_now)
        self.db.session.add(bot_historic)
        self.db.session.commit()
    if(self.lanc_sell_3):
        sell_target_price = purchase_price * (1+(self.lanc_sell_3 / 100))
        while True:
            current_price = float(self.client.get_symbol_ticker(symbol=symbol)['price'])
            if current_price >= sell_target_price:
                break  
            time.sleep(1)  
        
        coin_amount = sum([p['amount'] for p in purchase_prices]) * 0.99
        coin_amount = coin_amount * (self.lanc_amount_3 / 100)
        print("coin_amount 3", coin_amount)
        sell_coin(self.client, coin_amount, symbol)
        print(f"Venda realizada ao preço de {current_price}.")
        balance_coin_now = check_balance(self.client, self.coin_currency)
        balance_fiat_now = check_balance(self.client, self.fiat_currency)
        bot_historic = self.bot_historic(price=self.price, date=datetime.now(), bot_id=self.id, side='SELL', quantity_coin=float(result['origQty']), coin_currency=self.coin_currency, fiat_currency=self.fiat_currency, quantity_fiat=0, balance_coin=balance_coin_now, balance_fiat=balance_fiat_now)
        self.db.session.add(bot_historic)
        self.db.session.commit()

    self.purchased = False  
    

strategies = {
    'PRT': strategy_PRT,
    'LANC': strategy_LANC
}

class TradingBot:
    def __init__(self, id, app, db, bot_historic, api_key, api_secret, fiat_currency, coin_currency, value, percentage,price, skid, strategy, entry_datetime, buy_percentage, sell_percentage, lanc_sell_1, lanc_sell_2, lanc_sell_3, lanc_amount_1, lanc_amount_2, lanc_amount_3):
        self.app = app
        self.db = db
        self.bot_historic = bot_historic
        self.client = Client(api_key, api_secret)
        self.id = id
        self.coin_currency = coin_currency
        self.fiat_currency = fiat_currency
        self.value = value
        self.percentage = percentage
        self.skid = skid
        self.buy_percent = buy_percentage
        self.sell_percent = sell_percentage
        self.strategy = strategy
        self.purchased = False
        self.status = 'RUNNING' 
        self.entry_datetime =  entry_datetime
        self.lanc_sell_1 = lanc_sell_1
        self.lanc_sell_2 = lanc_sell_2
        self.lanc_sell_3 = lanc_sell_3
        self.lanc_amount_1 = lanc_amount_1
        self.lanc_amount_2 = lanc_amount_2
        self.lanc_amount_3 = lanc_amount_3
        if price:
            self.price = price
        else:
            self.price = None
        
        self.running = Event()
        self.running.set()
        
    
    def run(self):
        if self.fiat_currency != 'USDT':
                self.value = self.value * float(self.client.get_symbol_ticker(symbol='USDT' + self.fiat_currency)['price'])
                
        if(self.strategy == 'LANC'):
            target_time = self.entry_datetime
            while self.running.is_set():
                print("Data de entrada: ", target_time)
                print("Data atual: ", datetime.now())
                current_time = datetime.now(ZoneInfo("UTC"))
                if current_time > target_time:
                    strategy_LANC(self)
                print("Aguardando horário de entrada")
                time.sleep(1) 
            strategy_LANC(self)
            
        elif self.strategy == 'PRT':
            if self.price is None or self.price == '':
                self.price = float(self.client.get_symbol_ticker(symbol=self.coin_currency + self.fiat_currency)['price'])
            if(self.buy_percent is None and self.buy_percent == ''):
                self.buy_percent = 2
            if(self.sell_percent is None and self.sell_percent == ''):
                self.sell_percent = 2 
                
            while self.running.is_set():
                strategies[self.strategy](self)
                time.sleep(10) 
        

    def stop(self):
        self.running.clear()

def create_bot():
    print('Bot criado com sucesso')