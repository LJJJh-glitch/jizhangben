from datetime import datetime, date as date_type
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)

    accounts = db.relationship('Account', backref='user', lazy='dynamic')
    categories = db.relationship('Category', backref='user', lazy='dynamic')
    transactions = db.relationship('Transaction', backref='user', lazy='dynamic')
    tags = db.relationship('Tag', backref='user', lazy='dynamic')
    budgets = db.relationship('Budget', backref='user', lazy='dynamic')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Account(db.Model):
    __tablename__ = 'accounts'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    type = db.Column(db.String(20), nullable=False)  # cash, bank, credit, alipay, wechat
    balance = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.now)

    transactions = db.relationship('Transaction', backref='account', lazy='dynamic')

    ACCOUNT_TYPES = {
        'cash': '现金',
        'bank': '银行卡',
        'credit': '信用卡',
        'alipay': '支付宝',
        'wechat': '微信'
    }


class Category(db.Model):
    __tablename__ = 'categories'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    type = db.Column(db.String(10), nullable=False)  # income, expense
    icon = db.Column(db.String(50), default='bi-circle')
    parent_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=True)

    children = db.relationship('Category', backref=db.backref('parent', remote_side=[id]), lazy='dynamic')
    transactions = db.relationship('Transaction', backref='category', lazy='dynamic')
    budgets = db.relationship('Budget', backref='category', lazy='dynamic')


class Transaction(db.Model):
    __tablename__ = 'transactions'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    type = db.Column(db.String(10), nullable=False)  # income, expense
    description = db.Column(db.String(500), default='')
    date = db.Column(db.Date, nullable=False, default=date_type.today)
    created_at = db.Column(db.DateTime, default=datetime.now)

    tag_associations = db.relationship('TransactionTag', backref='transaction', lazy='dynamic', cascade='all, delete-orphan')


class Tag(db.Model):
    __tablename__ = 'tags'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(50), nullable=False)

    transaction_associations = db.relationship('TransactionTag', backref='tag', lazy='select')


class TransactionTag(db.Model):
    __tablename__ = 'transaction_tags'

    transaction_id = db.Column(db.Integer, db.ForeignKey('transactions.id'), primary_key=True)
    tag_id = db.Column(db.Integer, db.ForeignKey('tags.id'), primary_key=True)


class Budget(db.Model):
    __tablename__ = 'budgets'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    month = db.Column(db.Integer, nullable=False)
    year = db.Column(db.Integer, nullable=False)


DEFAULT_CATEGORIES = [
    # 支出分类
    {'name': '餐饮', 'type': 'expense', 'icon': 'bi-cup-hot'},
    {'name': '交通', 'type': 'expense', 'icon': 'bi-bus-front'},
    {'name': '购物', 'type': 'expense', 'icon': 'bi-bag'},
    {'name': '住房', 'type': 'expense', 'icon': 'bi-house'},
    {'name': '娱乐', 'type': 'expense', 'icon': 'bi-controller'},
    {'name': '医疗', 'type': 'expense', 'icon': 'bi-heart-pulse'},
    {'name': '教育', 'type': 'expense', 'icon': 'bi-book'},
    {'name': '通讯', 'type': 'expense', 'icon': 'bi-telephone'},
    {'name': '其他支出', 'type': 'expense', 'icon': 'bi-three-dots'},
    # 收入分类
    {'name': '工资', 'type': 'income', 'icon': 'bi-cash'},
    {'name': '奖金', 'type': 'income', 'icon': 'bi-gift'},
    {'name': '投资', 'type': 'income', 'icon': 'bi-graph-up'},
    {'name': '兼职', 'type': 'income', 'icon': 'bi-briefcase'},
    {'name': '其他收入', 'type': 'income', 'icon': 'bi-three-dots'},
]
