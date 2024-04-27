
from flask import Flask, request, jsonify
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask import Flask, jsonify, request
from threading import Thread, Event
from binance_func import TradingBot, fetch_portfolio
from datetime import timedelta, datetime
from flask_cors import CORS
from zoneinfo import ZoneInfo

app = Flask(__name__)
CORS(app) 
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://root:12345678@localhost:3306/tradewillian'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_SECRET_KEY'] = 'segredo_do_jwt'
db = SQLAlchemy(app)
jwt = JWTManager(app)
bots = {}

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(256), nullable=False)
    api_key = db.Column(db.String(256), nullable=True)
    api_secret = db.Column(db.String(256), nullable=True)
    
class Bot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    fiat_currency = db.Column(db.String(15), nullable=False)
    coin_currency = db.Column(db.String(15), nullable=False)
    value = db.Column(db.Float, nullable=False)
    percentage = db.Column(db.Float, nullable=False)
    skid = db.Column(db.Float, nullable=True)
    strategy = db.Column(db.String(30), nullable=False)
    purchased = db.Column(db.Boolean, nullable=False)
    price = db.Column(db.Float, nullable=True)
    status = db.Column(db.String(10), nullable=False)
    entry_datetime = db.Column(db.DateTime, nullable=True)
    sell_percentage = db.Column(db.Float, nullable=True)
    buy_percentage = db.Column(db.Float, nullable=True)
    lanc_sell_1 = db.Column(db.Float, nullable=True)
    lanc_sell_2 = db.Column(db.Float, nullable=True)
    lanc_sell_3 = db.Column(db.Float, nullable=True)
    lanc_amount_1 = db.Column(db.Float, nullable=True)
    lanc_amount_2 = db.Column(db.Float, nullable=True)
    lanc_amount_3 = db.Column(db.Float, nullable=True)
    
    
class BotHistoric(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    price = db.Column(db.Float, nullable=False)
    date = db.Column(db.DateTime, nullable=False)
    bot_id = db.Column(db.Integer, db.ForeignKey('bot.id'), nullable=False)
    side = db.Column(db.String(4), nullable=False) ### BUY or SELL
    quantity_fiat = db.Column(db.Float, nullable=False)
    quantity_coin = db.Column(db.Float, nullable=False)
    coin_currency = db.Column(db.String(10), nullable=False)
    fiat_currency = db.Column(db.String(10), nullable=False)
    balance_coin = db.Column(db.Float, nullable=False)
    balance_fiat = db.Column(db.Float, nullable=False)
    
with app.app_context():
    db.create_all()
    
    
def convert_sp_to_utc(sp_datetime):

    if sp_datetime.tzinfo is None:
        sp_datetime = sp_datetime.replace(tzinfo=ZoneInfo('America/Sao_Paulo'))
    
    utc_datetime = sp_datetime.astimezone(ZoneInfo('UTC'))
    return utc_datetime
    
def convert_date_to_datetime(date_str):
    try:
        return datetime.strptime(date_str, '%d/%m/%Y %H:%M:%S')
    except ValueError as e:
        print(f"Erro: {e}")
        return None

@app.route('/signup', methods=['POST'])
def signup():
    name = request.json.get('name')
    email = request.json.get('email')
    password = request.json.get('password')
    api_key = request.json.get('api_key')
    api_secret = request.json.get('api_secret')
    
    if not name or not email or not password:
        return jsonify({'message': 'Dados incompletos'}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({'message': 'Email já cadastrado'}), 400

    user = User(name=name, email=email, password=generate_password_hash(password), api_key=api_key, api_secret=api_secret)
    db.session.add(user)
    db.session.commit()

    return jsonify({'message': 'Usuário cadastrado com sucesso'}), 201

@app.route('/login', methods=['POST'])
def login():
    email = request.json.get('email')
    password = request.json.get('password')

    user = User.query.filter_by(email=email).first()

    if not user or not check_password_hash(user.password, password):
        return jsonify({'message': 'Credenciais inválidas'}), 401

    expires = timedelta(hours=12)
    access_token = create_access_token(identity=user.id, expires_delta=expires)
    
    return jsonify(access_token=access_token), 200

@app.route('/user', methods=['GET'])
@jwt_required()
def user():
    id = get_jwt_identity()
    user = User.query.filter_by(id=id).first()
    return jsonify({'name': user.name, 'email': user.email}), 200

@app.route('/protected', methods=['GET'])
@jwt_required()
def protected():
    id = get_jwt_identity()
    return jsonify({'message': 'Rota protegida'}), 200

@app.route('/create-bot', methods=['POST'])
@jwt_required()
def create_bot_api():
    id = get_jwt_identity()
    user = User.query.filter_by(id=id).first()
    api_key = user.api_key 
    api_secret = user.api_secret 
    fiat_currency = request.json.get('fiat_currency')
    coin_currency = request.json.get('coin_currency')
    value = float(request.json.get('value')) # 5 dol
    percentage = bool(request.json.get('percentage'))
    skid = request.json.get('skid')
    price = request.json.get('price')
    sell_percentage = request.json.get('sell_percentage')
    buy_percentage = request.json.get('buy_percentage')
    strategy = request.json.get('strategy')
    entry_datetime = request.json.get('entry_datetime')
    lanc_sell_1 = request.json.get('lanc_sell_1')
    lanc_sell_2 = request.json.get('lanc_sell_2')
    lanc_sell_3 = request.json.get('lanc_sell_3')
    lanc_amount_1 = request.json.get('lanc_amount_1')
    lanc_amount_2 = request.json.get('lanc_amount_2')
    lanc_amount_3 = request.json.get('lanc_amount_3')
    
    print("entry", entry_datetime)
    
    if(price is not None and price != ''):
        price = float(price)
    else:
        price = 0
    if(sell_percentage is not None and sell_percentage != ''):
        sell_percentage = float(sell_percentage)
    else:
        sell_percentage = 1
    if(buy_percentage is not None and buy_percentage != ''):
        buy_percentage = float(buy_percentage)
    else:
        buy_percentage = 1
    if(entry_datetime is not None and entry_datetime != ''):
        print("converteu", entry_datetime)
        entry_datetime = convert_date_to_datetime(entry_datetime)
        print("converteu", entry_datetime)
    if(lanc_sell_1 is not None and lanc_sell_1 != ''):
        print("converteu o lanc_1")
        lanc_sell_1 = float(lanc_sell_1)
    if(lanc_sell_2 is not None and lanc_sell_2 != ''):
        lanc_sell_2 = float(lanc_sell_2)
    if(lanc_sell_3 is not None and lanc_sell_3 != ''):
        lanc_sell_3 = float(lanc_sell_3)
    if(lanc_amount_1 is not None and lanc_amount_1 != ''):
        lanc_amount_1 = float(lanc_amount_1)
    if(lanc_amount_2 is not None and lanc_amount_2 != ''):
        lanc_amount_2 = float(lanc_amount_2)
    if(lanc_amount_3 is not None and lanc_amount_3 != ''):
        lanc_amount_3 = float(lanc_amount_3)
    if(skid is not None ):
        skid = float(skid)
    
    if not api_key or not api_secret or not fiat_currency or not coin_currency or not value:
        return jsonify({'message': 'Dados incompletos'}), 400

    bot = Bot(user_id=user.id, fiat_currency=fiat_currency, coin_currency=coin_currency, value=value, percentage=percentage, skid=skid, strategy=strategy, purchased=False, price=price, status='RUNNING', sell_percentage=sell_percentage, buy_percentage=buy_percentage, entry_datetime=entry_datetime, lanc_sell_1=lanc_sell_1, lanc_sell_2=lanc_sell_2, lanc_sell_3=lanc_sell_3, lanc_amount_1=lanc_amount_1, lanc_amount_2=lanc_amount_2, lanc_amount_3=lanc_amount_3)
    db.session.add(bot)
    db.session.commit()
    print("entry", entry_datetime)
    print("lanc_sell_1", lanc_sell_1)
    print("lanc_sell_2", lanc_sell_2)
    print("lanc_sell_3", lanc_sell_3)
    print("lanc_amount_1", lanc_amount_1)
    print("lanc_amount_2", lanc_amount_2)
    print("lanc_amount_3", lanc_amount_3)
    print("price", price)
    print("sell_percentage", sell_percentage)
    print("buy_percentage", buy_percentage)
    print("skid", skid)
    print("strategy", strategy)
    print("entry_datetime", entry_datetime)
    print("fiat_currency", fiat_currency)
    print("coin_currency", coin_currency)
    print("value", value)
    print("percentage", percentage)
    print("api_key", api_key)
    print("api_secret", api_secret)
    print("bot.id", bot.id)
    
    trading_bot = TradingBot(bot.id, app, db, BotHistoric, api_key, api_secret, fiat_currency, coin_currency, value, percentage,price, skid,strategy, entry_datetime, buy_percentage, sell_percentage, lanc_sell_1, lanc_sell_2, lanc_sell_3, lanc_amount_1, lanc_amount_2, lanc_amount_3)
    
    thread = Thread(target=trading_bot.run)
   
    bots[bot.id] = trading_bot  
    thread.start()
    return jsonify({'message': 'Bot criado com sucesso'}), 200

@app.route('/stop-bot', methods=['POST'])
@jwt_required()
def stop_bot_api():
    bot_id = request.json.get('id')
    print(bot_id)
    if not bot_id:
        return jsonify({'message': 'ID do bot é necessário'}), 400

    db_bot = Bot.query.filter_by(id=bot_id).first()
    if db_bot:
        db_bot.status = 'STOPPED'
        db.session.commit() 
        bot = bots.get(bot_id)
        if bot:
            bot.stop()
            return jsonify({'message': 'Bot parado com sucesso'}), 200
        else:
            return jsonify({'message': 'Instância do bot não encontrada'}), 404
    else:
        return jsonify({'message': 'Bot não encontrado'}), 404
    
@app.route('/start-bot', methods=['POST'])
@jwt_required()
def start_bot_api():
    bot_id = request.json.get('id')
    if not bot_id:
        return jsonify({'message': 'ID do bot é necessário'}), 400

    db_bot = Bot.query.filter_by(id=bot_id).first()
    if db_bot:
        db_bot.status = 'RUNNING'
        db.session.commit() 
        bot = bots.get(bot_id)
        if bot:
            thread = Thread(target=bot.run)
            thread.start()
            return jsonify({'message': 'Bot iniciado com sucesso'}), 200
        else:
            return jsonify({'message': 'Instância do bot não encontrada'}), 404
    else:
        return jsonify({'message': 'Bot não encontrado'}), 404
    
    
@app.route('/portfolio', methods=['GET'])
@jwt_required()
def portfolio_api():
    id = get_jwt_identity()
    user = User.query.filter_by(id=id).first()
    api_key = user.api_key 
    api_secret = user.api_secret 
    info = fetch_portfolio(api_key, api_secret)
    print(info)
    for asset, amount in info.items():
        print(f"{asset}: {amount}")
    return jsonify(info), 200

@app.route('/delete-bot', methods=['DELETE'])
@jwt_required()
def delete_bot_api():
    id = get_jwt_identity()
    bot = bots.get(id)
    if bot:
        bot.stop()
        return jsonify({'message': 'Bot parado com sucesso'}), 200
    else:
        return jsonify({'message': 'Bot não encontrado'}), 404

@app.route('/bots/historic', methods=['GET'])
@jwt_required()
def bot_historic_api():
    id = get_jwt_identity()
    user = User.query.filter_by(id=id).first()

    bots = Bot.query.filter_by(user_id=user.id).all()
    
    info = []
    for bot in bots:
        bot_historic = BotHistoric.query.filter_by(bot_id=bot.id).all()
        bot_info = {
            'id': bot.id,
            'fiatCurrency': bot.fiat_currency,
            'coinCurrency': bot.coin_currency,
            'value': bot.value,
            'percentage': bot.percentage,
            'skid': bot.skid,
            'strategy': bot.strategy,
            'purchased': bot.purchased,
            'price': bot.price,
            'status': bot.status,
            'entryDatetime': bot.entry_datetime,
            'historic': []
        }
        for historic in bot_historic:
            historic_info = {
                'id': historic.id,
                'price': historic.price,
                'date': historic.date,
                'side': historic.side,
                'quantityFiat': historic.quantity_fiat,
                'quantityCoin': historic.quantity_coin,
                'coinCurrency': historic.coin_currency,
                'fiatCurrency': historic.fiat_currency,
                'balanceCoin': historic.balance_coin,
                'balanceFiat': historic.balance_fiat
            }
            bot_info['historic'].append(historic_info)
        info.append(bot_info)
    return jsonify(info), 200

#if __name__ == '__main__':
#    with app.app_context():
#        db.create_all()
#
#    app.run(debug=True)
    
    
if __name__ == '__main__':
    with app.app_context():
        db.create_all()

    app.run(host='0.0.0.0', port=5173, debug=False)