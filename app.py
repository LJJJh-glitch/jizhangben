import csv
import io
from datetime import datetime, date, timedelta
from calendar import monthrange

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, Response
from flask_login import LoginManager, login_user, logout_user, login_required, current_user

from models import db, User, Account, Category, Transaction, Tag, TransactionTag, Budget, DEFAULT_CATEGORIES

app = Flask(__name__)
app.config['SECRET_KEY'] = 'zhangben-secret-key-change-in-production'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///zhangben.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = '请先登录'


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


def init_db():
    with app.app_context():
        db.create_all()


# ==================== 认证路由 ====================

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user, remember=True)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('dashboard'))
        flash('用户名或密码错误', 'danger')

    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        password2 = request.form.get('password2', '')

        if not username or not email or not password:
            flash('所有字段都为必填项', 'danger')
        elif password != password2:
            flash('两次输入的密码不一致', 'danger')
        elif User.query.filter_by(username=username).first():
            flash('用户名已存在', 'danger')
        elif User.query.filter_by(email=email).first():
            flash('邮箱已被注册', 'danger')
        else:
            user = User(username=username, email=email)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()

            # 创建默认分类
            for cat_data in DEFAULT_CATEGORIES:
                category = Category(
                    user_id=user.id,
                    name=cat_data['name'],
                    type=cat_data['type'],
                    icon=cat_data['icon']
                )
                db.session.add(category)
            db.session.commit()

            login_user(user)
            flash('注册成功！', 'success')
            return redirect(url_for('dashboard'))

    return render_template('register.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('已退出登录', 'info')
    return redirect(url_for('login'))


# ==================== 仪表盘 ====================

@app.route('/dashboard')
@login_required
def dashboard():
    today = date.today()
    year = request.args.get('year', today.year, type=int)
    month = request.args.get('month', today.month, type=int)

    # 本月收支统计
    month_start = date(year, month, 1)
    _, last_day = monthrange(year, month)
    month_end = date(year, month, last_day)

    month_transactions = Transaction.query.filter(
        Transaction.user_id == current_user.id,
        Transaction.date >= month_start,
        Transaction.date <= month_end
    ).all()

    month_income = sum(t.amount for t in month_transactions if t.type == 'income')
    month_expense = sum(t.amount for t in month_transactions if t.type == 'expense')

    # 最近 10 笔交易
    recent_transactions = Transaction.query.filter_by(
        user_id=current_user.id
    ).order_by(Transaction.date.desc(), Transaction.created_at.desc()).limit(10).all()

    # 各账户余额
    accounts = Account.query.filter_by(user_id=current_user.id).all()
    total_balance = sum(a.balance for a in accounts)

    # 本月分类支出
    category_expenses = {}
    for t in month_transactions:
        if t.type == 'expense':
            cat_name = t.category.name
            category_expenses[cat_name] = category_expenses.get(cat_name, 0) + t.amount

    # 预算预警
    budgets = Budget.query.filter_by(user_id=current_user.id, month=month, year=year).all()
    budget_alerts = []
    for budget in budgets:
        spent = sum(t.amount for t in month_transactions if t.type == 'expense' and t.category_id == budget.category_id)
        if spent > budget.amount * 0.8:
            budget_alerts.append({
                'category': budget.category.name,
                'budget': budget.amount,
                'spent': spent,
                'percent': round(spent / budget.amount * 100, 1)
            })

    return render_template('dashboard.html',
                           year=year, month=month,
                           month_income=month_income,
                           month_expense=month_expense,
                           recent_transactions=recent_transactions,
                           accounts=accounts,
                           total_balance=total_balance,
                           category_expenses=category_expenses,
                           budget_alerts=budget_alerts,
                           account_types=Account.ACCOUNT_TYPES,
                           now_hour=datetime.now().hour)


# ==================== 更多菜单 ====================

@app.route('/more')
@login_required
def more_menu():
    return render_template('more.html')


# ==================== 账户管理 ====================

@app.route('/accounts')
@login_required
def accounts_list():
    accounts = Account.query.filter_by(user_id=current_user.id).all()
    return render_template('accounts.html', accounts=accounts, account_types=Account.ACCOUNT_TYPES)


@app.route('/accounts/add', methods=['POST'])
@login_required
def account_add():
    name = request.form.get('name', '').strip()
    account_type = request.form.get('type', '')
    balance = request.form.get('balance', 0, type=float)

    if not name or account_type not in Account.ACCOUNT_TYPES:
        flash('请填写完整的账户信息', 'danger')
    else:
        account = Account(user_id=current_user.id, name=name, type=account_type, balance=balance)
        db.session.add(account)
        db.session.commit()
        flash('账户添加成功', 'success')

    return redirect(url_for('accounts_list'))


@app.route('/accounts/<int:id>/edit', methods=['POST'])
@login_required
def account_edit(id):
    account = Account.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    name = request.form.get('name', '').strip()
    account_type = request.form.get('type', '')

    if name and account_type in Account.ACCOUNT_TYPES:
        account.name = name
        account.type = account_type
        db.session.commit()
        flash('账户更新成功', 'success')
    else:
        flash('请填写完整信息', 'danger')

    return redirect(url_for('accounts_list'))


@app.route('/accounts/<int:id>/delete', methods=['POST'])
@login_required
def account_delete(id):
    account = Account.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    if account.transactions.count() > 0:
        flash('该账户下有交易记录，无法删除', 'danger')
    else:
        db.session.delete(account)
        db.session.commit()
        flash('账户已删除', 'success')
    return redirect(url_for('accounts_list'))


# ==================== 分类管理 ====================

@app.route('/categories')
@login_required
def categories_list():
    income_categories = Category.query.filter_by(
        user_id=current_user.id, type='income', parent_id=None
    ).all()
    expense_categories = Category.query.filter_by(
        user_id=current_user.id, type='expense', parent_id=None
    ).all()
    return render_template('categories.html',
                           income_categories=income_categories,
                           expense_categories=expense_categories)


@app.route('/categories/add', methods=['POST'])
@login_required
def category_add():
    name = request.form.get('name', '').strip()
    cat_type = request.form.get('type', '')
    icon = request.form.get('icon', 'bi-circle').strip()
    parent_id = request.form.get('parent_id', type=int)

    if not name or cat_type not in ('income', 'expense'):
        flash('请填写完整的分类信息', 'danger')
    else:
        category = Category(
            user_id=current_user.id,
            name=name,
            type=cat_type,
            icon=icon,
            parent_id=parent_id if parent_id else None
        )
        db.session.add(category)
        db.session.commit()
        flash('分类添加成功', 'success')

    return redirect(url_for('categories_list'))


@app.route('/categories/<int:id>/edit', methods=['POST'])
@login_required
def category_edit(id):
    category = Category.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    name = request.form.get('name', '').strip()
    icon = request.form.get('icon', '').strip()

    if name:
        category.name = name
        if icon:
            category.icon = icon
        db.session.commit()
        flash('分类更新成功', 'success')

    return redirect(url_for('categories_list'))


@app.route('/categories/<int:id>/delete', methods=['POST'])
@login_required
def category_delete(id):
    category = Category.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    if category.transactions.count() > 0:
        flash('该分类下有交易记录，无法删除', 'danger')
    else:
        db.session.delete(category)
        db.session.commit()
        flash('分类已删除', 'success')
    return redirect(url_for('categories_list'))


# ==================== 交易记录 ====================

@app.route('/transactions')
@login_required
def transactions_list():
    page = request.args.get('page', 1, type=int)
    per_page = 20

    query = Transaction.query.filter_by(user_id=current_user.id)

    # 筛选条件
    account_id = request.args.get('account_id', type=int)
    category_id = request.args.get('category_id', type=int)
    trans_type = request.args.get('type', '')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    tag_id = request.args.get('tag_id', type=int)

    if account_id:
        query = query.filter_by(account_id=account_id)
    if category_id:
        query = query.filter_by(category_id=category_id)
    if trans_type in ('income', 'expense'):
        query = query.filter_by(type=trans_type)
    if start_date:
        query = query.filter(Transaction.date >= start_date)
    if end_date:
        query = query.filter(Transaction.date <= end_date)
    if tag_id:
        query = query.join(TransactionTag).filter(TransactionTag.tag_id == tag_id)

    pagination = query.order_by(
        Transaction.date.desc(), Transaction.created_at.desc()
    ).paginate(page=page, per_page=per_page)

    accounts = Account.query.filter_by(user_id=current_user.id).all()
    categories = Category.query.filter_by(user_id=current_user.id).all()
    tags = Tag.query.filter_by(user_id=current_user.id).all()

    return render_template('transactions.html',
                           transactions=pagination.items,
                           pagination=pagination,
                           accounts=accounts,
                           categories=categories,
                           tags=tags,
                           account_types=Account.ACCOUNT_TYPES,
                           today=date.today())


@app.route('/transactions/add', methods=['GET', 'POST'])
@login_required
def transaction_add():
    if request.method == 'POST':
        account_id = request.form.get('account_id', type=int)
        category_id = request.form.get('category_id', type=int)
        amount = request.form.get('amount', type=float)
        trans_type = request.form.get('type', '')
        description = request.form.get('description', '').strip()
        trans_date = request.form.get('date', '')
        tag_ids = request.form.getlist('tags')

        if not all([account_id, category_id, amount, trans_type, trans_date]):
            flash('请填写完整的交易信息', 'danger')
        elif amount <= 0:
            flash('金额必须大于零', 'danger')
        else:
            account = Account.query.filter_by(id=account_id, user_id=current_user.id).first_or_404()
            transaction = Transaction(
                user_id=current_user.id,
                account_id=account_id,
                category_id=category_id,
                amount=amount,
                type=trans_type,
                description=description,
                date=datetime.strptime(trans_date, '%Y-%m-%d').date()
            )
            db.session.add(transaction)

            # 更新账户余额
            if trans_type == 'income':
                account.balance += amount
            else:
                account.balance -= amount

            # 添加标签
            for tag_id in tag_ids:
                tag = Tag.query.filter_by(id=tag_id, user_id=current_user.id).first()
                if tag:
                    db.session.add(TransactionTag(transaction=transaction, tag=tag))

            db.session.commit()
            flash('交易记录添加成功', 'success')
            return redirect(url_for('transactions_list'))

    accounts = Account.query.filter_by(user_id=current_user.id).all()
    categories = Category.query.filter_by(user_id=current_user.id).all()
    tags = Tag.query.filter_by(user_id=current_user.id).all()
    today = date.today()
    yesterday = today - timedelta(days=1)
    two_days_ago = today - timedelta(days=2)
    recent_dates = [(today - timedelta(days=i)).strftime('%Y-%m-%d') for i in range(3, 8)]

    return render_template('transaction_form.html',
                           accounts=accounts,
                           categories=categories,
                           tags=tags,
                           today=today.strftime('%Y-%m-%d'),
                           yesterday=yesterday.strftime('%Y-%m-%d'),
                           two_days_ago=two_days_ago.strftime('%Y-%m-%d'),
                           recent_dates=recent_dates,
                           edit=False)


@app.route('/transactions/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def transaction_edit(id):
    transaction = Transaction.query.filter_by(id=id, user_id=current_user.id).first_or_404()

    if request.method == 'POST':
        account_id = request.form.get('account_id', type=int)
        category_id = request.form.get('category_id', type=int)
        amount = request.form.get('amount', type=float)
        trans_type = request.form.get('type', '')
        description = request.form.get('description', '').strip()
        trans_date = request.form.get('date', '')
        tag_ids = request.form.getlist('tags')

        if not all([account_id, category_id, amount, trans_type, trans_date]):
            flash('请填写完整的交易信息', 'danger')
        else:
            # 恢复原账户余额
            old_account = Account.query.get(transaction.account_id)
            if transaction.type == 'income':
                old_account.balance -= transaction.amount
            else:
                old_account.balance += transaction.amount

            # 更新交易信息
            transaction.account_id = account_id
            transaction.category_id = category_id
            transaction.amount = amount
            transaction.type = trans_type
            transaction.description = description
            transaction.date = datetime.strptime(trans_date, '%Y-%m-%d').date()

            # 更新新账户余额
            new_account = Account.query.get(account_id)
            if trans_type == 'income':
                new_account.balance += amount
            else:
                new_account.balance -= amount

            # 更新标签
            TransactionTag.query.filter_by(transaction_id=transaction.id).delete()
            for tag_id in tag_ids:
                tag = Tag.query.filter_by(id=tag_id, user_id=current_user.id).first()
                if tag:
                    db.session.add(TransactionTag(transaction=transaction, tag=tag))

            db.session.commit()
            flash('交易记录更新成功', 'success')
            return redirect(url_for('transactions_list'))

    accounts = Account.query.filter_by(user_id=current_user.id).all()
    categories = Category.query.filter_by(user_id=current_user.id).all()
    tags = Tag.query.filter_by(user_id=current_user.id).all()
    selected_tags = [at.tag_id for at in transaction.tag_associations.all()]
    today = date.today()
    yesterday = today - timedelta(days=1)
    two_days_ago = today - timedelta(days=2)
    recent_dates = [(today - timedelta(days=i)).strftime('%Y-%m-%d') for i in range(3, 8)]

    return render_template('transaction_form.html',
                           transaction=transaction,
                           accounts=accounts,
                           categories=categories,
                           tags=tags,
                           selected_tags=selected_tags,
                           today=transaction.date.strftime('%Y-%m-%d'),
                           yesterday=yesterday.strftime('%Y-%m-%d'),
                           two_days_ago=two_days_ago.strftime('%Y-%m-%d'),
                           recent_dates=recent_dates,
                           edit=True)


@app.route('/transactions/<int:id>/delete', methods=['POST'])
@login_required
def transaction_delete(id):
    transaction = Transaction.query.filter_by(id=id, user_id=current_user.id).first_or_404()

    # 恢复账户余额
    account = Account.query.get(transaction.account_id)
    if transaction.type == 'income':
        account.balance -= transaction.amount
    else:
        account.balance += transaction.amount

    db.session.delete(transaction)
    db.session.commit()
    flash('交易记录已删除', 'success')
    return redirect(url_for('transactions_list'))


# ==================== 标签管理 ====================

@app.route('/tags')
@login_required
def tags_list():
    tags = Tag.query.filter_by(user_id=current_user.id).all()
    return render_template('tags.html', tags=tags)


@app.route('/tags/add', methods=['POST'])
@login_required
def tag_add():
    name = request.form.get('name', '').strip()
    if not name:
        flash('标签名称不能为空', 'danger')
    elif Tag.query.filter_by(user_id=current_user.id, name=name).first():
        flash('标签已存在', 'danger')
    else:
        tag = Tag(user_id=current_user.id, name=name)
        db.session.add(tag)
        db.session.commit()
        flash('标签添加成功', 'success')
    return redirect(url_for('tags_list'))


@app.route('/tags/<int:id>/edit', methods=['POST'])
@login_required
def tag_edit(id):
    tag = Tag.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    name = request.form.get('name', '').strip()
    if name:
        tag.name = name
        db.session.commit()
        flash('标签更新成功', 'success')
    return redirect(url_for('tags_list'))


@app.route('/tags/<int:id>/delete', methods=['POST'])
@login_required
def tag_delete(id):
    tag = Tag.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    db.session.delete(tag)
    db.session.commit()
    flash('标签已删除', 'success')
    return redirect(url_for('tags_list'))


# ==================== 预算管理 ====================

@app.route('/budget')
@login_required
def budget_list():
    today = date.today()
    year = request.args.get('year', today.year, type=int)
    month = request.args.get('month', today.month, type=int)

    budgets = Budget.query.filter_by(
        user_id=current_user.id, month=month, year=year
    ).all()

    # 计算每个预算的使用情况
    month_start = date(year, month, 1)
    _, last_day = monthrange(year, month)
    month_end = date(year, month, last_day)

    month_expenses = Transaction.query.filter(
        Transaction.user_id == current_user.id,
        Transaction.type == 'expense',
        Transaction.date >= month_start,
        Transaction.date <= month_end
    ).all()

    budget_data = []
    for budget in budgets:
        spent = sum(t.amount for t in month_expenses if t.category_id == budget.category_id)
        percent = round(spent / budget.amount * 100, 1) if budget.amount > 0 else 0
        budget_data.append({
            'budget': budget,
            'spent': spent,
            'remaining': budget.amount - spent,
            'percent': percent
        })

    # 可设置预算的分类
    expense_categories = Category.query.filter_by(
        user_id=current_user.id, type='expense', parent_id=None
    ).all()

    return render_template('budget.html',
                           budget_data=budget_data,
                           expense_categories=expense_categories,
                           year=year, month=month)


@app.route('/budget/add', methods=['POST'])
@login_required
def budget_add():
    category_id = request.form.get('category_id', type=int)
    amount = request.form.get('amount', type=float)
    month = request.form.get('month', type=int)
    year = request.form.get('year', type=int)

    if not all([category_id, amount, month, year]):
        flash('请填写完整的预算信息', 'danger')
    elif amount <= 0:
        flash('预算金额必须大于零', 'danger')
    else:
        existing = Budget.query.filter_by(
            user_id=current_user.id,
            category_id=category_id,
            month=month,
            year=year
        ).first()

        if existing:
            existing.amount = amount
            flash('预算已更新', 'success')
        else:
            budget = Budget(
                user_id=current_user.id,
                category_id=category_id,
                amount=amount,
                month=month,
                year=year
            )
            db.session.add(budget)
            flash('预算设置成功', 'success')

        db.session.commit()

    return redirect(url_for('budget_list', year=year, month=month))


@app.route('/budget/<int:id>/delete', methods=['POST'])
@login_required
def budget_delete(id):
    budget = Budget.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    year, month = budget.year, budget.month
    db.session.delete(budget)
    db.session.commit()
    flash('预算已删除', 'success')
    return redirect(url_for('budget_list', year=year, month=month))


# ==================== 报表 ====================

@app.route('/reports')
@login_required
def reports():
    today = date.today()
    year = request.args.get('year', today.year, type=int)

    # 月度收支趋势
    monthly_data = []
    for m in range(1, 13):
        month_start = date(year, m, 1)
        _, last_day = monthrange(year, m)
        month_end = date(year, m, last_day)

        transactions = Transaction.query.filter(
            Transaction.user_id == current_user.id,
            Transaction.date >= month_start,
            Transaction.date <= month_end
        ).all()

        income = sum(t.amount for t in transactions if t.type == 'income')
        expense = sum(t.amount for t in transactions if t.type == 'expense')
        monthly_data.append({
            'month': m,
            'income': income,
            'expense': expense,
            'balance': income - expense
        })

    # 年度汇总
    year_income = sum(d['income'] for d in monthly_data)
    year_expense = sum(d['expense'] for d in monthly_data)

    # 分类支出排行
    year_start = date(year, 1, 1)
    year_end = date(year, 12, 31)
    year_transactions = Transaction.query.filter(
        Transaction.user_id == current_user.id,
        Transaction.type == 'expense',
        Transaction.date >= year_start,
        Transaction.date <= year_end
    ).all()

    category_totals = {}
    for t in year_transactions:
        cat_name = t.category.name
        category_totals[cat_name] = category_totals.get(cat_name, 0) + t.amount

    sorted_categories = sorted(category_totals.items(), key=lambda x: x[1], reverse=True)

    return render_template('reports.html',
                           year=year,
                           monthly_data=monthly_data,
                           year_income=year_income,
                           year_expense=year_expense,
                           sorted_categories=sorted_categories)


@app.route('/reports/export')
@login_required
def export_csv():
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')

    query = Transaction.query.filter_by(user_id=current_user.id)

    if start_date:
        query = query.filter(Transaction.date >= start_date)
    if end_date:
        query = query.filter(Transaction.date <= end_date)

    transactions = query.order_by(Transaction.date.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['日期', '类型', '分类', '账户', '金额', '标签', '备注'])

    for t in transactions:
        tags = ', '.join(at.tag.name for at in t.tag_associations.all())
        writer.writerow([
            t.date.strftime('%Y-%m-%d'),
            '收入' if t.type == 'income' else '支出',
            t.category.name,
            t.account.name,
            t.amount,
            tags,
            t.description
        ])

    output.seek(0)
    return Response(
        '﻿' + output.getvalue(),
        mimetype='text/csv',
        headers={
            'Content-Disposition': f'attachment; filename=transactions_{datetime.now().strftime("%Y%m%d")}.csv'
        }
    )


# ==================== API 端点 ====================

@app.route('/api/chart/monthly')
@login_required
def api_monthly_chart():
    year = request.args.get('year', date.today().year, type=int)
    data = []
    for m in range(1, 13):
        month_start = date(year, m, 1)
        _, last_day = monthrange(year, m)
        month_end = date(year, m, last_day)

        transactions = Transaction.query.filter(
            Transaction.user_id == current_user.id,
            Transaction.date >= month_start,
            Transaction.date <= month_end
        ).all()

        income = sum(t.amount for t in transactions if t.type == 'income')
        expense = sum(t.amount for t in transactions if t.type == 'expense')
        data.append({'month': m, 'income': income, 'expense': expense})

    return jsonify(data)


@app.route('/api/chart/category')
@login_required
def api_category_chart():
    today = date.today()
    year = request.args.get('year', today.year, type=int)
    month = request.args.get('month', today.month, type=int)

    month_start = date(year, month, 1)
    _, last_day = monthrange(year, month)
    month_end = date(year, month, last_day)

    transactions = Transaction.query.filter(
        Transaction.user_id == current_user.id,
        Transaction.type == 'expense',
        Transaction.date >= month_start,
        Transaction.date <= month_end
    ).all()

    category_totals = {}
    for t in transactions:
        cat_name = t.category.name
        category_totals[cat_name] = category_totals.get(cat_name, 0) + t.amount

    return jsonify([{'name': k, 'value': v} for k, v in category_totals.items()])


if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5000)
